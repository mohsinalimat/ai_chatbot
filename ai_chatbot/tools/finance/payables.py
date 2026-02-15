"""
Accounts Payable Tools
AP aging analysis and top creditors for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import date_diff, flt, nowdate

from ai_chatbot.core.config import get_default_company
from ai_chatbot.core.constants import AGING_BUCKETS
from ai_chatbot.data.charts import build_bar_chart, build_horizontal_bar
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


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
	name="get_payable_aging",
	category="finance",
	description="Get accounts payable aging analysis with buckets (0-30, 31-60, 61-90, 90+ days overdue)",
	parameters={
		"ageing_based_on": {
			"type": "string",
			"description": "Aging basis: 'Due Date' or 'Posting Date' (default: 'Due Date')",
		},
		"supplier": {"type": "string", "description": "Filter by specific supplier name"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
)
def get_payable_aging(ageing_based_on="Due Date", supplier=None, company=None):
	"""Get AP aging analysis from outstanding Purchase Invoices."""
	company = get_default_company(company)
	today = nowdate()

	pi = frappe.qb.DocType("Purchase Invoice")
	date_field = pi.due_date if ageing_based_on == "Due Date" else pi.posting_date

	query = (
		frappe.qb.from_(pi)
		.select(
			pi.name,
			pi.supplier,
			pi.outstanding_amount,
			pi.base_grand_total,
			date_field.as_("age_date"),
			pi.posting_date,
		)
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.outstanding_amount > 0)
	)

	if supplier:
		query = query.where(pi.supplier == supplier)

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
			title="Payable Aging",
			categories=categories,
			series_data=values,
			y_axis_name="Amount",
			series_name="Outstanding",
		),
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_top_creditors",
	category="finance",
	description="Get top suppliers with the highest outstanding payables",
	parameters={
		"limit": {"type": "integer", "description": "Number of creditors to return (default 10)"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
)
def get_top_creditors(limit=10, company=None):
	"""Get top suppliers by outstanding payable amount."""
	company = get_default_company(company)

	pi = frappe.qb.DocType("Purchase Invoice")

	creditors = (
		frappe.qb.from_(pi)
		.select(
			pi.supplier,
			fn.Sum(pi.outstanding_amount).as_("total_outstanding"),
			fn.Count("*").as_("invoice_count"),
		)
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.outstanding_amount > 0)
		.groupby(pi.supplier)
		.orderby(fn.Sum(pi.outstanding_amount), order=frappe.qb.desc)
		.limit(limit)
		.run(as_dict=True)
	)

	top_creditors = [
		{
			"supplier": c.supplier,
			"outstanding": flt(c.total_outstanding, 2),
			"invoice_count": c.invoice_count,
		}
		for c in creditors
	]

	# Build chart (reversed for horizontal bar — top at top)
	suppliers = [c["supplier"] for c in reversed(top_creditors)]
	amounts = [c["outstanding"] for c in reversed(top_creditors)]

	result = {
		"top_creditors": top_creditors,
		"count": len(top_creditors),
		"echart_option": build_horizontal_bar(
			title="Top Creditors by Outstanding",
			categories=suppliers,
			series_data=amounts,
			x_axis_name="Amount",
			series_name="Outstanding",
		),
	}
	return build_currency_response(result, company)
