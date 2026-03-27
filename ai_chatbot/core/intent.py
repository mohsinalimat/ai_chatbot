# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Intent Classifier for AI Chatbot Tool Router

Deterministic (no LLM) classification of user queries into tool categories
using keyword matching with weighted scoring. Part of Phase 12A — System
Tool Discovery Layer.

The classifier maps user messages to one or more tool categories
(e.g. "selling", "finance", "hrms") so the tool router can send only
relevant tool schemas to the LLM, saving ~6K-10K tokens per request.
"""

from __future__ import annotations

import dataclasses
import re

from ai_chatbot.core.entity_extractor import extract_entities

# ── IntentResult ────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True, slots=True)
class IntentResult:
	"""Result of intent classification on a user query."""

	categories: tuple[str, ...]
	"""Matched tool categories, e.g. ("selling", "finance")."""

	query_type: str
	"""One of: aggregate, detail, comparison, forecast, action, conversational, unknown."""

	confidence: float
	"""0.0-1.0 -- ratio of keyword match strength."""

	is_followup: bool
	"""True if the query is likely a follow-up to prior tool results."""

	matched_keywords: tuple[str, ...]
	"""Which keywords from INTENT_KEYWORDS matched."""

	entities: dict
	"""Extracted entities (dates, companies, items, etc.)."""


# ── Keyword → Category mapping ──────────────────────────────────────
# Each keyword maps to a list of (category, weight) tuples.
# Longer phrases are matched first to avoid partial collisions.

INTENT_KEYWORDS: dict[str, list[tuple[str, float]]] = {
	# ── selling ──
	"sales analytics": [("selling", 1.0)],
	"sales trend": [("selling", 1.0)],
	"sales by territory": [("selling", 1.0)],
	"top customers": [("selling", 1.0)],
	"average order": [("selling", 0.8)],
	"sales": [("selling", 1.0)],
	"revenue": [("selling", 0.9), ("finance", 0.3)],
	"territory": [("selling", 0.9)],
	"item group": [("selling", 0.7), ("buying", 0.3)],
	"product category": [("selling", 0.7)],
	"item category": [("selling", 0.7)],
	# ── buying ──
	"purchase analytics": [("buying", 1.0)],
	"purchase order": [("buying", 1.0)],
	"supplier performance": [("buying", 1.0)],
	"purchase": [("buying", 1.0)],
	"procurement": [("buying", 1.0)],
	"supplier": [("buying", 1.0)],
	"spending": [("buying", 0.9), ("finance", 0.3)],
	"vendor": [("buying", 0.9)],
	# ── crm ──
	"sales funnel": [("crm", 1.0)],
	"lead source": [("crm", 1.0)],
	"lead conversion": [("crm", 1.0)],
	"conversion rate": [("crm", 1.0)],
	"pipeline": [("crm", 1.0)],
	"funnel": [("crm", 1.0)],
	"campaign": [("crm", 0.9)],
	"lead": [("crm", 1.0)],
	"leads": [("crm", 1.0)],
	"opportunity": [("crm", 1.0)],
	"opportunities": [("crm", 1.0)],
	"crm": [("crm", 1.0)],
	# ── inventory ──
	"stock movement": [("inventory", 1.0)],
	"stock ageing": [("inventory", 1.0)],
	"stock age": [("inventory", 1.0)],
	"low stock": [("inventory", 1.0)],
	"reorder level": [("inventory", 1.0)],
	"stock": [("inventory", 1.0)],
	"inventory": [("inventory", 1.0)],
	"warehouse": [("inventory", 1.0)],
	"reorder": [("inventory", 1.0)],
	# ── finance ──
	"financial overview": [("finance", 1.0)],
	"financial health": [("finance", 1.0)],
	"financial summary": [("finance", 1.0)],
	"financial ratios": [("finance", 1.0)],
	"trial balance": [("finance", 1.0)],
	"general ledger": [("finance", 1.0)],
	"bank balance": [("finance", 1.0)],
	"cash flow": [("finance", 1.0)],
	"cash conversion": [("finance", 1.0)],
	"working capital": [("finance", 1.0)],
	"account statement": [("finance", 1.0)],
	"monthly comparison": [("finance", 1.0)],
	"gross margin": [("finance", 1.0)],
	"net margin": [("finance", 1.0)],
	"balance sheet": [("finance", 1.0)],
	"cfo dashboard": [("finance", 1.0)],
	"budget": [("finance", 1.0)],
	"budget variance": [("finance", 1.0)],
	"receivable": [("finance", 1.0)],
	"receivables": [("finance", 1.0)],
	"payable": [("finance", 1.0)],
	"payables": [("finance", 1.0)],
	"debtor": [("finance", 1.0)],
	"debtors": [("finance", 1.0)],
	"creditor": [("finance", 1.0)],
	"creditors": [("finance", 1.0)],
	"outstanding": [("finance", 0.9)],
	"overdue": [("finance", 0.9)],
	"aging": [("finance", 0.9)],
	"ageing": [("finance", 0.9)],
	"p&l": [("finance", 1.0)],
	"profit and loss": [("finance", 1.0)],
	"profit": [("finance", 1.0)],
	"loss": [("finance", 1.0)],
	"financial": [("finance", 1.0)],
	"accounting": [("finance", 1.0)],
	"ratio": [("finance", 1.0)],
	"ratios": [("finance", 1.0)],
	"gl": [("finance", 1.0)],
	"bank": [("finance", 0.8)],
	"cfo": [("finance", 1.0)],
	"profitability": [("finance", 1.0)],
	"consolidated": [("finance", 0.9)],
	"subsidiary": [("finance", 0.8)],
	"subsidiaries": [("finance", 0.8)],
	"currency": [("finance", 0.7)],
	"expense": [("finance", 0.9)],
	"expenses": [("finance", 0.9)],
	"cost": [("finance", 0.7)],
	"margin": [("finance", 0.8), ("selling", 0.3)],
	"ebitda": [("finance", 1.0)],
	# ── hrms ──
	"department wise salary": [("hrms", 1.0)],
	"employee turnover": [("hrms", 1.0)],
	"human resource": [("hrms", 1.0)],
	"employee": [("hrms", 1.0)],
	"employees": [("hrms", 1.0)],
	"attendance": [("hrms", 1.0)],
	"leave": [("hrms", 1.0)],
	"payroll": [("hrms", 1.0)],
	"salary": [("hrms", 1.0)],
	"salaries": [("hrms", 1.0)],
	"turnover": [("hrms", 0.9)],
	"headcount": [("hrms", 1.0)],
	"hr": [("hrms", 1.0)],
	"hire": [("hrms", 0.9)],
	"hires": [("hrms", 0.9)],
	"attrition": [("hrms", 0.9)],
	"department": [("hrms", 0.7), ("finance", 0.3)],
	# ── idp ──
	"document extraction": [("idp", 1.0)],
	"compare document": [("idp", 1.0)],
	"extract data": [("idp", 1.0)],
	"extract": [("idp", 0.9)],
	"upload": [("idp", 0.8)],
	"receipt": [("idp", 0.8), ("buying", 0.3)],
	"reconcile": [("idp", 0.8)],
	# ── predictive ──
	"demand forecast": [("predictive", 1.0)],
	"revenue forecast": [("predictive", 1.0)],
	"cash flow forecast": [("predictive", 1.0)],
	"anomaly detection": [("predictive", 1.0)],
	"forecast": [("predictive", 1.0)],
	"predict": [("predictive", 1.0)],
	"prediction": [("predictive", 1.0)],
	"anomaly": [("predictive", 1.0)],
	"anomalies": [("predictive", 1.0)],
	"projection": [("predictive", 1.0)],
	"trend": [("predictive", 0.6), ("selling", 0.4)],
	# ── operations (action verbs + entity) ──
	"change status": [("operations", 1.0)],
	"look up": [("operations", 0.9)],
	"search": [("operations", 0.8)],
	"find": [("operations", 0.8)],
	"create": [("operations", 1.0)],
	"add": [("operations", 0.7)],
	"update": [("operations", 1.0)],
	"todo": [("operations", 1.0)],
	"task": [("operations", 0.8)],
	"submit": [("operations", 1.0)],
	"cancel document": [("operations", 1.0)],
	"draft": [("operations", 0.8)],
	"undo": [("operations", 0.9)],
	"modify": [("operations", 0.8)],
	"delete": [("operations", 0.9)],
	"remove": [("operations", 0.8)],
	# ── cross-category keywords ──
	"customer": [("selling", 0.7), ("crm", 0.5)],
	"customers": [("selling", 0.7), ("crm", 0.5)],
	"order": [("selling", 0.6), ("buying", 0.4)],
	"orders": [("selling", 0.6), ("buying", 0.4)],
	"invoice": [("selling", 0.5), ("buying", 0.5), ("finance", 0.3)],
	"invoices": [("selling", 0.5), ("buying", 0.5), ("finance", 0.3)],
	"item": [("selling", 0.5), ("inventory", 0.5)],
	"items": [("selling", 0.5), ("inventory", 0.5)],
	# ── report-specific keywords (Phase 12B) ──
	"gl report": [("finance", 1.0)],
	"accounts receivable": [("finance", 1.0)],
	"accounts payable": [("finance", 1.0)],
	"ar summary": [("finance", 1.0)],
	"ap summary": [("finance", 1.0)],
	"account balance": [("finance", 1.0)],
	"consolidated financial": [("finance", 1.0)],
	"consolidated trial": [("finance", 1.0)],
	"sales register": [("selling", 1.0)],
	"purchase register": [("buying", 1.0)],
	"stock ledger": [("inventory", 1.0)],
	"stock balance": [("inventory", 1.0)],
	"stock aging": [("inventory", 1.0)],
}

# Pre-sort keywords by length descending so longer phrases match first
_SORTED_KEYWORDS: list[tuple[str, re.Pattern, list[tuple[str, float]]]] = []


def _get_sorted_keywords() -> list[tuple[str, re.Pattern, list[tuple[str, float]]]]:
	"""Lazily build and cache sorted keyword patterns."""
	global _SORTED_KEYWORDS
	if _SORTED_KEYWORDS:
		return _SORTED_KEYWORDS

	for kw in sorted(INTENT_KEYWORDS.keys(), key=len, reverse=True):
		pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
		_SORTED_KEYWORDS.append((kw, pattern, INTENT_KEYWORDS[kw]))

	return _SORTED_KEYWORDS


# ── Query type signals ──────────────────────────────────────────────

QUERY_TYPE_SIGNALS: dict[str, re.Pattern] = {
	"comparison": re.compile(
		r"\b(compare|comparison|versus|vs\.?|difference|between|against)\b",
		re.IGNORECASE,
	),
	"forecast": re.compile(
		r"\b(forecast|predict|prediction|projection|next month|next quarter|"
		r"will be|expected|future)\b",
		re.IGNORECASE,
	),
	"action": re.compile(
		r"\b(create|add|update|change|set|modify|delete|remove|submit|cancel|propose|undo|draft)\b",
		re.IGNORECASE,
	),
	"aggregate": re.compile(
		r"\b(total|sum|how much|how many|count|average|overall|summary)\b",
		re.IGNORECASE,
	),
	"detail": re.compile(
		r"\b(list|show me|details|breakdown|which|specific|individual)\b",
		re.IGNORECASE,
	),
}

# ── Follow-up signals ───────────────────────────────────────────────

FOLLOWUP_SIGNALS = re.compile(
	r"\b("
	r"show more|more details|elaborate|expand on|"
	r"what about|how about|and also|"
	r"same for|same but|same thing|"
	r"now show|now tell|now do|"
	r"instead|rather|"
	r"for (?:the same|that)|"
	r"drill down|go deeper|"
	r"yes|ok|sure|go ahead|do it|confirm|proceed"
	r")\b",
	re.IGNORECASE,
)

# ── Conversational signals (full-match only) ────────────────────────

CONVERSATIONAL_SIGNALS = re.compile(
	r"^(?:"
	r"hi|hello|hey|good morning|good afternoon|good evening|"
	r"thanks|thank you|thx|"
	r"bye|goodbye|see you|"
	r"how are you|what can you do|help|"
	r"who are you|what are you|"
	r"ok|okay|got it|understood|"
	r"please|sorry"
	r")[\s!?.,:;]*$",
	re.IGNORECASE,
)

# ── Thresholds ──────────────────────────────────────────────────────

# Minimum score for a category to be included in results
CATEGORY_THRESHOLD = 0.5

# Maximum number of categories to return (prevents overly broad routing)
MAX_CATEGORIES = 3


# ── Public API ──────────────────────────────────────────────────────


def classify_intent(
	user_message: str,
	conversation_history: list[dict] | None = None,
) -> IntentResult:
	"""Classify user intent deterministically using keyword matching.

	Algorithm:
	1. Check for conversational signals (no tools needed)
	2. Check for follow-up signals (reuse prior categories from history)
	3. Multi-pass keyword scan with weighted scoring
	4. Detect query type
	5. Extract entities
	6. Return IntentResult with matched categories

	Args:
		user_message: The user's latest message.
		conversation_history: Optional conversation history for follow-up detection.

	Returns:
		IntentResult with matched categories and metadata.
	"""
	if not user_message or not user_message.strip():
		return IntentResult(
			categories=(),
			query_type="unknown",
			confidence=0.0,
			is_followup=False,
			matched_keywords=(),
			entities={},
		)

	msg = user_message.strip()

	# 1. Conversational check — full match only
	if CONVERSATIONAL_SIGNALS.fullmatch(msg):
		return IntentResult(
			categories=(),
			query_type="conversational",
			confidence=1.0,
			is_followup=False,
			matched_keywords=(),
			entities={},
		)

	msg_lower = msg.lower()

	# 2. Follow-up check — look at prior tool calls in history
	is_followup = bool(FOLLOWUP_SIGNALS.search(msg_lower))
	followup_categories: tuple[str, ...] = ()

	if is_followup and conversation_history:
		followup_categories = _extract_followup_categories(conversation_history)

	# 3. Keyword scan — accumulate weighted scores per category
	scores: dict[str, float] = {}
	matched_kws: list[str] = []

	for kw, pattern, mappings in _get_sorted_keywords():
		if pattern.search(msg_lower):
			matched_kws.append(kw)
			for category, weight in mappings:
				scores[category] = scores.get(category, 0.0) + weight

	# 4. Category selection
	if scores:
		# Sort categories by score descending
		ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

		# Filter by threshold
		above_threshold = [(cat, score) for cat, score in ranked if score >= CATEGORY_THRESHOLD]

		if above_threshold:
			# Cap at MAX_CATEGORIES
			selected = [cat for cat, _score in above_threshold[:MAX_CATEGORIES]]
			max_score = above_threshold[0][1]
			confidence = min(1.0, max_score / 2.0)
			categories = tuple(selected)
		else:
			# Scores exist but none above threshold
			categories = ()
			confidence = 0.0
	elif is_followup and followup_categories:
		# No keyword matches, but this is a follow-up — use prior categories
		categories = followup_categories
		confidence = 0.5
	else:
		categories = ()
		confidence = 0.0

	# If follow-up with no keyword matches, prefer follow-up categories
	if not categories and is_followup and followup_categories:
		categories = followup_categories
		confidence = max(confidence, 0.5)

	# 5. Query type detection
	query_type = _detect_query_type(msg_lower)

	# 6. Entity extraction
	entities = extract_entities(user_message)

	return IntentResult(
		categories=categories,
		query_type=query_type,
		confidence=confidence,
		is_followup=is_followup,
		matched_keywords=tuple(matched_kws),
		entities=entities,
	)


# ── Internal helpers ────────────────────────────────────────────────


def _detect_query_type(msg_lower: str) -> str:
	"""Detect the query type from signal keywords.

	Returns the first matching type (ordered by specificity) or "unknown".
	"""
	for qtype, pattern in QUERY_TYPE_SIGNALS.items():
		if pattern.search(msg_lower):
			return qtype
	return "unknown"


def _extract_followup_categories(history: list[dict]) -> tuple[str, ...]:
	"""Extract tool categories from the most recent tool calls in history.

	Scans backward through conversation history for the last assistant
	message with tool_calls, extracts tool names, and looks up their
	categories from the registry.

	Args:
		history: Conversation history (list of message dicts).

	Returns:
		Tuple of category strings, or empty tuple if none found.
	"""
	for msg in reversed(history):
		if msg.get("role") != "assistant":
			continue

		tool_calls = msg.get("tool_calls")
		if not tool_calls:
			continue

		categories: set[str] = set()
		for tc in tool_calls:
			# Handle both normalised {"name": ...} and raw OpenAI {"function": {"name": ...}}
			name = tc.get("name") or ""
			if not name:
				func = tc.get("function")
				if isinstance(func, dict):
					name = func.get("name", "")
			if not name:
				continue

			# Look up category from registry (lazy import to avoid circular deps)
			from ai_chatbot.tools.registry import get_tool_info

			info = get_tool_info(name)
			if info:
				categories.add(info["category"])

		if categories:
			return tuple(sorted(categories))

	return ()
