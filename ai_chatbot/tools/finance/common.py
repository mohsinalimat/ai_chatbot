# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Common Finance Helpers
Shared utilities for finance tool modules — eliminates duplication across files.
"""

from __future__ import annotations

from ai_chatbot.core.constants import AGING_BUCKETS


def primary(company: str | list[str]) -> str:
	"""Get primary company name (first in list or string as-is)."""
	return company[0] if isinstance(company, list) else company


def apply_company_filter(query, doctype_ref, company: str | list[str]):
	"""Apply company filter supporting both single string and list.

	Args:
		query: A frappe.qb query object.
		doctype_ref: The DocType reference (e.g. `frappe.qb.DocType("Sales Invoice")`).
		company: Single company string or list of company strings.

	Returns:
		The query with the company filter applied.
	"""
	if isinstance(company, list):
		return query.where(doctype_ref.company.isin(company))
	return query.where(doctype_ref.company == company)


def get_aging_bucket(days_overdue: int) -> str:
	"""Classify days overdue into an aging bucket label.

	Uses the AGING_BUCKETS constant (0-30, 31-60, 61-90, 90+).

	Args:
		days_overdue: Number of days overdue (non-negative).

	Returns:
		Bucket label string (e.g. "0-30", "31-60", "61-90", "90+").
	"""
	for bucket in AGING_BUCKETS:
		if bucket["max"] is None:
			if days_overdue >= bucket["min"]:
				return bucket["label"]
		elif bucket["min"] <= days_overdue <= bucket["max"]:
			return bucket["label"]
	return "90+"
