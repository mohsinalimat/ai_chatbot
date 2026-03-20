# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Token Usage Tracking Module

Records per-request token usage and estimated cost into the
Chatbot Token Usage DocType for analytics and budgeting.
"""

import frappe

# Pricing per 1M tokens: (input, output) in USD
MODEL_PRICING = {
	# OpenAI
	"gpt-4o": (2.50, 10.00),
	"gpt-4o-mini": (0.15, 0.60),
	"gpt-4-turbo": (10.00, 30.00),
	"gpt-3.5-turbo": (0.50, 1.50),
	# Claude
	"claude-opus-4-5-20251101": (15.00, 75.00),
	"claude-sonnet-4-5-20250929": (3.00, 15.00),
	"claude-haiku-4-5-20251001": (0.80, 4.00),
	# Gemini
	"gemini-2.5-flash": (0.15, 0.60),
	"gemini-2.5-pro": (1.25, 10.00),
	"gemini-2.5-flash-lite": (0.075, 0.30),
}


def _resolve_model_pricing(model: str) -> tuple[float, float] | None:
	"""Resolve pricing for a model, using prefix-match fallback.

	Exact match is tried first. If it fails, the longest MODEL_PRICING
	key that is a prefix of the model string is used. This handles
	versioned model names like ``gemini-2.5-flash-preview-04-17``
	matching the ``gemini-2.5-flash`` pricing entry.

	Returns:
		(input_rate, output_rate) per 1M tokens, or None.
	"""
	pricing = MODEL_PRICING.get(model)
	if pricing:
		return pricing

	# Prefix-match fallback — pick the longest matching key
	best_key = ""
	for key in MODEL_PRICING:
		if model.startswith(key) and len(key) > len(best_key):
			best_key = key
	if best_key:
		return MODEL_PRICING[best_key]

	return None


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
	"""Estimate cost in USD for the given token counts.

	Uses MODEL_PRICING lookup with prefix-match fallback.
	Returns 0.0 for unknown models.
	"""
	pricing = _resolve_model_pricing(model)
	if not pricing:
		return 0.0

	input_rate, output_rate = pricing
	cost = (prompt_tokens * input_rate / 1_000_000) + (completion_tokens * output_rate / 1_000_000)
	return round(cost, 6)


def track_token_usage(
	provider: str,
	model: str,
	prompt_tokens: int,
	completion_tokens: int,
	user: str | None = None,
	conversation_id: str | None = None,
):
	"""Record token usage for cost tracking.

	Creates a Chatbot Token Usage document. Runs silently — errors are
	logged but never raised to avoid disrupting chat flow.
	"""
	try:
		cost = estimate_cost(model, prompt_tokens, completion_tokens)
		frappe.get_doc(
			{
				"doctype": "Chatbot Token Usage",
				"user": user or frappe.session.user,
				"conversation": conversation_id,
				"provider": provider,
				"model": model,
				"prompt_tokens": prompt_tokens,
				"completion_tokens": completion_tokens,
				"total_tokens": prompt_tokens + completion_tokens,
				"estimated_cost": cost,
				"date": frappe.utils.today(),
			}
		).insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Token tracking error: {e!s}", "AI Chatbot")
