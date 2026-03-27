# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Tool Router for AI Chatbot (Phase 12A — System Tool Discovery Layer)

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
	4. If follow-up → use categories from prior tool calls
	5. If no match / low confidence → fallback to all tools

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
		)

	# Confident category match — filter tools
	if intent.categories and intent.confidence >= CONFIDENCE_THRESHOLD:
		categories = _expand_categories(intent.categories)
		tools = _get_filtered_tools(categories)

		log_info(
			"Tool routing: filtered",
			message_preview=user_message[:80],
			categories=",".join(sorted(categories)),
			tool_count=len(tools),
			confidence=f"{intent.confidence:.2f}",
			query_type=intent.query_type,
			matched_keywords=",".join(intent.matched_keywords[:5]),
		)

		return ToolRoutingResult(
			tools=tools,
			intent=intent,
			is_fallback=False,
			tool_count=len(tools),
			categories_matched=tuple(sorted(categories)),
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
	)


# ── Internal helpers ────────────────────────────────────────────────


def _expand_categories(categories: tuple[str, ...]) -> set[str]:
	"""Expand matched categories with their adjacent categories.

	Args:
		categories: Primary matched categories from intent classification.

	Returns:
		Expanded set including adjacency categories.
	"""
	expanded: set[str] = set(categories)

	for cat in categories:
		for adj in CATEGORY_ADJACENCY.get(cat, []):
			expanded.add(adj)

	log_debug(
		"Category expansion",
		primary=",".join(categories),
		expanded=",".join(sorted(expanded)),
	)

	return expanded


def _get_filtered_tools(categories: set[str]) -> list[dict]:
	"""Get tool schemas filtered by categories plus always-include tools.

	Args:
		categories: Set of category keys to include.

	Returns:
		List of tool schemas in OpenAI function calling format.
	"""
	from ai_chatbot.tools.registry import get_tools_by_categories

	return get_tools_by_categories(categories, extra_tool_names=set(ALWAYS_INCLUDE_TOOLS))
