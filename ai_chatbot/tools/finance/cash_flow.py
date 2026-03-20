# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Enhanced Cash Flow Tools
Cash flow statement, trend analysis, and bank balances for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import add_months, flt, get_first_day, get_last_day, nowdate

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_multi_series_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


def _primary(company):
	"""Get primary company name (first in list or string as-is)."""
	return company[0] if isinstance(company, list) else company


def _apply_company_filter(query, doctype_ref, company):
	"""Apply company filter supporting both single string and list."""
	if isinstance(company, list):
		return query.where(doctype_ref.company.isin(company))
	return query.where(doctype_ref.company == company)


@register_tool(
	name="get_cash_flow_statement",
	category="finance",
	description="Get a structured cash flow statement with operating, investing, and financing activities",
	parameters={
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end.",
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
def get_cash_flow_statement(
	from_date=None, to_date=None, company=None, cost_center=None, department=None, project=None
):
	"""Get structured cash flow statement from Payment Entries."""
	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	pe = frappe.qb.DocType("Payment Entry")

	# Operating: cash received from customers
	op_inflow_q = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Receive")
		.where(pe.party_type == "Customer")
		.where(pe.posting_date >= from_date)
		.where(pe.posting_date <= to_date)
	)
	op_inflow_q = _apply_company_filter(op_inflow_q, pe, company)
	op_inflow_q = apply_dimension_filters(
		op_inflow_q, pe, cost_center=cost_center, department=department, project=project
	)
	op_inflow = op_inflow_q.run(as_dict=True)
	operating_inflow = flt(op_inflow[0].total) if op_inflow else 0

	# Operating: cash paid to suppliers
	op_outflow_q = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Pay")
		.where(pe.party_type == "Supplier")
		.where(pe.posting_date >= from_date)
		.where(pe.posting_date <= to_date)
	)
	op_outflow_q = _apply_company_filter(op_outflow_q, pe, company)
	op_outflow_q = apply_dimension_filters(
		op_outflow_q, pe, cost_center=cost_center, department=department, project=project
	)
	op_outflow = op_outflow_q.run(as_dict=True)
	operating_outflow = flt(op_outflow[0].total) if op_outflow else 0

	# Other receipts (non-customer Receive)
	other_inflow_q = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Receive")
		.where((pe.party_type != "Customer") | (pe.party_type.isnull()))
		.where(pe.posting_date >= from_date)
		.where(pe.posting_date <= to_date)
	)
	other_inflow_q = _apply_company_filter(other_inflow_q, pe, company)
	other_inflow_q = apply_dimension_filters(
		other_inflow_q, pe, cost_center=cost_center, department=department, project=project
	)
	other_inflow = other_inflow_q.run(as_dict=True)
	financing_inflow = flt(other_inflow[0].total) if other_inflow else 0

	# Other payments (non-supplier Pay)
	other_outflow_q = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Pay")
		.where((pe.party_type != "Supplier") | (pe.party_type.isnull()))
		.where(pe.posting_date >= from_date)
		.where(pe.posting_date <= to_date)
	)
	other_outflow_q = _apply_company_filter(other_outflow_q, pe, company)
	other_outflow_q = apply_dimension_filters(
		other_outflow_q, pe, cost_center=cost_center, department=department, project=project
	)
	other_outflow = other_outflow_q.run(as_dict=True)
	financing_outflow = flt(other_outflow[0].total) if other_outflow else 0

	operating_net = operating_inflow - operating_outflow
	financing_net = financing_inflow - financing_outflow
	total_net = operating_net + financing_net

	result = {
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
	return build_currency_response(result, _primary(company))


@register_tool(
	name="get_cash_flow_trend",
	category="finance",
	description="Get monthly cash flow trend showing inflow, outflow, and net cash flow over time",
	parameters={
		"months": {"type": "integer", "description": "Number of months to analyze (default 12)"},
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
def get_cash_flow_trend(months=12, company=None, cost_center=None, department=None, project=None):
	"""Get monthly inflow/outflow/net trend from Payment Entry."""
	company = get_company_filter(company)

	pe = frappe.qb.DocType("Payment Entry")
	start_date = get_first_day(add_months(nowdate(), -months + 1))
	end_date = get_last_day(nowdate())
	month_expr = fn.DateFormat(pe.posting_date, "%Y-%m")

	# Inflow by month
	inflow_q = (
		frappe.qb.from_(pe)
		.select(
			month_expr.as_("month"),
			fn.Sum(pe.base_paid_amount).as_("total"),
		)
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Receive")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
	)
	inflow_q = _apply_company_filter(inflow_q, pe, company)
	inflow_q = apply_dimension_filters(
		inflow_q, pe, cost_center=cost_center, department=department, project=project
	)
	inflow_data = inflow_q.groupby(month_expr).orderby(month_expr).run(as_dict=True)

	# Outflow by month
	outflow_q = (
		frappe.qb.from_(pe)
		.select(
			month_expr.as_("month"),
			fn.Sum(pe.base_paid_amount).as_("total"),
		)
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Pay")
		.where(pe.posting_date >= start_date)
		.where(pe.posting_date <= end_date)
	)
	outflow_q = _apply_company_filter(outflow_q, pe, company)
	outflow_q = apply_dimension_filters(
		outflow_q, pe, cost_center=cost_center, department=department, project=project
	)
	outflow_data = outflow_q.groupby(month_expr).orderby(month_expr).run(as_dict=True)

	# Build lookup dicts
	inflow_map = {r.month: flt(r.total) for r in inflow_data}
	outflow_map = {r.month: flt(r.total) for r in outflow_data}

	# Collect all months
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

	# Build chart
	categories = [m["month"] for m in monthly]
	series_list = [
		{"name": "Inflow", "data": [m["inflow"] for m in monthly]},
		{"name": "Outflow", "data": [m["outflow"] for m in monthly]},
		{"name": "Net", "data": [m["net"] for m in monthly]},
	]

	result = {
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
	return build_currency_response(result, _primary(company))


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
		return build_currency_response(result, _primary(company))

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
	return build_currency_response(result, _primary(company))
