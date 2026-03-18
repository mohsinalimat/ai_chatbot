# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Account Tools Module
Finance and accounting tools for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import add_days, flt, nowdate

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


def _primary(company):
	"""Get primary company name (first in list or string as-is)."""
	return company[0] if isinstance(company, list) else company


@register_tool(
	name="get_financial_summary",
	category="finance",
	description="Get financial summary including revenue, expenses, and profit for a period",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
	doctypes=["Sales Invoice", "Purchase Invoice"],
)
def get_financial_summary(from_date=None, to_date=None, company=None):
	"""Get financial summary using base currency fields and frappe.qb."""
	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	# Revenue from Sales Invoices (base_grand_total = company currency)
	si = frappe.qb.DocType("Sales Invoice")
	query = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
	)
	if isinstance(company, list):
		query = query.where(si.company.isin(company))
	else:
		query = query.where(si.company == company)
	revenue_result = query.run(as_dict=True)
	revenue = flt(revenue_result[0].total) if revenue_result else 0

	# Expenses from Purchase Invoices (base_grand_total = company currency)
	pi = frappe.qb.DocType("Purchase Invoice")
	query = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
	)
	if isinstance(company, list):
		query = query.where(pi.company.isin(company))
	else:
		query = query.where(pi.company == company)
	expense_result = query.run(as_dict=True)
	expenses = flt(expense_result[0].total) if expense_result else 0

	result = {
		"revenue": revenue,
		"expenses": expenses,
		"profit": revenue - expenses,
		"period": {"from": from_date, "to": to_date},
	}
	return build_currency_response(result, _primary(company))


@register_tool(
	name="get_cash_flow_analysis",
	category="finance",
	description="Analyze cash flow patterns and trends over a period",
	parameters={
		"months": {"type": "integer", "description": "Number of months to analyze (default 6)"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
	doctypes=["Payment Entry"],
)
def get_cash_flow_analysis(months=6, company=None):
	"""Get cash flow analysis using base currency fields and frappe.qb."""
	company = get_company_filter(company)

	end_date = nowdate()
	start_date = add_days(end_date, -months * 30)

	pe = frappe.qb.DocType("Payment Entry")

	# Cash inflow (Receive) — base_paid_amount = company currency
	query = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Receive")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
	)
	if isinstance(company, list):
		query = query.where(pe.company.isin(company))
	else:
		query = query.where(pe.company == company)
	inflow_result = query.run(as_dict=True)
	inflow = flt(inflow_result[0].total) if inflow_result else 0

	# Cash outflow (Pay)
	query = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Pay")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
	)
	if isinstance(company, list):
		query = query.where(pe.company.isin(company))
	else:
		query = query.where(pe.company == company)
	outflow_result = query.run(as_dict=True)
	outflow = flt(outflow_result[0].total) if outflow_result else 0

	result = {
		"cash_inflow": inflow,
		"cash_outflow": outflow,
		"net_cash_flow": inflow - outflow,
		"period_months": months,
		"period": {"from": start_date, "to": end_date},
	}
	return build_currency_response(result, _primary(company))
