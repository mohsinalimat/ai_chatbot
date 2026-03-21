# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Cash Flow Tools
Unified cash flow statement, trend, and analysis for AI Chatbot.

Phase 11D: Merged get_cash_flow_analysis (from account.py), get_cash_flow_statement,
and get_cash_flow_trend into a single get_cash_flow tool.
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import add_days, add_months, flt, get_first_day, get_last_day, nowdate

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_multi_series_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.finance.common import apply_company_filter, primary
from ai_chatbot.tools.registry import register_tool


def _cash_flow_analysis(months, company):
	"""Simple cash flow analysis: total inflow vs outflow for a period (no chart)."""
	end_date = nowdate()
	start_date = add_days(end_date, -months * 30)

	pe = frappe.qb.DocType("Payment Entry")

	# Cash inflow (Receive)
	inflow_q = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Receive")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
	)
	inflow_q = apply_company_filter(inflow_q, pe, company)
	inflow_result = inflow_q.run(as_dict=True)
	inflow = flt(inflow_result[0].total) if inflow_result else 0

	# Cash outflow (Pay)
	outflow_q = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Pay")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
	)
	outflow_q = apply_company_filter(outflow_q, pe, company)
	outflow_result = outflow_q.run(as_dict=True)
	outflow = flt(outflow_result[0].total) if outflow_result else 0

	return {
		"view": "analysis",
		"cash_inflow": inflow,
		"cash_outflow": outflow,
		"net_cash_flow": inflow - outflow,
		"period_months": months,
		"period": {"from": start_date, "to": end_date},
	}


def _cash_flow_statement(from_date, to_date, company, cost_center, department, project):
	"""Structured cash flow statement with operating and financing activities."""
	pe = frappe.qb.DocType("Payment Entry")

	def _pe_sum(payment_type, party_type=None, exclude_party_type=None):
		q = (
			frappe.qb.from_(pe)
			.select(fn.Sum(pe.base_paid_amount).as_("total"))
			.where(pe.docstatus == 1)
			.where(pe.payment_type == payment_type)
			.where(pe.posting_date >= from_date)
			.where(pe.posting_date <= to_date)
		)
		if party_type:
			q = q.where(pe.party_type == party_type)
		if exclude_party_type:
			q = q.where((pe.party_type != exclude_party_type) | (pe.party_type.isnull()))
		q = apply_company_filter(q, pe, company)
		q = apply_dimension_filters(q, pe, cost_center=cost_center, department=department, project=project)
		r = q.run(as_dict=True)
		return flt(r[0].total) if r else 0

	operating_inflow = _pe_sum("Receive", party_type="Customer")
	operating_outflow = _pe_sum("Pay", party_type="Supplier")
	financing_inflow = _pe_sum("Receive", exclude_party_type="Customer")
	financing_outflow = _pe_sum("Pay", exclude_party_type="Supplier")

	operating_net = operating_inflow - operating_outflow
	financing_net = financing_inflow - financing_outflow
	total_net = operating_net + financing_net

	return {
		"view": "statement",
		"operating": {
			"inflow": flt(operating_inflow, 2),
			"outflow": flt(operating_outflow, 2),
			"net": flt(operating_net, 2),
		},
		"financing_and_other": {
			"inflow": flt(financing_inflow, 2),
			"outflow": flt(financing_outflow, 2),
			"net": flt(financing_net, 2),
		},
		"total_net_cash_flow": flt(total_net, 2),
		"period": {"from": from_date, "to": to_date},
	}


def _cash_flow_trend(months, company, cost_center, department, project):
	"""Monthly inflow/outflow/net trend with line chart."""
	pe = frappe.qb.DocType("Payment Entry")
	start_date = get_first_day(add_months(nowdate(), -months + 1))
	end_date = get_last_day(nowdate())
	month_expr = fn.DateFormat(pe.posting_date, "%Y-%m")

	def _monthly_sum(payment_type):
		q = (
			frappe.qb.from_(pe)
			.select(
				month_expr.as_("month"),
				fn.Sum(pe.base_paid_amount).as_("total"),
			)
			.where(pe.docstatus == 1)
			.where(pe.payment_type == payment_type)
			.where(pe.posting_date >= start_date)
			.where(pe.posting_date <= end_date)
		)
		q = apply_company_filter(q, pe, company)
		q = apply_dimension_filters(q, pe, cost_center=cost_center, department=department, project=project)
		return {r.month: flt(r.total) for r in q.groupby(month_expr).orderby(month_expr).run(as_dict=True)}

	inflow_map = _monthly_sum("Receive")
	outflow_map = _monthly_sum("Pay")

	all_months = sorted(set(list(inflow_map.keys()) + list(outflow_map.keys())))

	monthly = []
	for m in all_months:
		inflow = flt(inflow_map.get(m, 0), 2)
		outflow = flt(outflow_map.get(m, 0), 2)
		monthly.append(
			{
				"month": m,
				"inflow": inflow,
				"outflow": outflow,
				"net": flt(inflow - outflow, 2),
			}
		)

	categories = [m["month"] for m in monthly]
	series_list = [
		{"name": "Inflow", "data": [m["inflow"] for m in monthly]},
		{"name": "Outflow", "data": [m["outflow"] for m in monthly]},
		{"name": "Net", "data": [m["net"] for m in monthly]},
	]

	return {
		"view": "trend",
		"months": monthly,
		"period_months": months,
		"echart_option": build_multi_series_chart(
			title="Monthly Cash Flow Trend",
			categories=categories,
			series_list=series_list,
			y_axis_name="Amount",
			chart_type="line",
		),
	}


@register_tool(
	name="get_cash_flow",
	category="finance",
	description=(
		"Get cash flow data. Use view='analysis' for simple inflow/outflow summary, "
		"view='statement' for structured operating/financing breakdown, "
		"or view='trend' for monthly trend with chart."
	),
	parameters={
		"view": {
			"type": "string",
			"description": "Cash flow view: 'analysis', 'statement', or 'trend'",
			"enum": ["analysis", "statement", "trend"],
		},
		"months": {
			"type": "integer",
			"description": "Number of months (default 6 for analysis, 12 for trend). Not used for statement view.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start. Used only for statement view.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end. Used only for statement view.",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
	},
	doctypes=["Payment Entry"],
)
def get_cash_flow(
	view="analysis",
	months=None,
	from_date=None,
	to_date=None,
	company=None,
	cost_center=None,
	department=None,
	project=None,
):
	"""Unified cash flow tool — replaces get_cash_flow_analysis, get_cash_flow_statement,
	and get_cash_flow_trend (Phase 11D consolidation).
	"""
	company = get_company_filter(company)

	if view == "statement":
		if not from_date or not to_date:
			fy_from, fy_to = get_fiscal_year_dates(primary(company))
			from_date = from_date or fy_from
			to_date = to_date or fy_to
		result = _cash_flow_statement(from_date, to_date, company, cost_center, department, project)
	elif view == "trend":
		result = _cash_flow_trend(months or 12, company, cost_center, department, project)
	else:
		result = _cash_flow_analysis(months or 6, company)

	return build_currency_response(result, primary(company))


@register_tool(
	name="get_bank_balance",
	category="finance",
	description="Get current bank and cash account balances",
	parameters={
		"account": {"type": "string", "description": "Specific bank or cash account name to filter"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["GL Entry", "Account"],
)
def get_bank_balance(account=None, company=None):
	"""Get current balances for bank and cash accounts from GL Entry."""
	company = get_company_filter(company)

	acc = frappe.qb.DocType("Account")
	gle = frappe.qb.DocType("GL Entry")

	# Get bank/cash accounts
	acc_query = (
		frappe.qb.from_(acc)
		.select(acc.name, acc.account_type)
		.where(acc.account_type.isin(["Bank", "Cash"]))
		.where(acc.is_group == 0)
	)
	if isinstance(company, list):
		acc_query = acc_query.where(acc.company.isin(company))
	else:
		acc_query = acc_query.where(acc.company == company)

	if account:
		acc_query = acc_query.where(acc.name == account)

	accounts = acc_query.run(as_dict=True)

	if not accounts:
		result = {
			"accounts": [],
			"total_balance": 0,
			"message": "No bank or cash accounts found",
		}
		return build_currency_response(result, primary(company))

	account_names = [a.name for a in accounts]

	# Get balances from GL Entry (debit - credit)
	bal_query = (
		frappe.qb.from_(gle)
		.select(
			gle.account,
			(fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("balance"),
		)
		.where(gle.account.isin(account_names))
		.where(gle.is_cancelled == 0)
		.groupby(gle.account)
	)
	if isinstance(company, list):
		bal_query = bal_query.where(gle.company.isin(company))
	else:
		bal_query = bal_query.where(gle.company == company)
	balances = bal_query.run(as_dict=True)

	balance_map = {b.account: flt(b.balance, 2) for b in balances}
	account_type_map = {a.name: a.account_type for a in accounts}

	account_list = []
	total_balance = 0.0
	for acc_name in account_names:
		bal = balance_map.get(acc_name, 0)
		account_list.append(
			{
				"account": acc_name,
				"account_type": account_type_map.get(acc_name, ""),
				"balance": flt(bal, 2),
			}
		)
		total_balance += bal

	result = {
		"accounts": account_list,
		"total_balance": flt(total_balance, 2),
	}
	return build_currency_response(result, primary(company))
