"""
Chat API Module
RESTful API endpoints for AI chatbot
"""

import json

import frappe

from ai_chatbot.core.prompts import build_system_prompt
from ai_chatbot.tools.base import BaseTool, get_all_tools_schema
from ai_chatbot.utils.ai_providers import get_ai_provider


@frappe.whitelist()
def create_conversation(title: str, ai_provider: str = "OpenAI") -> dict:
	"""Create a new chat conversation"""
	try:
		conversation = frappe.get_doc(
			{
				"doctype": "Chatbot Conversation",
				"title": title,
				"user": frappe.session.user,
				"ai_provider": ai_provider,
				"status": "Active",
				"created_at": frappe.utils.now(),
				"updated_at": frappe.utils.now(),
			}
		)
		conversation.insert()
		frappe.db.commit()

		return {
			"success": True,
			"conversation_id": conversation.name,
			"data": conversation.as_dict(),
		}
	except Exception as e:
		frappe.log_error(f"Error creating conversation: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_conversations(limit: int = 20) -> dict:
	"""Get user's conversations"""
	try:
		conversations = frappe.get_all(
			"Chatbot Conversation",
			filters={"user": frappe.session.user},
			fields=["name", "title", "ai_provider", "status", "created_at", "updated_at", "message_count"],
			order_by="updated_at desc",
			limit=limit,
		)

		return {
			"success": True,
			"conversations": conversations,
		}
	except Exception as e:
		frappe.log_error(f"Error getting conversations: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_conversation_messages(conversation_id: str) -> dict:
	"""Get messages for a conversation"""
	try:
		messages = frappe.get_all(
			"Chatbot Message",
			filters={"conversation": conversation_id},
			fields=["name", "role", "content", "timestamp", "tokens_used", "tool_calls", "tool_results"],
			order_by="timestamp asc",
		)

		# Parse JSON string fields
		for msg in messages:
			if msg.get("tool_calls"):
				try:
					msg["tool_calls"] = (
						json.loads(msg["tool_calls"])
						if isinstance(msg["tool_calls"], str)
						else msg["tool_calls"]
					)
				except (json.JSONDecodeError, TypeError):
					msg["tool_calls"] = None
			if msg.get("tool_results"):
				try:
					msg["tool_results"] = (
						json.loads(msg["tool_results"])
						if isinstance(msg["tool_results"], str)
						else msg["tool_results"]
					)
				except (json.JSONDecodeError, TypeError):
					msg["tool_results"] = None

		return {
			"success": True,
			"messages": messages,
		}
	except Exception as e:
		frappe.log_error(f"Error getting messages: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_message(conversation_id: str, message: str, stream: bool = False) -> dict:
	"""Send a message and get AI response.

	When stream=True, delegates to the streaming API which delivers tokens
	via frappe.publish_realtime. The HTTP response returns immediately with
	the stream_id. When stream=False, returns the complete response.
	"""
	try:
		if stream:
			from ai_chatbot.api.streaming import send_message_streaming

			return send_message_streaming(conversation_id, message)

		# Validate conversation
		conversation = frappe.get_doc("Chatbot Conversation", conversation_id)
		if conversation.user != frappe.session.user:
			frappe.throw("Unauthorized access to conversation")

		# Save user message
		frappe.get_doc(
			{
				"doctype": "Chatbot Message",
				"conversation": conversation_id,
				"role": "user",
				"content": message,
				"timestamp": frappe.utils.now(),
			}
		).insert()

		# Get conversation history
		history = get_conversation_history(conversation_id)

		# Prepend system prompt
		system_prompt = build_system_prompt()
		history = [{"role": "system", "content": system_prompt}, *history]

		# Get AI provider
		provider = get_ai_provider(conversation.ai_provider)

		# Get ERPNext tools if enabled
		tools = get_all_tools_schema()

		# Generate non-streaming response
		return generate_ai_response(conversation, provider, history, tools)

	except Exception as e:
		frappe.log_error(f"Error sending message: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


def get_conversation_history(conversation_id: str) -> list[dict]:
	"""Get conversation history in AI format"""
	messages = frappe.get_all(
		"Chatbot Message",
		filters={"conversation": conversation_id},
		fields=["role", "content", "tool_calls"],
		order_by="timestamp asc",
	)

	history = []
	for msg in messages:
		message_dict = {"role": msg.role, "content": msg.content}
		history.append(message_dict)

	return history


def generate_ai_response(conversation, provider, history, tools) -> dict:
	"""Generate non-streaming AI response"""
	try:
		response = provider.chat_completion(history, tools=tools, stream=False)

		# Extract response content
		if conversation.ai_provider == "OpenAI":
			content = response["choices"][0]["message"]["content"]
			tool_calls = response["choices"][0]["message"].get("tool_calls", [])
			tokens_used = response["usage"]["total_tokens"]
		else:  # Claude
			content = response["content"][0]["text"] if response["content"] else ""
			tool_calls = []
			tokens_used = response["usage"]["input_tokens"] + response["usage"]["output_tokens"]

			# Handle tool calls if present
		all_tool_results = []
		if tool_calls:
			tool_results = []
			for tool_call in tool_calls:
				if conversation.ai_provider == "OpenAI":
					func_name = tool_call["function"]["name"]
					func_args = json.loads(tool_call["function"]["arguments"])
				else:
					func_name = tool_call["name"]
					func_args = tool_call["input"]

				result = BaseTool.execute_tool(func_name, func_args)
				tool_results.append(result)

			all_tool_results = tool_results

			# Add tool results to history and get final response
			history.append(
				{
					"role": "assistant",
					"content": content,
					"tool_calls": tool_calls,
				}
			)

			for i, result in enumerate(tool_results):
				history.append(
					{
						"role": "tool",
						"content": json.dumps(result),
						"tool_call_id": tool_calls[i].get("id", f"tool_{i}"),
					}
				)

			# Get final response with tool results
			final_response = provider.chat_completion(history, tools=tools, stream=False)
			if conversation.ai_provider == "OpenAI":
				content = final_response["choices"][0]["message"]["content"]
				tokens_used += final_response["usage"]["total_tokens"]
			else:
				content = final_response["content"][0]["text"]
				tokens_used += (
					final_response["usage"]["input_tokens"] + final_response["usage"]["output_tokens"]
				)

		# Save assistant message
		frappe.get_doc(
			{
				"doctype": "Chatbot Message",
				"conversation": conversation.name,
				"role": "assistant",
				"content": content,
				"timestamp": frappe.utils.now(),
				"tokens_used": tokens_used,
				"tool_calls": json.dumps(tool_calls) if tool_calls else None,
				"tool_results": json.dumps(all_tool_results) if all_tool_results else None,
			}
		).insert()

		# Update conversation
		conversation.reload()
		conversation.message_count = frappe.db.count("Chatbot Message", {"conversation": conversation.name})
		conversation.total_tokens += tokens_used
		conversation.updated_at = frappe.utils.now()

		# Auto-generate title from first message if still "New Chat"
		if conversation.title == "New Chat" and conversation.message_count == 2:
			first_message = frappe.get_all(
				"Chatbot Message",
				filters={"conversation": conversation.name, "role": "user"},
				fields=["content"],
				order_by="timestamp asc",
				limit=1,
			)
			if first_message:
				title = first_message[0].content[:50].strip()
				if len(first_message[0].content) > 50:
					title += "..."
				conversation.title = title

		conversation.save(ignore_version=True)
		frappe.db.commit()

		return {
			"success": True,
			"message": content,
			"tokens_used": tokens_used,
		}

	except Exception as e:
		frappe.log_error(f"Error generating response: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def delete_conversation(conversation_id: str) -> dict:
	"""Delete a conversation and its messages"""
	try:
		conversation = frappe.get_doc("Chatbot Conversation", conversation_id)
		if conversation.user != frappe.session.user:
			frappe.throw("Unauthorized access to conversation")

		# Delete all messages
		messages = frappe.get_all("Chatbot Message", filters={"conversation": conversation_id})
		for msg in messages:
			frappe.delete_doc("Chatbot Message", msg.name)

		# Delete conversation
		frappe.delete_doc("Chatbot Conversation", conversation_id)
		frappe.db.commit()

		return {"success": True}
	except Exception as e:
		frappe.log_error(f"Error deleting conversation: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_conversation_title(conversation_id: str, title: str) -> dict:
	"""Update conversation title"""
	try:
		conversation = frappe.get_doc("Chatbot Conversation", conversation_id)
		if conversation.user != frappe.session.user:
			frappe.throw("Unauthorized access to conversation")

		conversation.title = title
		conversation.updated_at = frappe.utils.now()
		conversation.save()
		frappe.db.commit()

		return {"success": True}
	except Exception as e:
		frappe.log_error(f"Error updating title: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_settings() -> dict:
	"""Get chatbot settings"""
	try:
		settings = frappe.get_single("Chatbot Settings")
		return {
			"success": True,
			"settings": {
				"openai_enabled": settings.openai_enabled,
				"claude_enabled": settings.claude_enabled,
				"enable_streaming": settings.enable_streaming if hasattr(settings, "enable_streaming") else 1,
				"tools_enabled": {
					"crm": settings.enable_crm_tools,
					"sales": settings.enable_sales_tools,
					"purchase": settings.enable_purchase_tools,
					"finance": settings.enable_finance_tools,
					"inventory": settings.enable_inventory_tools,
					"operations": getattr(settings, "enable_write_operations", 0),
				},
			},
		}
	except Exception as e:
		frappe.log_error(f"Error getting settings: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}
