# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Accounts Payable Tools
Top creditors for AI Chatbot.

NOTE: get_payable_aging has been merged into get_party_aging in finance/aging.py
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
	name="get_top_creditors",
	category="finance",
	description="Get top suppliers with the highest outstanding payables",
	parameters={
		"limit": {"type": "integer", "description": "Number of creditors to return (default 10)"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
	},
	doctypes=["Purchase Invoice"],
)
def get_top_creditors(limit=10, company=None, cost_center=None, department=None, project=None):
	"""Get top suppliers by outstanding payable amount."""
	limit = get_top_n_limit(limit)
	company = get_company_filter(company)

	pi = frappe.qb.DocType("Purchase Invoice")

	query = (
		frappe.qb.from_(pi)
		.select(
			pi.supplier,
			fn.Sum(pi.outstanding_amount).as_("total_outstanding"),
			fn.Count("*").as_("invoice_count"),
		)
		.where(pi.docstatus == 1)
		.where(pi.outstanding_amount > 0)
	)
	query = apply_company_filter(query, pi, company)
	query = apply_dimension_filters(
		query, pi, cost_center=cost_center, department=department, project=project
	)
	creditors = (
		query.groupby(pi.supplier)
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
	return build_currency_response(result, primary(company))
