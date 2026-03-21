# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Accounts Receivable Tools
Top debtors for AI Chatbot.

NOTE: get_receivable_aging has been merged into get_party_aging in finance/aging.py
(Phase 11D tool consolidation).
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_top_n_limit
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_horizontal_bar
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.finance.common import apply_company_filter, primary
from ai_chatbot.tools.registry import register_tool


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
	query = apply_company_filter(query, si, company)
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
	return build_currency_response(result, primary(company))
