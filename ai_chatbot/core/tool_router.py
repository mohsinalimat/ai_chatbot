# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Tool Router for AI Chatbot

Phase 12A — deterministic keyword-based tool routing (5-15 tools per request).
Phase 14A — query-type-aware filtering, routing context hints for the system
             prompt, write-request awareness, ambiguity handling, and complexity
             classification for smarter LLM tool selection.

Routes user queries to the relevant subset of tools instead of sending
all ~58 tool schemas (~8K-12K tokens) on every request.  Uses the
deterministic intent classifier (keyword-based, no LLM calls) to select
5-15 tools per request, saving ~6K-10K tokens.

Entry point: ``route_tools(user_message, conversation_history)``
"""

from __future__ import annotations

import dataclasses

from ai_chatbot.core.intent import IntentResult, classify_intent
from ai_chatbot.core.logger import log_debug, log_info, log_warning

# ── ToolRoutingResult ───────────────────────────────────────────────


@dataclasses.dataclass(frozen=True, slots=True)
class ToolRoutingResult:
	"""Result of tool routing."""

	tools: list[dict]
	"""Filtered tool schemas in OpenAI function calling format."""

	intent: IntentResult
	"""The classified intent used for routing."""

	is_fallback: bool
	"""True if the full tool set was sent (no confident category match)."""

	tool_count: int
	"""Number of tools in the filtered set."""

	categories_matched: tuple[str, ...]
	"""Which categories were included in the filtered set."""

	# Phase 14A — routing context for prompt injection
	routing_hint: str = ""
	"""Short natural-language hint injected into the system prompt to guide
	the LLM's tool selection.  E.g. "Query is about sales analytics (selling).
	Consider using get_sales_analytics or get_sales_by_territory."
	Empty string when no hint is needed (conversational or fallback)."""


# ── Configuration ───────────────────────────────────────────────────

# Tool names that are always included regardless of intent,
# because they manage session state and are broadly applicable.
ALWAYS_INCLUDE_TOOLS: frozenset[str] = frozenset(
	{
		"set_include_subsidiaries",
		"set_target_currency",
	}
)

# When a primary category is matched, adjacent categories are also
# included to give the LLM useful related options.
CATEGORY_ADJACENCY: dict[str, list[str]] = {
	"selling": ["operations"],
	"buying": ["operations"],
	"crm": ["operations"],
	"inventory": [],
	"finance": ["operations"],
	"hrms": [],
	"idp": ["operations"],
	"predictive": ["selling", "finance"],
	"operations": [],
}

# Minimum confidence from intent classification to trigger routing
# (below this threshold, fall back to all tools).
CONFIDENCE_THRESHOLD = 0.3


# ── Public API ──────────────────────────────────────────────────────


def route_tools(
	user_message: str,
	conversation_history: list[dict] | None = None,
) -> ToolRoutingResult:
	"""Route a user query to the relevant subset of tools.

	This is the main entry point, replacing direct calls to
	``get_all_tools_schema()`` in the chat and streaming APIs.

	Algorithm:
	1. Classify intent (deterministic keyword matching)
	2. If conversational → return empty tool set
	3. If confident match → filter tools by matched categories + adjacency
	   - Phase 14A: write requests always include operations category
	   - Phase 14A: ambiguous queries get broader category set
	4. If follow-up → use categories from prior tool calls
	5. If no match / low confidence → fallback to all tools
	6. Phase 14A: generate routing_hint for system prompt injection

	Args:
		user_message: The user's latest message text.
		conversation_history: Optional conversation history for follow-up
			detection and context.

	Returns:
		ToolRoutingResult with filtered tools and routing metadata.
	"""
	intent = classify_intent(user_message, conversation_history)

	# Conversational queries need no tools at all
	if intent.query_type == "conversational":
		log_info(
			"Tool routing: conversational (no tools)",
			message_preview=user_message[:80],
		)
		return ToolRoutingResult(
			tools=[],
			intent=intent,
			is_fallback=False,
			tool_count=0,
			categories_matched=(),
			routing_hint="",
		)

	# Confident category match — filter tools
	if intent.categories and intent.confidence >= CONFIDENCE_THRESHOLD:
		categories = _expand_categories(intent.categories)

		# Phase 14A: write requests include operations tools (if enabled)
		if intent.is_write_request and "operations" not in categories and _is_category_enabled("operations"):
			categories.add("operations")

		# Phase 14A: ambiguous queries — include one extra adjacent category
		# to give the LLM a broader selection when intent is unclear
		if intent.is_ambiguous:
			categories = _expand_categories_for_ambiguity(intent.categories, categories)

		tools = _get_filtered_tools(categories)

		# Phase 14A: generate routing hint
		routing_hint = _build_routing_hint(intent, tuple(sorted(categories)), tools)

		log_info(
			"Tool routing: filtered",
			message_preview=user_message[:80],
			categories=",".join(sorted(categories)),
			tool_count=len(tools),
			confidence=f"{intent.confidence:.2f}",
			query_type=intent.query_type,
			is_write=intent.is_write_request,
			is_ambiguous=intent.is_ambiguous,
			complexity=intent.complexity,
			matched_keywords=",".join(intent.matched_keywords[:5]),
		)

		return ToolRoutingResult(
			tools=tools,
			intent=intent,
			is_fallback=False,
			tool_count=len(tools),
			categories_matched=tuple(sorted(categories)),
			routing_hint=routing_hint,
		)

	# No confident match — fallback to all tools
	from ai_chatbot.tools.registry import get_all_tools_schema

	all_tools = get_all_tools_schema()

	log_warning(
		"Tool routing: fallback (all tools)",
		message_preview=user_message[:80],
		confidence=f"{intent.confidence:.2f}",
		query_type=intent.query_type,
	)

	return ToolRoutingResult(
		tools=all_tools,
		intent=intent,
		is_fallback=True,
		tool_count=len(all_tools),
		categories_matched=(),
		routing_hint=_build_fallback_hint(intent),
	)


# ── Internal helpers ────────────────────────────────────────────────


def _expand_categories(categories: tuple[str, ...]) -> set[str]:
	"""Expand matched categories with their adjacent categories.

	Only includes categories that are enabled in Chatbot Settings —
	disabled categories are pruned from both primary and adjacency sets
	so the LLM never receives tools from disabled categories.

	Args:
		categories: Primary matched categories from intent classification.

	Returns:
		Expanded set including adjacency categories (enabled only).
	"""
	expanded: set[str] = set()

	for cat in categories:
		if _is_category_enabled(cat):
			expanded.add(cat)

	for cat in list(expanded):
		for adj in CATEGORY_ADJACENCY.get(cat, []):
			if _is_category_enabled(adj):
				expanded.add(adj)

	log_debug(
		"Category expansion",
		primary=",".join(categories),
		expanded=",".join(sorted(expanded)),
	)

	return expanded


def _is_category_enabled(category: str) -> bool:
	"""Check whether a tool category is enabled in Chatbot Settings.

	Categories without a settings field (not in TOOL_CATEGORIES) are
	treated as always enabled.
	"""
	from ai_chatbot.core.config import is_tool_category_enabled
	from ai_chatbot.core.constants import TOOL_CATEGORIES

	settings_field = TOOL_CATEGORIES.get(category)
	if not settings_field:
		return True  # Unknown category — don't block
	return is_tool_category_enabled(settings_field)


def _get_filtered_tools(categories: set[str]) -> list[dict]:
	"""Get tool schemas filtered by categories plus always-include tools.

	Args:
		categories: Set of category keys to include.

	Returns:
		List of tool schemas in OpenAI function calling format.
	"""
	from ai_chatbot.tools.registry import get_tools_by_categories

	return get_tools_by_categories(categories, extra_tool_names=set(ALWAYS_INCLUDE_TOOLS))


def _expand_categories_for_ambiguity(
	primary_categories: tuple[str, ...],
	current: set[str],
) -> set[str]:
	"""When intent is ambiguous, expand the category set more aggressively.

	In addition to the standard adjacency expansion, add all adjacent
	categories from every matched primary category (not just top ones).
	Only includes enabled categories.

	Args:
		primary_categories: The original matched categories from intent.
		current: Already-expanded category set.

	Returns:
		Further expanded set.
	"""
	expanded = set(current)
	for cat in primary_categories:
		for adj in CATEGORY_ADJACENCY.get(cat, []):
			if _is_category_enabled(adj):
				expanded.add(adj)
	# Also expand adjacencies of adjacencies for ambiguous queries
	second_pass = set()
	for cat in list(expanded):
		for adj in CATEGORY_ADJACENCY.get(cat, []):
			if _is_category_enabled(adj):
				second_pass.add(adj)
	expanded |= second_pass
	return expanded


# ── Category label map (Phase 14A — for human-readable hints) ──────

CATEGORY_LABELS: dict[str, str] = {
	"selling": "sales & revenue",
	"buying": "purchasing & procurement",
	"crm": "CRM & pipeline",
	"inventory": "stock & inventory",
	"finance": "finance & accounting",
	"hrms": "HR & payroll",
	"operations": "document operations (CRUD)",
	"idp": "document processing (IDP)",
	"predictive": "forecasting & anomaly detection",
}


def _build_routing_hint(
	intent: IntentResult,
	categories: tuple[str, ...],
	tools: list[dict],
) -> str:
	"""Build a concise routing context hint for the system prompt.

	The hint tells the LLM what the router detected and which tool
	categories are available, so it can make better tool selections
	without the full 60-tool schema.

	Args:
		intent: The classified intent result.
		categories: Expanded category set used for filtering.
		tools: The filtered tool list.

	Returns:
		A short hint string (typically 100-200 tokens).
	"""
	parts: list[str] = []

	# Category context
	cat_labels = [CATEGORY_LABELS.get(c, c) for c in categories]
	parts.append(f"Detected categories: {', '.join(cat_labels)}.")

	# Query type context
	if intent.query_type == "action":
		parts.append("This is a write/action request — use propose_* tools for document operations.")
	elif intent.query_type == "comparison":
		parts.append(
			"This is a comparison query — consider calling the relevant tool multiple times with different parameters, or use a multi-dimensional tool."
		)
	elif intent.query_type == "forecast":
		parts.append("This is a forecasting query — use the forecast_* tools.")
	elif intent.query_type == "aggregate":
		parts.append("This is a summary/aggregate query — use analytics tools that return totals.")
	elif intent.query_type == "detail":
		parts.append("This is a detail query — use tools that return breakdowns or lists.")

	# Complexity hints
	if intent.complexity == "multi_step":
		parts.append(
			"This appears to be a multi-step request — you may need to call multiple tools sequentially."
		)
	elif intent.complexity == "comparative":
		parts.append(
			"This is a comparative request — call the tool with different parameters for each period/entity to compare."
		)

	# Ambiguity warning
	if intent.is_ambiguous:
		parts.append(
			"The query is ambiguous — if the available tools don't clearly match, ask the user to clarify before calling a tool."
		)

	# Available tool names (compact list for LLM reference)
	tool_names = [t["function"]["name"] for t in tools if t.get("function")]
	if tool_names and len(tool_names) <= 20:
		parts.append(f"Available tools: {', '.join(tool_names)}.")

	return " ".join(parts)


def _build_fallback_hint(intent: IntentResult) -> str:
	"""Build a routing hint when falling back to all tools.

	Less specific than a filtered hint — just tells the LLM to be
	careful about tool selection since the query didn't match clearly.

	Args:
		intent: The classified intent result.

	Returns:
		A short fallback hint string.
	"""
	parts = ["All tools are available for this query."]

	if intent.query_type != "unknown":
		parts.append(f"Detected query type: {intent.query_type}.")

	if intent.matched_keywords:
		kws = ", ".join(intent.matched_keywords[:5])
		parts.append(f"Matched keywords: {kws}.")

	parts.append(
		"Choose the most relevant tool carefully. If the query doesn't require data lookup, you may respond directly without tools."
	)

	return " ".join(parts)
