# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Working Capital Analysis Tools
Working capital summary and cash conversion cycle for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import date_diff, flt

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.finance.common import apply_company_filter, primary
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_working_capital_summary",
	category="finance",
	description="Get working capital summary: receivables, payables, inventory, and net working capital",
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Sales Invoice", "Purchase Invoice"],
)
def get_working_capital_summary(company=None):
	"""Working Capital = Receivables + Inventory - Payables."""
	company = get_company_filter(company)

	# Total receivables (outstanding Sales Invoices)
	si = frappe.qb.DocType("Sales Invoice")
	recv_q = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.outstanding_amount).as_("total"))
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
	)
	recv_q = apply_company_filter(recv_q, si, company)
	recv_result = recv_q.run(as_dict=True)
	receivables = flt(recv_result[0].total) if recv_result else 0

	# Total payables (outstanding Purchase Invoices)
	pi = frappe.qb.DocType("Purchase Invoice")
	pay_q = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.outstanding_amount).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.outstanding_amount > 0)
	)
	pay_q = apply_company_filter(pay_q, pi, company)
	pay_result = pay_q.run(as_dict=True)
	payables = flt(pay_result[0].total) if pay_result else 0

	# Total inventory value
	bin_table = frappe.qb.DocType("Bin")
	wh_table = frappe.qb.DocType("Warehouse")

	inv_q = (
		frappe.qb.from_(bin_table)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.select(fn.Sum(bin_table.stock_value).as_("total"))
	)
	if isinstance(company, list):
		inv_q = inv_q.where(wh_table.company.isin(company))
	else:
		inv_q = inv_q.where(wh_table.company == company)
	inv_result = inv_q.run(as_dict=True)
	inventory = flt(inv_result[0].total) if inv_result else 0

	current_assets = receivables + inventory
	current_liabilities = payables
	net_working_capital = current_assets - current_liabilities

	result = {
		"receivables": flt(receivables, 2),
		"inventory_value": flt(inventory, 2),
		"current_assets": flt(current_assets, 2),
		"payables": flt(payables, 2),
		"current_liabilities": flt(current_liabilities, 2),
		"net_working_capital": flt(net_working_capital, 2),
	}
	return build_currency_response(result, primary(company))


@register_tool(
	name="get_cash_conversion_cycle",
	category="finance",
	description="Calculate the cash conversion cycle (CCC = DSO + DIO - DPO) for a period",
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
	},
	doctypes=["Sales Invoice", "Purchase Invoice"],
)
def get_cash_conversion_cycle(from_date=None, to_date=None, company=None):
	"""Calculate CCC = DSO + DIO - DPO."""
	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	days_in_period = max(1, date_diff(to_date, from_date))

	# Revenue (Sales Invoice base_grand_total)
	si = frappe.qb.DocType("Sales Invoice")
	rev_q = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
	)
	rev_q = apply_company_filter(rev_q, si, company)
	rev_result = rev_q.run(as_dict=True)
	revenue = flt(rev_result[0].total) if rev_result else 0

	# Use total outstanding as approximation for average receivables
	recv_q = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.outstanding_amount).as_("total"))
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
	)
	recv_q = apply_company_filter(recv_q, si, company)
	recv_total = recv_q.run(as_dict=True)
	avg_receivables = flt(recv_total[0].total) if recv_total else 0

	# COGS approximation (Purchase Invoice base_grand_total)
	pi = frappe.qb.DocType("Purchase Invoice")
	cogs_q = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
	)
	cogs_q = apply_company_filter(cogs_q, pi, company)
	cogs_result = cogs_q.run(as_dict=True)
	cogs = flt(cogs_result[0].total) if cogs_result else 0

	# Average inventory
	bin_table = frappe.qb.DocType("Bin")
	wh_table = frappe.qb.DocType("Warehouse")
	inv_q = (
		frappe.qb.from_(bin_table)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.select(fn.Sum(bin_table.stock_value).as_("total"))
	)
	if isinstance(company, list):
		inv_q = inv_q.where(wh_table.company.isin(company))
	else:
		inv_q = inv_q.where(wh_table.company == company)
	inv_result = inv_q.run(as_dict=True)
	avg_inventory = flt(inv_result[0].total) if inv_result else 0

	# Average payables
	pay_q = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.outstanding_amount).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.outstanding_amount > 0)
	)
	pay_q = apply_company_filter(pay_q, pi, company)
	pay_result = pay_q.run(as_dict=True)
	avg_payables = flt(pay_result[0].total) if pay_result else 0

	# DSO = (Avg Receivables / Revenue) * Days
	dso = flt((avg_receivables / revenue) * days_in_period, 1) if revenue else 0

	# DIO = (Avg Inventory / COGS) * Days
	dio = flt((avg_inventory / cogs) * days_in_period, 1) if cogs else 0

	# DPO = (Avg Payables / COGS) * Days
	dpo = flt((avg_payables / cogs) * days_in_period, 1) if cogs else 0

	# CCC = DSO + DIO - DPO
	ccc = flt(dso + dio - dpo, 1)

	result = {
		"dso": dso,
		"dio": dio,
		"dpo": dpo,
		"cash_conversion_cycle": ccc,
		"days_in_period": days_in_period,
		"period": {"from": from_date, "to": to_date},
		"components": {
			"avg_receivables": flt(avg_receivables, 2),
			"avg_inventory": flt(avg_inventory, 2),
			"avg_payables": flt(avg_payables, 2),
			"revenue": flt(revenue, 2),
			"cogs": flt(cogs, 2),
		},
	}
	return build_currency_response(result, primary(company))
