# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
AI Provider Integration Module
Handles OpenAI, Claude, and Gemini API integrations with streaming support.

Provider configuration uses the unified Chatbot Settings fields:
  ai_provider, api_key, model, temperature, max_tokens
"""

import json

import frappe
import requests

# Default models per provider
DEFAULT_MODELS = {
	"OpenAI": "gpt-4o",
	"Claude": "claude-sonnet-4-5-20250929",
	"Gemini": "gemini-2.5-flash",
}

# User-friendly error messages for common API errors
RATE_LIMIT_MESSAGE = (
	"The AI service is temporarily unavailable due to rate limiting. "
	"This usually means too many requests were sent in a short period. "
	"Please wait a moment and try again."
)

QUOTA_EXCEEDED_MESSAGE = (
	"Your AI API quota has been exceeded. Please check your API plan "
	"and billing details with your AI provider, or try again later."
)

AUTH_ERROR_MESSAGE = (
	"Authentication failed with the AI provider. Please check that your API key is valid in Chatbot Settings."
)


def classify_api_error(error: requests.exceptions.RequestException) -> str:
	"""Classify an API error and return a user-friendly message.

	Detects rate limit (429), authentication (401/403), and quota errors
	and returns a clear message. Falls back to the original error string
	for other error types.
	"""
	status_code = None
	response_body = ""

	if hasattr(error, "response") and error.response is not None:
		status_code = error.response.status_code
		try:
			response_body = error.response.text or ""
		except Exception:
			pass

	body_lower = response_body.lower()

	# Billing / credit / quota issues — Anthropic returns 400, OpenAI returns 429
	if "credit balance" in body_lower or "billing" in body_lower or "purchase credits" in body_lower:
		return QUOTA_EXCEEDED_MESSAGE

	if status_code == 429:
		if "quota" in body_lower or "exceeded" in body_lower:
			return QUOTA_EXCEEDED_MESSAGE
		return RATE_LIMIT_MESSAGE

	if status_code in (401, 403):
		return AUTH_ERROR_MESSAGE

	return str(error)


class AIProvider:
	"""Base class for AI providers"""

	def __init__(self, settings):
		self.settings = settings

	def chat_completion(self, messages, tools=None, stream=False):
		raise NotImplementedError

	def chat_completion_stream(self, messages, tools=None):
		"""Yield structured streaming events.

		Yields dicts with keys:
			type: "token" | "tool_call" | "finish"
			content: str (for token events)
			tool_call: dict (for tool_call events, contains id, name, arguments)
			finish_reason: str (for finish events)
		"""
		raise NotImplementedError

	def validate_settings(self):
		raise NotImplementedError


class OpenAIProvider(AIProvider):
	"""OpenAI API Integration"""

	def __init__(self, settings):
		super().__init__(settings)
		self.api_key = settings.get("api_key")
		self.model = settings.get("model") or DEFAULT_MODELS["OpenAI"]
		self.temperature = settings.get("temperature") or 0.7
		self.max_tokens = settings.get("max_tokens") or 4000
		self.base_url = "https://api.openai.com/v1"

	def validate_settings(self):
		if not self.api_key:
			frappe.throw("API Key is required for OpenAI")
		return True

	def chat_completion(self, messages, tools=None, stream=False):
		"""OpenAI Chat Completion (non-streaming)"""
		self.validate_settings()

		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}

		payload = {
			"model": self.model,
			"messages": messages,
			"temperature": self.temperature,
			"max_tokens": self.max_tokens,
			"stream": False,
		}

		if tools:
			payload["tools"] = tools
			payload["tool_choice"] = "auto"

		try:
			response = requests.post(
				f"{self.base_url}/chat/completions",
				headers=headers,
				json=payload,
				timeout=120,
			)
			response.raise_for_status()
			return response.json()

		except requests.exceptions.RequestException as e:
			frappe.log_error(f"OpenAI API Error: {e!s}", "AI Chatbot")
			frappe.throw(f"OpenAI API Error: {classify_api_error(e)}")

	def chat_completion_stream(self, messages, tools=None):
		"""Yield structured streaming events from OpenAI.

		Handles both text content and tool calls during streaming.
		"""
		self.validate_settings()

		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}

		payload = {
			"model": self.model,
			"messages": messages,
			"temperature": self.temperature,
			"max_tokens": self.max_tokens,
			"stream": True,
			"stream_options": {"include_usage": True},
		}

		if tools:
			payload["tools"] = tools
			payload["tool_choice"] = "auto"

		try:
			response = requests.post(
				f"{self.base_url}/chat/completions",
				headers=headers,
				json=payload,
				stream=True,
				timeout=120,
			)
			response.raise_for_status()

			# Accumulate tool call chunks
			tool_calls_acc = {}

			for line in response.iter_lines():
				if not line:
					continue
				line = line.decode("utf-8")
				if not line.startswith("data: "):
					continue
				data = line[6:]
				if data == "[DONE]":
					break

				try:
					chunk = json.loads(data)
				except json.JSONDecodeError:
					continue

				# Usage data arrives in the final chunk (choices may be empty)
				if chunk.get("usage"):
					usage = chunk["usage"]
					yield {
						"type": "usage",
						"prompt_tokens": usage.get("prompt_tokens", 0),
						"completion_tokens": usage.get("completion_tokens", 0),
					}

				choice = chunk.get("choices", [{}])[0]
				delta = choice.get("delta", {})
				finish_reason = choice.get("finish_reason")

				# Text content
				if delta.get("content"):
					yield {"type": "token", "content": delta["content"]}

				# Tool call chunks (streamed incrementally)
				if delta.get("tool_calls"):
					for i, tc in enumerate(delta["tool_calls"]):
						idx = tc.get("index", i)
						if idx not in tool_calls_acc:
							tool_calls_acc[idx] = {
								"id": tc.get("id", ""),
								"name": "",
								"arguments": "",
							}
						if tc.get("id"):
							tool_calls_acc[idx]["id"] = tc["id"]
						if tc.get("function", {}).get("name"):
							tool_calls_acc[idx]["name"] = tc["function"]["name"]
						if tc.get("function", {}).get("arguments"):
							tool_calls_acc[idx]["arguments"] += tc["function"]["arguments"]

				# Stream finished
				if finish_reason:
					# Emit accumulated tool calls
					if finish_reason in ("tool_calls", "stop") and tool_calls_acc:
						for _idx, tc_data in sorted(tool_calls_acc.items()):
							try:
								args = json.loads(tc_data["arguments"])
							except json.JSONDecodeError:
								args = {}
							yield {
								"type": "tool_call",
								"tool_call": {
									"id": tc_data["id"],
									"name": tc_data["name"],
									"arguments": args,
								},
							}

					yield {"type": "finish", "finish_reason": finish_reason}

		except requests.exceptions.RequestException as e:
			frappe.log_error(f"OpenAI Streaming Error: {e!s}", "AI Chatbot")
			yield {"type": "error", "content": classify_api_error(e)}


class GeminiProvider(OpenAIProvider):
	"""Google Gemini provider via OpenAI-compatible endpoint.

	Gemini exposes an OpenAI-compatible /chat/completions API at
	generativelanguage.googleapis.com, so we extend OpenAIProvider
	and only override the base URL and defaults.
	"""

	def __init__(self, settings):
		# Skip OpenAIProvider.__init__ — set fields directly
		AIProvider.__init__(self, settings)
		self.api_key = settings.get("api_key")
		self.model = settings.get("model") or DEFAULT_MODELS["Gemini"]
		self.temperature = settings.get("temperature") or 1.0
		self.max_tokens = settings.get("max_tokens") or 8192
		self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai"

	def validate_settings(self):
		if not self.api_key:
			frappe.throw("API Key is required for Gemini")
		return True


class ClaudeProvider(AIProvider):
	"""Anthropic Claude API Integration"""

	def __init__(self, settings):
		super().__init__(settings)
		self.api_key = settings.get("api_key")
		self.model = settings.get("model") or DEFAULT_MODELS["Claude"]
		self.temperature = settings.get("temperature") or 0.7
		self.max_tokens = settings.get("max_tokens") or 4000
		self.base_url = "https://api.anthropic.com/v1"
		self.api_version = "2023-06-01"

	def validate_settings(self):
		if not self.api_key:
			frappe.throw("API Key is required for Claude")
		return True

	def chat_completion(self, messages, tools=None, stream=False):
		"""Claude Messages API (non-streaming)"""
		self.validate_settings()

		headers = {
			"x-api-key": self.api_key,
			"anthropic-version": self.api_version,
			"Content-Type": "application/json",
		}

		claude_messages = self._convert_messages_to_claude(messages)
		system_message = self._extract_system_message(messages)

		payload = {
			"model": self.model,
			"messages": claude_messages,
			"max_tokens": self.max_tokens,
			"temperature": self.temperature,
			"stream": False,
		}

		if system_message:
			payload["system"] = system_message

		if tools:
			payload["tools"] = self._convert_tools_to_claude(tools)

		try:
			response = requests.post(
				f"{self.base_url}/messages",
				headers=headers,
				json=payload,
				timeout=120,
			)
			response.raise_for_status()
			return response.json()

		except requests.exceptions.RequestException as e:
			frappe.log_error(f"Claude API Error: {e!s}", "AI Chatbot")
			frappe.throw(f"Claude API Error: {classify_api_error(e)}")

	def chat_completion_stream(self, messages, tools=None):
		"""Yield structured streaming events from Claude.

		Claude SSE event types:
			message_start, content_block_start, content_block_delta,
			content_block_stop, message_delta, message_stop
		"""
		self.validate_settings()

		headers = {
			"x-api-key": self.api_key,
			"anthropic-version": self.api_version,
			"Content-Type": "application/json",
		}

		claude_messages = self._convert_messages_to_claude(messages)
		system_message = self._extract_system_message(messages)

		payload = {
			"model": self.model,
			"messages": claude_messages,
			"max_tokens": self.max_tokens,
			"temperature": self.temperature,
			"stream": True,
		}

		if system_message:
			payload["system"] = system_message

		if tools:
			payload["tools"] = self._convert_tools_to_claude(tools)

		try:
			response = requests.post(
				f"{self.base_url}/messages",
				headers=headers,
				json=payload,
				stream=True,
				timeout=120,
			)
			response.raise_for_status()

			# Track content blocks for tool calls
			current_block_type = None
			current_tool_name = None
			current_tool_id = None
			tool_input_json = ""

			# Accumulate usage across message_start and message_delta
			usage_prompt = 0
			usage_completion = 0

			for line in response.iter_lines():
				if not line:
					continue
				line = line.decode("utf-8")
				if not line.startswith("data: "):
					continue
				data = line[6:]

				try:
					event = json.loads(data)
				except json.JSONDecodeError:
					continue

				event_type = event.get("type")

				if event_type == "message_start":
					# message_start contains input token count
					msg_usage = event.get("message", {}).get("usage", {})
					usage_prompt = msg_usage.get("input_tokens", 0)

				elif event_type == "content_block_start":
					block = event.get("content_block", {})
					current_block_type = block.get("type")
					if current_block_type == "tool_use":
						current_tool_name = block.get("name", "")
						current_tool_id = block.get("id", "")
						tool_input_json = ""

				elif event_type == "content_block_delta":
					delta = event.get("delta", {})
					delta_type = delta.get("type")

					if delta_type == "text_delta":
						yield {"type": "token", "content": delta.get("text", "")}

					elif delta_type == "input_json_delta":
						tool_input_json += delta.get("partial_json", "")

				elif event_type == "content_block_stop":
					if current_block_type == "tool_use" and current_tool_name:
						try:
							args = json.loads(tool_input_json) if tool_input_json else {}
						except json.JSONDecodeError:
							args = {}
						yield {
							"type": "tool_call",
							"tool_call": {
								"id": current_tool_id,
								"name": current_tool_name,
								"arguments": args,
							},
						}
					current_block_type = None
					current_tool_name = None
					current_tool_id = None
					tool_input_json = ""

				elif event_type == "message_delta":
					# message_delta contains output token count
					delta_usage = event.get("usage", {})
					usage_completion = delta_usage.get("output_tokens", 0)

					stop_reason = event.get("delta", {}).get("stop_reason")
					if stop_reason:
						yield {
							"type": "usage",
							"prompt_tokens": usage_prompt,
							"completion_tokens": usage_completion,
						}
						yield {"type": "finish", "finish_reason": stop_reason}

				elif event_type == "message_stop":
					pass  # Already handled via message_delta

		except requests.exceptions.RequestException as e:
			frappe.log_error(f"Claude Streaming Error: {e!s}", "AI Chatbot")
			yield {"type": "error", "content": classify_api_error(e)}

	def _convert_messages_to_claude(self, messages):
		"""Convert OpenAI message format to Claude format"""
		claude_messages = []
		for msg in messages:
			if msg["role"] == "system":
				continue
			if msg["role"] == "tool":
				# Claude expects tool results as user messages with tool_result content
				claude_messages.append(
					{
						"role": "user",
						"content": [
							{
								"type": "tool_result",
								"tool_use_id": msg.get("tool_call_id", ""),
								"content": msg.get("content", ""),
							}
						],
					}
				)
			elif msg["role"] == "assistant" and msg.get("tool_calls"):
				# Convert assistant tool_calls to Claude format
				content = []
				if msg.get("content"):
					content.append({"type": "text", "text": msg["content"]})
				for tc in msg["tool_calls"]:
					func = tc.get("function", tc)
					try:
						args = (
							json.loads(func["arguments"])
							if isinstance(func.get("arguments"), str)
							else func.get("arguments", {})
						)
					except json.JSONDecodeError:
						args = {}
					content.append(
						{
							"type": "tool_use",
							"id": tc.get("id", ""),
							"name": func.get("name", ""),
							"input": args,
						}
					)
				claude_messages.append({"role": "assistant", "content": content})
			else:
				content = msg.get("content", "")
				if isinstance(content, list):
					# Multi-modal content (vision) — convert from OpenAI to Claude format
					claude_content = []
					for part in content:
						if part.get("type") == "text":
							claude_content.append({"type": "text", "text": part["text"]})
						elif part.get("type") == "image_url":
							# Extract base64 from data URL: "data:image/jpeg;base64,/9j/..."
							data_url = part["image_url"]["url"]
							header, b64_data = data_url.split(",", 1)
							media_type = header.split(":")[1].split(";")[0]
							claude_content.append(
								{
									"type": "image",
									"source": {
										"type": "base64",
										"media_type": media_type,
										"data": b64_data,
									},
								}
							)
					claude_messages.append({"role": "user", "content": claude_content})
				else:
					claude_messages.append({"role": msg["role"], "content": content})
		return claude_messages

	def _extract_system_message(self, messages):
		"""Extract system message from messages list"""
		for msg in messages:
			if msg["role"] == "system":
				return msg["content"]
		return ""

	def _convert_tools_to_claude(self, tools):
		"""Convert OpenAI tool format to Claude format"""
		claude_tools = []
		for tool in tools:
			if tool.get("type") == "function":
				func = tool["function"]
				claude_tools.append(
					{
						"name": func["name"],
						"description": func.get("description", ""),
						"input_schema": func.get("parameters", {}),
					}
				)
		return claude_tools


def _resolve_settings(provider_name: str) -> dict:
	"""Build a unified settings dict for the given provider."""
	settings = frappe.get_single("Chatbot Settings")
	sd = settings.as_dict()

	api_key = settings.get_password("api_key") if sd.get("api_key") else None

	return {
		"api_key": api_key,
		"model": sd.get("model") or DEFAULT_MODELS.get(provider_name),
		"temperature": sd.get("temperature") or 0.7,
		"max_tokens": sd.get("max_tokens") or 4000,
	}


def get_ai_provider(provider_name: str) -> AIProvider:
	"""Factory function to get AI provider instance."""
	resolved = _resolve_settings(provider_name)

	if provider_name == "OpenAI":
		return OpenAIProvider(resolved)
	elif provider_name == "Claude":
		return ClaudeProvider(resolved)
	elif provider_name == "Gemini":
		return GeminiProvider(resolved)
	else:
		frappe.throw(f"Unknown AI provider: {provider_name}")
