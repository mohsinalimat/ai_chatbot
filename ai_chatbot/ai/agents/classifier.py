# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Query Complexity Classifier

Determines whether a user query should be handled by the standard single-pass
tool-calling flow (simple) or the multi-agent orchestration pipeline (complex).
"""

from __future__ import annotations

import json
import re

import frappe

from ai_chatbot.ai.agents.prompts import get_classifier_prompt

# Keywords that strongly signal multi-step analysis
COMPLEX_SIGNALS = re.compile(
	r"\b("
	r"compare|comparison|versus|vs\.?|"
	r"analyze|analyse|analysis|"
	r"comprehensive|complete|full|detailed|"
	r"financial health|health report|"
	r"root cause|why is|what.s causing|"
	r"trend.* and .*(recommend|suggest|action)|"
	r"across all|across .* regions|across .* departments|"
	r"forecast.* and|budget.* and|"
	r"top \d+.* and .*(suggest|recommend|pattern|insight)|"
	r"evaluate|assessment|breakdown .* and|"
	r"profitability .* and .* (cost|margin|revenue)"
	r")\b",
	re.IGNORECASE,
)

# Very short queries are almost always simple
MIN_COMPLEX_WORD_COUNT = 8


def classify_query(
	provider,
	user_message: str,
	history: list[dict],
	tools: list[dict],
) -> bool:
	"""Classify whether a query needs multi-agent orchestration.

	Uses a two-stage approach:
	1. Fast heuristic pre-filter for obvious simple/complex cases
	2. LLM-based classification for ambiguous cases

	Args:
		provider: The AI provider instance.
		user_message: The user's latest message text.
		history: Full conversation history.
		tools: Available tool schemas.

	Returns:
		True if the query is complex and should use orchestration.
	"""
	if not user_message or not user_message.strip():
		return False

	message = user_message.strip()

	# Stage 1: Heuristic pre-filter
	word_count = len(message.split())

	# Very short messages are simple
	if word_count < MIN_COMPLEX_WORD_COUNT:
		return False

	# Strong complex signals — skip LLM classification
	if COMPLEX_SIGNALS.search(message):
		return True

	# Stage 2: LLM classification for ambiguous cases
	return _llm_classify(provider, message, history)


def _llm_classify(provider, user_message: str, history: list[dict]) -> bool:
	"""Use the LLM to classify query complexity.

	Makes a lightweight call with minimal context. Returns False on any error
	(safe fallback to simple path).
	"""
	try:
		# Build a short context: classifier prompt + recent conversation + user query
		messages = [{"role": "system", "content": get_classifier_prompt()}]

		# Include last 2 assistant messages for conversational context
		recent = [m for m in history if m.get("role") in ("user", "assistant")][-4:]
		for msg in recent[:-1]:  # Exclude the current user message (added below)
			content = msg.get("content", "")
			if isinstance(content, list):
				content = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
			if content:
				messages.append({"role": msg["role"], "content": content[:200]})

		messages.append({"role": "user", "content": user_message})

		# Call LLM without tools — classification only
		response = provider.chat_completion(messages, tools=None, stream=False)

		# Extract the classification
		return _parse_classification(provider, response)

	except Exception as e:
		frappe.log_error(f"Agent classifier error: {e!s}", "AI Chatbot Agent")
		return False


def _parse_classification(provider, response: dict) -> bool:
	"""Parse the LLM classification response.

	Handles both OpenAI/Gemini and Claude response formats.
	"""
	try:
		# Extract text content based on provider format
		if "choices" in response:
			# OpenAI / Gemini format
			content = response["choices"][0]["message"].get("content", "")
		else:
			# Claude format
			content = ""
			for block in response.get("content", []):
				if block.get("type") == "text":
					content += block.get("text", "")

		if not content:
			return False

		# Try to parse JSON from the response (may be wrapped in ```json ... ```)
		json_match = re.search(r"\{[^}]+\}", content)
		if json_match:
			result = json.loads(json_match.group())
			return result.get("complexity") == "complex"

		# Fallback: look for the word "complex" in the response
		return '"complex"' in content.lower()

	except (json.JSONDecodeError, KeyError, IndexError, TypeError):
		return False
