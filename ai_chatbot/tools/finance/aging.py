# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Party Aging Tools
Unified AR/AP aging analysis — replaces separate receivables.py and payables.py aging tools.
"""

import frappe
from frappe.utils import date_diff, flt, nowdate

from ai_chatbot.core.constants import AGING_BUCKETS
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_bar_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.finance.common import apply_company_filter, get_aging_bucket, primary
from ai_chatbot.tools.registry import register_tool


# ---------------------------------------------------------------------------
# Unified: get_party_aging  (replaces get_receivable_aging + get_payable_aging)
# ---------------------------------------------------------------------------
@register_tool(
	name="get_party_aging",
	category="finance",
	description=(
		"Get accounts receivable or payable aging analysis with buckets "
		"(0-30, 31-60, 61-90, 90+ days overdue). "
		"Use party_type='Customer' for receivables (AR) or party_type='Supplier' for payables (AP)."
	),
	parameters={
		"party_type": {
			"type": "string",
			"description": "Party type: 'Customer' for receivables (AR) or 'Supplier' for payables (AP)",
			"enum": ["Customer", "Supplier"],
		},
		"ageing_based_on": {
			"type": "string",
			"description": "Aging basis: 'Due Date' or 'Posting Date' (default: 'Due Date')",
		},
		"party": {"type": "string", "description": "Filter by specific customer or supplier name"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
	},
	doctypes=["Sales Invoice", "Purchase Invoice"],
)
def get_party_aging(
	party_type="Customer",
	ageing_based_on="Due Date",
	party=None,
	company=None,
	cost_center=None,
	department=None,
	project=None,
):
	"""Get AR or AP aging analysis from outstanding invoices.

	Unified replacement for get_receivable_aging and get_payable_aging.
	"""
	company = get_company_filter(company)
	today = nowdate()

	is_receivable = party_type == "Customer"
	doctype = "Sales Invoice" if is_receivable else "Purchase Invoice"
	party_field_name = "customer" if is_receivable else "supplier"

	inv = frappe.qb.DocType(doctype)
	date_field = inv.due_date if ageing_based_on == "Due Date" else inv.posting_date
	party_col = inv[party_field_name]

	query = (
		frappe.qb.from_(inv)
		.select(
			inv.name,
			party_col.as_("party_name"),
			inv.outstanding_amount,
			inv.base_grand_total,
			date_field.as_("age_date"),
			inv.posting_date,
		)
		.where(inv.docstatus == 1)
		.where(inv.outstanding_amount > 0)
	)
	query = apply_company_filter(query, inv, company)

	if party:
		query = query.where(party_col == party)

	query = apply_dimension_filters(
		query, inv, cost_center=cost_center, department=department, project=project
	)

	invoices = query.run(as_dict=True)

	# Bucket the invoices
	bucket_totals = {b["label"]: 0.0 for b in AGING_BUCKETS}
	bucket_counts = {b["label"]: 0 for b in AGING_BUCKETS}
	total_outstanding = 0.0

	for inv_row in invoices:
		days = max(0, date_diff(today, inv_row.age_date))
		bucket = get_aging_bucket(days)
		bucket_totals[bucket] += flt(inv_row.outstanding_amount)
		bucket_counts[bucket] += 1
		total_outstanding += flt(inv_row.outstanding_amount)

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
	chart_title = "Receivable Aging" if is_receivable else "Payable Aging"

	result = {
		"party_type": party_type,
		"aging_buckets": aging_buckets,
		"total_outstanding": flt(total_outstanding, 2),
		"total_invoices": len(invoices),
		"ageing_based_on": ageing_based_on,
		"echart_option": build_bar_chart(
			title=chart_title,
			categories=categories,
			series_data=values,
			y_axis_name="Amount",
			series_name="Outstanding",
		),
	}
	return build_currency_response(result, primary(company))
