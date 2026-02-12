"""
Account Tools Module
Finance and accounting tools for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import add_days, flt, nowdate

from ai_chatbot.core.config import get_default_company
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_financial_summary",
	category="finance",
	description="Get financial summary including revenue, expenses, and profit for a period",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_financial_summary(from_date=None, to_date=None, company=None):
	"""Get financial summary using base currency fields and frappe.qb."""
	company = get_default_company(company)

	if not from_date:
		from_date = add_days(nowdate(), -30)
	if not to_date:
		to_date = nowdate()

	# Revenue from Sales Invoices (base_grand_total = company currency)
	si = frappe.qb.DocType("Sales Invoice")
	revenue_result = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.company == company)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
		.run(as_dict=True)
	)
	revenue = flt(revenue_result[0].total) if revenue_result else 0

	# Expenses from Purchase Invoices (base_grand_total = company currency)
	pi = frappe.qb.DocType("Purchase Invoice")
	expense_result = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
		.run(as_dict=True)
	)
	expenses = flt(expense_result[0].total) if expense_result else 0

	result = {
		"revenue": revenue,
		"expenses": expenses,
		"profit": revenue - expenses,
		"period": {"from": from_date, "to": to_date},
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_cash_flow_analysis",
	category="finance",
	description="Analyze cash flow patterns and trends over a period",
	parameters={
		"months": {"type": "integer", "description": "Number of months to analyze (default 6)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_cash_flow_analysis(months=6, company=None):
	"""Get cash flow analysis using base currency fields and frappe.qb."""
	company = get_default_company(company)

	end_date = nowdate()
	start_date = add_days(end_date, -months * 30)

	pe = frappe.qb.DocType("Payment Entry")

	# Cash inflow (Receive) — base_paid_amount = company currency
	inflow_result = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.company == company)
		.where(pe.payment_type == "Receive")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
		.run(as_dict=True)
	)
	inflow = flt(inflow_result[0].total) if inflow_result else 0

	# Cash outflow (Pay)
	outflow_result = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.company == company)
		.where(pe.payment_type == "Pay")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
		.run(as_dict=True)
	)
	outflow = flt(outflow_result[0].total) if outflow_result else 0

	result = {
		"cash_inflow": inflow,
		"cash_outflow": outflow,
		"net_cash_flow": inflow - outflow,
		"period_months": months,
		"period": {"from": start_date, "to": end_date},
	}
	return build_currency_response(result, company)
