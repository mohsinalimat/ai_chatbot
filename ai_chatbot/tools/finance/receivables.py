# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Accounts Receivable Tools
AR aging analysis and top debtors for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import date_diff, flt, nowdate

from ai_chatbot.core.config import get_top_n_limit
from ai_chatbot.core.constants import AGING_BUCKETS
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_bar_chart, build_horizontal_bar
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


def _primary(company):
	"""Get primary company name (first in list or string as-is)."""
	return company[0] if isinstance(company, list) else company


def _get_aging_bucket(days_overdue: int) -> str:
	"""Classify days overdue into an aging bucket label."""
	for bucket in AGING_BUCKETS:
		if bucket["max"] is None:
			if days_overdue >= bucket["min"]:
				return bucket["label"]
		elif bucket["min"] <= days_overdue <= bucket["max"]:
			return bucket["label"]
	return "90+"


@register_tool(
	name="get_receivable_aging",
	category="finance",
	description="Get accounts receivable aging analysis with buckets (0-30, 31-60, 61-90, 90+ days overdue)",
	parameters={
		"ageing_based_on": {
			"type": "string",
			"description": "Aging basis: 'Due Date' or 'Posting Date' (default: 'Due Date')",
		},
		"customer": {"type": "string", "description": "Filter by specific customer name"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
	},
	doctypes=["Sales Invoice"],
)
def get_receivable_aging(
	ageing_based_on="Due Date", customer=None, company=None, cost_center=None, department=None, project=None
):
	"""Get AR aging analysis from outstanding Sales Invoices."""
	company = get_company_filter(company)
	today = nowdate()

	si = frappe.qb.DocType("Sales Invoice")
	date_field = si.due_date if ageing_based_on == "Due Date" else si.posting_date

	query = (
		frappe.qb.from_(si)
		.select(
			si.name,
			si.customer,
			si.outstanding_amount,
			si.base_grand_total,
			date_field.as_("age_date"),
			si.posting_date,
		)
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
	)
	if isinstance(company, list):
		query = query.where(si.company.isin(company))
	else:
		query = query.where(si.company == company)

	if customer:
		query = query.where(si.customer == customer)

	query = apply_dimension_filters(
		query, si, cost_center=cost_center, department=department, project=project
	)

	invoices = query.run(as_dict=True)

	# Bucket the invoices
	bucket_totals = {b["label"]: 0.0 for b in AGING_BUCKETS}
	bucket_counts = {b["label"]: 0 for b in AGING_BUCKETS}
	total_outstanding = 0.0

	for inv in invoices:
		days = max(0, date_diff(today, inv.age_date))
		bucket = _get_aging_bucket(days)
		bucket_totals[bucket] += flt(inv.outstanding_amount)
		bucket_counts[bucket] += 1
		total_outstanding += flt(inv.outstanding_amount)

	aging_buckets = [
		{
			"bucket": label,
			"outstanding": flt(bucket_totals[label], 2),
			"invoice_count": bucket_counts[label],
		}
		for label in bucket_totals
	]

	# Build chart
	categories = [b["bucket"] for b in aging_buckets]
	values = [b["outstanding"] for b in aging_buckets]

	result = {
		"aging_buckets": aging_buckets,
		"total_outstanding": flt(total_outstanding, 2),
		"total_invoices": len(invoices),
		"ageing_based_on": ageing_based_on,
		"echart_option": build_bar_chart(
			title="Receivable Aging",
			categories=categories,
			series_data=values,
			y_axis_name="Amount",
			series_name="Outstanding",
		),
	}
	return build_currency_response(result, _primary(company))


@register_tool(
	name="get_top_debtors",
	category="finance",
	description="Get top customers with the highest outstanding receivables",
	parameters={
		"limit": {"type": "integer", "description": "Number of debtors to return (default 10)"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
	},
	doctypes=["Sales Invoice"],
)
def get_top_debtors(limit=10, company=None, cost_center=None, department=None, project=None):
	"""Get top customers by outstanding receivable amount."""
	limit = get_top_n_limit(limit)
	company = get_company_filter(company)

	si = frappe.qb.DocType("Sales Invoice")

	query = (
		frappe.qb.from_(si)
		.select(
			si.customer,
			fn.Sum(si.outstanding_amount).as_("total_outstanding"),
			fn.Count("*").as_("invoice_count"),
		)
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
	)
	if isinstance(company, list):
		query = query.where(si.company.isin(company))
	else:
		query = query.where(si.company == company)
	query = apply_dimension_filters(
		query, si, cost_center=cost_center, department=department, project=project
	)
	debtors = (
		query.groupby(si.customer)
		.orderby(fn.Sum(si.outstanding_amount), order=frappe.qb.desc)
		.limit(limit)
		.run(as_dict=True)
	)

	top_debtors = [
		{
			"customer": d.customer,
			"outstanding": flt(d.total_outstanding, 2),
			"invoice_count": d.invoice_count,
		}
		for d in debtors
	]

	# Build chart (reversed for horizontal bar — top at top)
	customers = [d["customer"] for d in reversed(top_debtors)]
	amounts = [d["outstanding"] for d in reversed(top_debtors)]

	result = {
		"top_debtors": top_debtors,
		"count": len(top_debtors),
		"echart_option": build_horizontal_bar(
			title="Top Debtors by Outstanding",
			categories=customers,
			series_data=amounts,
			x_axis_name="Amount",
			series_name="Outstanding",
		),
	}
	return build_currency_response(result, _primary(company))
