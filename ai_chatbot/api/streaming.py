# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Streaming API Module
Real-time token streaming via frappe.publish_realtime (Socket.IO/WebSocket)

The streaming endpoint enqueues the AI response generation as a background
job so the HTTP response returns immediately. Tokens are delivered to the
frontend via frappe.publish_realtime → Redis Pub/Sub → Socket.IO.
"""

import json
import uuid

import frappe

from ai_chatbot.core.prompts import build_system_prompt
from ai_chatbot.core.token_optimizer import optimize_history
from ai_chatbot.core.token_tracker import track_token_usage
from ai_chatbot.tools.base import BaseTool, get_all_tools_schema
from ai_chatbot.utils.ai_providers import get_ai_provider

# Buffer threshold — batch tokens to reduce Redis Pub/Sub overhead
TOKEN_BUFFER_SIZE = 20  # characters


@frappe.whitelist()
def send_message_streaming(conversation_id: str, message: str, attachments: str | None = None) -> dict:
	"""Send a message and stream the AI response via frappe.publish_realtime.

	Saves the user message, then enqueues a background job that streams
	tokens via Socket.IO. Returns immediately with the stream_id so the
	frontend can start listening for realtime events.

	Args:
		conversation_id: The conversation document name.
		message: The user's message text.
		attachments: Optional JSON string of file attachment metadata.

	Returns:
		dict with success status and stream_id.
	"""
	try:
		# Validate conversation ownership
		conversation = frappe.get_doc("Chatbot Conversation", conversation_id)
		if conversation.user != frappe.session.user:
			frappe.throw("Unauthorized access to conversation")

		# Generate a unique stream ID for this request
		stream_id = str(uuid.uuid4())[:8]

		# Save user message immediately (before enqueue)
		msg_doc = {
			"doctype": "Chatbot Message",
			"conversation": conversation_id,
			"role": "user",
			"content": message,
			"timestamp": frappe.utils.now(),
		}
		if attachments:
			msg_doc["attachments"] = attachments
		frappe.get_doc(msg_doc).insert()
		frappe.db.commit()

		# Enqueue the streaming job so HTTP response returns immediately.
		# Always use now=False (even in dev mode) to ensure the HTTP response
		# returns before tokens start streaming. With now=True the job runs
		# synchronously, blocking the response and making tokens appear all at once.
		frappe.enqueue(
			"ai_chatbot.api.streaming._run_streaming_job",
			queue="default",
			timeout=300,
			now=False,
			conversation_id=conversation_id,
			stream_id=stream_id,
			ai_provider=conversation.ai_provider,
			user=frappe.session.user,
		)

		return {"success": True, "stream_id": stream_id}

	except Exception as e:
		frappe.log_error(f"Streaming error: {e!s}", "AI Chatbot Streaming")
		return {"success": False, "error": str(e)}


def _run_streaming_job(conversation_id: str, stream_id: str, ai_provider: str, user: str):
	"""Background job that performs the actual AI streaming.

	This runs in a background worker (or inline in dev mode via now=True).
	Publishes tokens via frappe.publish_realtime as they arrive.
	"""
	try:
		# Set conversation context for session tools
		frappe.flags.current_conversation_id = conversation_id

		# Notify frontend: stream started
		_publish(
			"ai_chat_stream_start",
			{
				"conversation_id": conversation_id,
				"stream_id": stream_id,
			},
			user=user,
		)

		_publish_process_step(conversation_id, stream_id, "Preparing context...", user)

		# Get conversation history and provider
		history = _get_conversation_history(conversation_id)

		# Prepend system prompt (pass conversation_id for session context)
		system_prompt = build_system_prompt(conversation_id=conversation_id)
		history = [{"role": "system", "content": system_prompt}, *history]

		# Optimize history (trim + compress tool results)
		history = optimize_history(history)

		_publish_process_step(conversation_id, stream_id, "Communicating with LLM...", user)

		provider = get_ai_provider(ai_provider)
		tools = get_all_tools_schema()

		# Run the streaming loop
		full_content, tool_calls_data, tool_results_data, tokens_used, prompt_tokens, completion_tokens = (
			_stream_with_tools(
				ai_provider=ai_provider,
				provider=provider,
				history=history,
				tools=tools,
				conversation_id=conversation_id,
				stream_id=stream_id,
				user=user,
			)
		)

		_publish_process_step(conversation_id, stream_id, "Saving response...", user)

		# Save assistant message to database
		frappe.get_doc(
			{
				"doctype": "Chatbot Message",
				"conversation": conversation_id,
				"role": "assistant",
				"content": full_content,
				"timestamp": frappe.utils.now(),
				"tokens_used": tokens_used,
				"tool_calls": json.dumps(tool_calls_data) if tool_calls_data else None,
				"tool_results": json.dumps(tool_results_data) if tool_results_data else None,
			}
		).insert()

		# Track token usage with real prompt/completion split from the provider
		track_token_usage(
			provider=ai_provider,
			model=provider.model,
			prompt_tokens=prompt_tokens,
			completion_tokens=completion_tokens,
			user=user,
			conversation_id=conversation_id,
		)

		# Update conversation metadata
		conversation = frappe.get_doc("Chatbot Conversation", conversation_id)
		conversation.message_count = frappe.db.count("Chatbot Message", {"conversation": conversation_id})
		conversation.total_tokens += tokens_used
		conversation.updated_at = frappe.utils.now()

		# Auto-generate title from first user message
		if conversation.title == "New Chat" and conversation.message_count == 2:
			first_msg = frappe.get_all(
				"Chatbot Message",
				filters={"conversation": conversation_id, "role": "user"},
				fields=["content"],
				order_by="timestamp asc",
				limit=1,
			)
			if first_msg:
				title = first_msg[0].content[:50].strip()
				if len(first_msg[0].content) > 50:
					title += "..."
				conversation.title = title

		conversation.save(ignore_version=True)
		frappe.db.commit()

		# Notify frontend: stream ended
		_publish(
			"ai_chat_stream_end",
			{
				"conversation_id": conversation_id,
				"stream_id": stream_id,
				"content": full_content,
				"tokens_used": tokens_used,
				"tool_calls": tool_calls_data,
			},
			user=user,
		)

	except Exception as e:
		frappe.log_error(f"Streaming job error: {e!s}", "AI Chatbot Streaming")
		_publish(
			"ai_chat_error",
			{
				"conversation_id": conversation_id,
				"stream_id": stream_id,
				"error": str(e),
			},
			user=user,
		)


def _stream_with_tools(
	ai_provider, provider, history, tools, conversation_id, stream_id, user, max_tool_rounds=5
):
	"""Stream AI response with tool call support.

	Handles the loop: stream tokens → tool call detected → execute tool →
	add results to history → stream again with tool results.

	Returns:
		tuple of (full_content, tool_calls_data, tool_results_data,
		          tokens_used, prompt_tokens, completion_tokens)
	"""
	# Check if agent orchestration should handle this query
	from ai_chatbot.ai.agents.orchestrator import run_orchestrated_streaming, should_orchestrate

	user_msg = next((m.get("content", "") for m in reversed(history) if m.get("role") == "user"), "")
	if isinstance(user_msg, list):
		user_msg = " ".join(p.get("text", "") for p in user_msg if p.get("type") == "text")

	if should_orchestrate(provider, user_msg, history, tools):
		result = run_orchestrated_streaming(
			ai_provider=ai_provider,
			provider=provider,
			history=history,
			tools=tools,
			conversation_id=conversation_id,
			stream_id=stream_id,
			user=user,
		)
		if result is not None:
			return result
		# Fall through to standard flow if orchestration returned None

	full_content = ""
	all_tool_calls = []
	all_tool_results = []
	total_prompt_tokens = 0
	total_completion_tokens = 0

	for _round in range(max_tool_rounds):
		round_content, round_tool_calls, _needs_followup, round_usage = _stream_single_round(
			provider=provider,
			history=history,
			tools=tools,
			conversation_id=conversation_id,
			stream_id=stream_id,
			user=user,
		)

		# Accumulate real usage data from the provider
		if round_usage:
			total_prompt_tokens += round_usage.get("prompt_tokens", 0)
			total_completion_tokens += round_usage.get("completion_tokens", 0)

		full_content += round_content

		if not round_tool_calls:
			# No tool calls — we're done
			break

		# Execute tool calls and add results to history
		all_tool_calls.extend(round_tool_calls)

		# Add assistant message with tool calls to history
		if ai_provider in ("OpenAI", "Gemini"):
			openai_tool_calls = []
			for tc in round_tool_calls:
				openai_tool_calls.append(
					{
						"id": tc["id"],
						"type": "function",
						"function": {
							"name": tc["name"],
							"arguments": json.dumps(tc["arguments"]),
						},
					}
				)
			history.append(
				{
					"role": "assistant",
					"content": round_content or None,
					"tool_calls": openai_tool_calls,
				}
			)
		else:
			history.append(
				{
					"role": "assistant",
					"content": round_content or None,
					"tool_calls": round_tool_calls,
				}
			)

		# Execute each tool and add results
		for tc in round_tool_calls:
			tool_display = tc["name"].replace("_", " ").title()
			_publish_process_step(conversation_id, stream_id, f"Executing {tool_display}...", user)

			_publish(
				"ai_chat_tool_call",
				{
					"conversation_id": conversation_id,
					"stream_id": stream_id,
					"tool_name": tc["name"],
					"tool_arguments": tc["arguments"],
				},
				user=user,
			)

			try:
				result = BaseTool.execute_tool(tc["name"], tc["arguments"])
			except Exception as e:
				result = {"error": str(e)}

			all_tool_results.append(result)

			_publish(
				"ai_chat_tool_result",
				{
					"conversation_id": conversation_id,
					"stream_id": stream_id,
					"tool_name": tc["name"],
					"result": result,
				},
				user=user,
			)

			history.append(
				{
					"role": "tool",
					"content": json.dumps(result),
					"tool_call_id": tc["id"],
				}
			)

		_publish_process_step(conversation_id, stream_id, "Processing results...", user)

		# Continue streaming with tool results in history
	else:
		# Max rounds reached
		pass

	# Use real usage data from the provider when available; fall back to estimate
	if total_prompt_tokens or total_completion_tokens:
		tokens_used = total_prompt_tokens + total_completion_tokens
	else:
		tokens_used = _estimate_tokens(full_content, history)
		total_completion_tokens = tokens_used

	return (
		full_content,
		all_tool_calls,
		all_tool_results,
		tokens_used,
		total_prompt_tokens,
		total_completion_tokens,
	)


def _stream_single_round(provider, history, tools, conversation_id, stream_id, user):
	"""Stream a single round of AI response.

	Returns:
		tuple of (content, tool_calls, needs_followup, usage)
		where tool_calls is a list of dicts with id, name, arguments
		and usage is a dict with prompt_tokens and completion_tokens (or None)
	"""
	content = ""
	tool_calls = []
	buffer = ""
	usage = None

	for event in provider.chat_completion_stream(history, tools=tools):
		event_type = event.get("type")

		if event_type == "token":
			token_text = event.get("content", "")
			content += token_text
			buffer += token_text

			# Flush buffer when it reaches threshold
			if len(buffer) >= TOKEN_BUFFER_SIZE:
				_publish(
					"ai_chat_token",
					{
						"conversation_id": conversation_id,
						"stream_id": stream_id,
						"content": buffer,
					},
					user=user,
				)
				buffer = ""

		elif event_type == "usage":
			usage = {
				"prompt_tokens": event.get("prompt_tokens", 0),
				"completion_tokens": event.get("completion_tokens", 0),
			}

		elif event_type == "tool_call":
			tc = event.get("tool_call", {})
			tool_calls.append(
				{
					"id": tc.get("id", f"tool_{len(tool_calls)}"),
					"name": tc.get("name", ""),
					"arguments": tc.get("arguments", {}),
				}
			)

		elif event_type == "finish":
			# Flush remaining buffer
			if buffer:
				_publish(
					"ai_chat_token",
					{
						"conversation_id": conversation_id,
						"stream_id": stream_id,
						"content": buffer,
					},
					user=user,
				)
				buffer = ""

		elif event_type == "error":
			_publish(
				"ai_chat_error",
				{
					"conversation_id": conversation_id,
					"stream_id": stream_id,
					"error": event.get("content", "Unknown error"),
				},
				user=user,
			)
			break

	# Flush any remaining buffer
	if buffer:
		_publish(
			"ai_chat_token",
			{
				"conversation_id": conversation_id,
				"stream_id": stream_id,
				"content": buffer,
			},
			user=user,
		)

	return content, tool_calls, bool(tool_calls), usage


def _publish(event, message, user=None):
	"""Publish a realtime event to the specified user."""
	frappe.publish_realtime(
		event,
		message=message,
		user=user or frappe.session.user,
	)


def _publish_process_step(conversation_id, stream_id, step, user):
	"""Publish a process step indicator to the frontend."""
	_publish(
		"ai_chat_process_step",
		{
			"conversation_id": conversation_id,
			"stream_id": stream_id,
			"step": step,
		},
		user=user,
	)


def _get_conversation_history(conversation_id: str) -> list[dict]:
	"""Get conversation history in AI message format.

	For messages with image attachments, builds multimodal content arrays
	using the OpenAI Vision format (converted to Claude format by the provider).
	"""
	messages = frappe.get_all(
		"Chatbot Message",
		filters={"conversation": conversation_id},
		fields=["role", "content", "tool_calls", "attachments"],
		order_by="timestamp asc",
	)

	history = []
	for msg in messages:
		# Check if user message has attachments — build appropriate content
		if msg.role == "user" and msg.attachments:
			try:
				atts = json.loads(msg.attachments) if isinstance(msg.attachments, str) else msg.attachments
			except (json.JSONDecodeError, TypeError):
				atts = None

			if atts:
				has_images = any(a.get("is_image") for a in atts)
				if has_images:
					# Image attachments: use multimodal Vision content
					from ai_chatbot.api.files import build_vision_content

					content = build_vision_content(msg.content or "", atts)
					history.append({"role": msg.role, "content": content})
				else:
					# Non-image attachments (PDF, Excel, etc.): append file refs
					# so the LLM knows the file_url for IDP tools
					text = msg.content or ""
					for att in atts:
						file_url = att.get("file_url", "")
						file_name = att.get("file_name", "unknown")
						mime_type = att.get("mime_type", "")
						text += f"\n[Attached file: {file_name} ({mime_type}), file_url: {file_url}]"
					history.append({"role": msg.role, "content": text})
				continue

		message_dict = {"role": msg.role, "content": msg.content}
		history.append(message_dict)

	return history


def _estimate_tokens(content: str, history: list[dict]) -> int:
	"""Rough token estimation (1 token ~ 4 chars).

	This is an approximation. For accurate counts, the provider response
	would need to include usage data, which streaming doesn't always provide.
	"""
	total_chars = len(content)
	for msg in history:
		total_chars += len(msg.get("content") or "")
	return total_chars // 4
