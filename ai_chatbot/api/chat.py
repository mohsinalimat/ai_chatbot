# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Chat API Module
RESTful API endpoints for AI chatbot
"""

import json

import frappe

from ai_chatbot.core.prompts import build_system_prompt
from ai_chatbot.core.token_optimizer import optimize_history
from ai_chatbot.core.token_tracker import track_token_usage
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
			fields=["name", "role", "content", "timestamp", "tokens_used", "tool_calls", "tool_results", "attachments"],
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
			if msg.get("attachments"):
				try:
					msg["attachments"] = (
						json.loads(msg["attachments"])
						if isinstance(msg["attachments"], str)
						else msg["attachments"]
					)
				except (json.JSONDecodeError, TypeError):
					msg["attachments"] = None

		return {
			"success": True,
			"messages": messages,
		}
	except Exception as e:
		frappe.log_error(f"Error getting messages: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_message(conversation_id: str, message: str, stream: bool = False, attachments: str = None) -> dict:
	"""Send a message and get AI response.

	When stream=True, delegates to the streaming API which delivers tokens
	via frappe.publish_realtime. The HTTP response returns immediately with
	the stream_id. When stream=False, returns the complete response.

	Args:
		conversation_id: The conversation document name.
		message: The user's message text.
		stream: Whether to use streaming mode.
		attachments: Optional JSON string of file attachment metadata.
	"""
	try:
		if stream:
			from ai_chatbot.api.streaming import send_message_streaming

			return send_message_streaming(conversation_id, message, attachments=attachments)

		# Validate conversation
		conversation = frappe.get_doc("Chatbot Conversation", conversation_id)
		if conversation.user != frappe.session.user:
			frappe.throw("Unauthorized access to conversation")

		# Save user message
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

		# Get conversation history
		history = get_conversation_history(conversation_id)

		# Prepend system prompt
		system_prompt = build_system_prompt()
		history = [{"role": "system", "content": system_prompt}, *history]

		# Optimize history (trim + compress tool results)
		history = optimize_history(history)

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
	"""Get conversation history in AI format.

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
		# Check if user message has image attachments — build vision content
		if msg.role == "user" and msg.attachments:
			try:
				atts = json.loads(msg.attachments) if isinstance(msg.attachments, str) else msg.attachments
			except (json.JSONDecodeError, TypeError):
				atts = None

			if atts and any(a.get("is_image") for a in atts):
				from ai_chatbot.api.files import build_vision_content

				content = build_vision_content(msg.content or "", atts)
				history.append({"role": msg.role, "content": content})
				continue

		message_dict = {"role": msg.role, "content": msg.content}
		history.append(message_dict)

	return history


def _is_openai_format(provider_name: str) -> bool:
	"""Return True if the provider uses OpenAI-compatible response format."""
	return provider_name in ("OpenAI", "Gemini")


def _extract_response(provider_name: str, response: dict) -> tuple:
	"""Extract content, tool_calls, prompt_tokens, completion_tokens from a provider response."""
	if _is_openai_format(provider_name):
		msg = response["choices"][0]["message"]
		content = msg.get("content") or ""
		tool_calls = msg.get("tool_calls", [])
		usage = response.get("usage", {})
		prompt_tokens = usage.get("prompt_tokens", 0)
		completion_tokens = usage.get("completion_tokens", 0)
	else:  # Claude
		content = ""
		tool_calls = []
		for block in response.get("content", []):
			if block.get("type") == "text":
				content += block.get("text", "")
			elif block.get("type") == "tool_use":
				tool_calls.append(block)
		usage = response.get("usage", {})
		prompt_tokens = usage.get("input_tokens", 0)
		completion_tokens = usage.get("output_tokens", 0)

	return content, tool_calls, prompt_tokens, completion_tokens


def _extract_tool_info(provider_name: str, tool_call: dict) -> tuple:
	"""Extract (func_name, func_args) from a tool_call dict."""
	if _is_openai_format(provider_name):
		func_name = tool_call["function"]["name"]
		func_args = json.loads(tool_call["function"]["arguments"])
	else:  # Claude
		func_name = tool_call["name"]
		func_args = tool_call.get("input", {})
	return func_name, func_args


def generate_ai_response(conversation, provider, history, tools) -> dict:
	"""Generate non-streaming AI response with provider-agnostic parsing."""
	try:
		response = provider.chat_completion(history, tools=tools, stream=False)
		ai_provider = conversation.ai_provider

		# Extract response content
		content, tool_calls, prompt_tokens, completion_tokens = _extract_response(ai_provider, response)
		tokens_used = prompt_tokens + completion_tokens

		# Handle tool calls if present
		all_tool_results = []
		if tool_calls:
			tool_results = []
			for tool_call in tool_calls:
				func_name, func_args = _extract_tool_info(ai_provider, tool_call)
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
			final_content, _, final_prompt, final_completion = _extract_response(ai_provider, final_response)
			content = final_content
			prompt_tokens += final_prompt
			completion_tokens += final_completion
			tokens_used = prompt_tokens + completion_tokens

		# Track token usage
		track_token_usage(
			provider=ai_provider,
			model=provider.model,
			prompt_tokens=prompt_tokens,
			completion_tokens=completion_tokens,
			conversation_id=conversation.name,
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
	"""Get chatbot settings and current user info"""
	try:
		settings = frappe.get_single("Chatbot Settings")

		# Get current user's fullname and avatar
		from frappe.utils.user import get_fullname_and_avatar

		user_info = get_fullname_and_avatar(frappe.session.user)

		# Unified provider (new) or legacy dual-provider flags
		ai_provider = getattr(settings, "ai_provider", None)

		return {
			"success": True,
			"settings": {
				"ai_provider": ai_provider or "OpenAI",
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
			"user": {
				"fullname": user_info.get("fullname"),
				"avatar": user_info.get("avatar"),
			},
		}
	except Exception as e:
		frappe.log_error(f"Error getting settings: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def search_conversations(query: str, limit: int = 20) -> dict:
	"""Search conversations by title or message content.

	Searches the current user's conversations where the title matches
	or any message content matches the query string.

	Args:
		query: The search term.
		limit: Maximum number of results to return.

	Returns:
		dict with success and conversations list.
	"""
	try:
		query = query.strip()
		if not query or len(query) < 2:
			return {"success": True, "conversations": []}

		user = frappe.session.user
		like_pattern = f"%{query}%"

		# Search by conversation title
		title_matches = frappe.get_all(
			"Chatbot Conversation",
			filters={"user": user, "title": ["like", like_pattern]},
			fields=["name", "title", "ai_provider", "status", "created_at", "updated_at", "message_count"],
			order_by="updated_at desc",
			limit=limit,
		)

		# Search by message content (get distinct conversation IDs)
		message_conv_ids = frappe.get_all(
			"Chatbot Message",
			filters={"content": ["like", like_pattern]},
			fields=["distinct conversation as name"],
			limit=limit * 2,
		)
		message_conv_names = [m.name for m in message_conv_ids]

		# Filter to user's conversations and fetch details
		content_matches = []
		if message_conv_names:
			content_matches = frappe.get_all(
				"Chatbot Conversation",
				filters={"user": user, "name": ["in", message_conv_names]},
				fields=["name", "title", "ai_provider", "status", "created_at", "updated_at", "message_count"],
				order_by="updated_at desc",
				limit=limit,
			)

		# Deduplicate (title matches take priority)
		seen = {c.name for c in title_matches}
		for c in content_matches:
			if c.name not in seen:
				title_matches.append(c)
				seen.add(c.name)

		# Sort combined results by updated_at desc and limit
		title_matches.sort(key=lambda c: c.get("updated_at") or "", reverse=True)

		return {
			"success": True,
			"conversations": title_matches[:limit],
		}
	except Exception as e:
		frappe.log_error(f"Search conversations error: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_mention_values(mention_type: str, search_term: str = "", company: str = None) -> dict:
	"""Return values for @mention autocomplete in chat input.

	Args:
		mention_type: One of: company, period, cost_center, department, warehouse,
			customer, item, accounting_dimension
		search_term: Filter string
		company: Company context (defaults to user default)

	Returns:
		dict with success and values list
	"""
	try:
		if not company:
			company = frappe.defaults.get_user_default("Company")

		if mention_type == "company":
			filters = {}
			if search_term:
				filters["name"] = ["like", f"%{search_term}%"]
			companies = frappe.get_all(
				"Company",
				filters=filters,
				pluck="name",
				limit_page_length=50,
				order_by="name asc",
			)
			# Put the user's default company first
			if company and company in companies:
				companies.remove(company)
				companies.insert(0, company)
			return {"success": True, "values": companies}

		if mention_type == "period":
			return {"success": True, "values": _get_period_presets(company)}

		# Searchable DocType mentions
		doctype_map = {
			"cost_center": "Cost Center",
			"department": "Department",
			"warehouse": "Warehouse",
			"customer": "Customer",
			"item": "Item",
		}

		if mention_type in doctype_map:
			doctype = doctype_map[mention_type]
			filters = {}
			if search_term:
				filters["name"] = ["like", f"%{search_term}%"]
			# Company filter for company-scoped DocTypes
			if mention_type in ("cost_center", "department", "warehouse") and company:
				filters["company"] = company

			values = frappe.get_all(
				doctype,
				filters=filters,
				pluck="name",
				limit_page_length=20,
				order_by="name asc",
			)
			return {"success": True, "values": values}

		if mention_type == "accounting_dimension":
			return {"success": True, "values": _get_accounting_dimensions(company, search_term)}

		return {"success": False, "error": f"Unknown mention type: {mention_type}"}

	except Exception as e:
		frappe.log_error(f"Mention values error: {e!s}", "AI Chatbot")
		return {"success": False, "error": str(e)}


def _get_period_presets(company: str = None) -> list[dict]:
	"""Return date range presets for @period mention."""
	from datetime import timedelta

	today = frappe.utils.today()
	today_date = frappe.utils.getdate(today)

	# This Week (Monday to Sunday)
	monday = today_date - timedelta(days=today_date.weekday())
	sunday = monday + timedelta(days=6)

	# This Month
	month_start = today_date.replace(day=1)
	if today_date.month == 12:
		month_end = today_date.replace(year=today_date.year + 1, month=1, day=1) - timedelta(days=1)
	else:
		month_end = today_date.replace(month=today_date.month + 1, day=1) - timedelta(days=1)

	# Last Month
	last_month_end = month_start - timedelta(days=1)
	last_month_start = last_month_end.replace(day=1)

	presets = [
		{"label": "This Week", "value": f"{monday} to {sunday}"},
		{"label": "This Month", "value": f"{month_start} to {month_end}"},
		{"label": "Last Month", "value": f"{last_month_start} to {last_month_end}"},
	]

	# Try to get fiscal year info
	try:
		from erpnext.accounts.utils import get_fiscal_year

		fy = get_fiscal_year(today, company=company)
		if fy:
			fy_start, fy_end = str(fy[1]), str(fy[2])

			# This Quarter
			quarter_month = ((today_date.month - frappe.utils.getdate(fy_start).month) // 3) * 3
			q_start_month = frappe.utils.getdate(fy_start).month + quarter_month
			q_start_year = today_date.year if q_start_month <= 12 else today_date.year + 1
			if q_start_month > 12:
				q_start_month -= 12
			q_start = today_date.replace(year=q_start_year, month=q_start_month, day=1)
			q_end_month = q_start_month + 2
			q_end_year = q_start_year
			if q_end_month > 12:
				q_end_month -= 12
				q_end_year += 1
			if q_end_month == 12:
				q_end = today_date.replace(year=q_end_year, month=12, day=31)
			else:
				q_end = today_date.replace(year=q_end_year, month=q_end_month + 1, day=1) - timedelta(days=1)

			presets.append({"label": "This Quarter", "value": f"{q_start} to {q_end}"})
			presets.append({"label": "This FY", "value": f"{fy_start} to {fy_end}"})

			# Last FY
			try:
				prev_fy_date = frappe.utils.getdate(fy_start) - timedelta(days=1)
				prev_fy = get_fiscal_year(str(prev_fy_date), company=company)
				if prev_fy:
					presets.append({"label": "Last FY", "value": f"{prev_fy[1]} to {prev_fy[2]}"})
			except Exception:
				pass
	except Exception:
		pass

	return presets


def _get_accounting_dimensions(company: str = None, search_term: str = "") -> list[dict]:
	"""Return available accounting dimensions and their values.

	Uses frappe.get_all("Accounting Dimension") to list configured dimensions,
	then queries each dimension's document_type for its values.
	"""
	try:
		# Get accounting dimension records directly from the DocType
		dim_filters = {"disabled": 0}
		if search_term:
			dim_filters["label"] = ["like", f"%{search_term}%"]

		dimensions = frappe.get_all(
			"Accounting Dimension",
			filters=dim_filters,
			fields=["name", "label", "document_type", "disabled"],
			order_by="label asc",
		)

		results = []
		for dim in dimensions:
			doc_type = dim.get("document_type") or dim.get("name")
			label = dim.get("label") or doc_type

			# Get values for this dimension's document type
			try:
				value_filters = {}
				if company and frappe.get_meta(doc_type).has_field("company"):
					value_filters["company"] = company

				values = frappe.get_all(
					doc_type,
					filters=value_filters,
					pluck="name",
					limit_page_length=20,
					order_by="name asc",
				)
			except Exception:
				values = []

			results.append({
				"label": label,
				"description": f"{doc_type} ({len(values)} values)",
				"values": values,
			})
		return results
	except Exception as e:
		frappe.log_error(f"Error fetching accounting dimensions: {e}")
		return []
