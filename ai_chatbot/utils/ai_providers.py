"""
AI Provider Integration Module
Handles OpenAI and Claude API integrations with streaming support
"""

import json

import frappe
import requests


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
		self.api_key = settings.get("openai_api_key")
		self.model = settings.get("openai_model", "gpt-4o")
		self.temperature = settings.get("openai_temperature", 0.7)
		self.max_tokens = settings.get("openai_max_tokens", 4000)
		self.base_url = "https://api.openai.com/v1"

	def validate_settings(self):
		if not self.api_key:
			frappe.throw("OpenAI API Key is required")
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
			frappe.throw(f"OpenAI API Error: {e!s}")

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

				choice = chunk.get("choices", [{}])[0]
				delta = choice.get("delta", {})
				finish_reason = choice.get("finish_reason")

				# Text content
				if delta.get("content"):
					yield {"type": "token", "content": delta["content"]}

				# Tool call chunks (streamed incrementally)
				if delta.get("tool_calls"):
					for tc in delta["tool_calls"]:
						idx = tc["index"]
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
					if finish_reason == "tool_calls" and tool_calls_acc:
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
			yield {"type": "error", "content": str(e)}


class ClaudeProvider(AIProvider):
	"""Anthropic Claude API Integration"""

	def __init__(self, settings):
		super().__init__(settings)
		self.api_key = settings.get("claude_api_key")
		self.model = settings.get("claude_model", "claude-sonnet-4-5-20250929")
		self.temperature = settings.get("claude_temperature", 0.7)
		self.max_tokens = settings.get("claude_max_tokens", 4000)
		self.base_url = "https://api.anthropic.com/v1"
		self.api_version = "2023-06-01"

	def validate_settings(self):
		if not self.api_key:
			frappe.throw("Claude API Key is required")
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
			frappe.throw(f"Claude API Error: {e!s}")

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

				if event_type == "content_block_start":
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
					stop_reason = event.get("delta", {}).get("stop_reason")
					if stop_reason:
						yield {"type": "finish", "finish_reason": stop_reason}

				elif event_type == "message_stop":
					pass  # Already handled via message_delta

		except requests.exceptions.RequestException as e:
			frappe.log_error(f"Claude Streaming Error: {e!s}", "AI Chatbot")
			yield {"type": "error", "content": str(e)}

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
							claude_content.append({
								"type": "image",
								"source": {
									"type": "base64",
									"media_type": media_type,
									"data": b64_data,
								},
							})
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


def get_ai_provider(provider_name: str):
	"""Factory function to get AI provider instance"""
	settings = frappe.get_single("Chatbot Settings")

	if provider_name == "OpenAI":
		if not settings.openai_enabled:
			frappe.throw("OpenAI is not enabled in settings")
		return OpenAIProvider(settings.as_dict())
	elif provider_name == "Claude":
		if not settings.claude_enabled:
			frappe.throw("Claude is not enabled in settings")
		return ClaudeProvider(settings.as_dict())
	else:
		frappe.throw(f"Unknown AI provider: {provider_name}")
