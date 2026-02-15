"""
Financial Ratio Tools
Liquidity, profitability, and efficiency ratios for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import date_diff, flt, nowdate

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


def _get_current_assets_liabilities(company):
	"""Get current assets and liabilities components for ratio calculations.

	Returns:
		Dict with receivables, inventory, payables, cash_balance.
	"""
	# Receivables
	si = frappe.qb.DocType("Sales Invoice")
	recv_result = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.outstanding_amount).as_("total"))
		.where(si.docstatus == 1)
		.where(si.company == company)
		.where(si.outstanding_amount > 0)
		.run(as_dict=True)
	)
	receivables = flt(recv_result[0].total) if recv_result else 0

	# Payables
	pi = frappe.qb.DocType("Purchase Invoice")
	pay_result = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.outstanding_amount).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.outstanding_amount > 0)
		.run(as_dict=True)
	)
	payables = flt(pay_result[0].total) if pay_result else 0

	# Inventory
	bin_table = frappe.qb.DocType("Bin")
	wh_table = frappe.qb.DocType("Warehouse")
	inv_result = (
		frappe.qb.from_(bin_table)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.select(fn.Sum(bin_table.stock_value).as_("total"))
		.where(wh_table.company == company)
		.run(as_dict=True)
	)
	inventory = flt(inv_result[0].total) if inv_result else 0

	# Cash/Bank balances
	acc = frappe.qb.DocType("Account")
	gle = frappe.qb.DocType("GL Entry")

	cash_accounts = (
		frappe.qb.from_(acc)
		.select(acc.name)
		.where(acc.company == company)
		.where(acc.account_type.isin(["Bank", "Cash"]))
		.where(acc.is_group == 0)
		.run(as_list=True)
	)
	cash_account_names = [a[0] for a in cash_accounts] if cash_accounts else []

	cash_balance = 0
	if cash_account_names:
		cash_result = (
			frappe.qb.from_(gle)
			.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("balance"))
			.where(gle.company == company)
			.where(gle.account.isin(cash_account_names))
			.where(gle.is_cancelled == 0)
			.run(as_dict=True)
		)
		cash_balance = flt(cash_result[0].balance) if cash_result else 0

	return {
		"receivables": receivables,
		"inventory": inventory,
		"payables": payables,
		"cash_balance": cash_balance,
	}


@register_tool(
	name="get_liquidity_ratios",
	category="finance",
	description="Calculate liquidity ratios: current ratio and quick ratio",
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
)
def get_liquidity_ratios(company=None):
	"""Current Ratio = Current Assets / Current Liabilities.
	Quick Ratio = (Current Assets - Inventory) / Current Liabilities.
	"""
	company = get_default_company(company)
	components = _get_current_assets_liabilities(company)

	current_assets = (
		components["receivables"] + components["inventory"] + components["cash_balance"]
	)
	current_liabilities = components["payables"]

	current_ratio = flt(current_assets / current_liabilities, 2) if current_liabilities else 0
	quick_ratio = (
		flt((current_assets - components["inventory"]) / current_liabilities, 2)
		if current_liabilities
		else 0
	)

	result = {
		"current_ratio": current_ratio,
		"quick_ratio": quick_ratio,
		"components": {
			"current_assets": flt(current_assets, 2),
			"receivables": flt(components["receivables"], 2),
			"inventory": flt(components["inventory"], 2),
			"cash_balance": flt(components["cash_balance"], 2),
			"current_liabilities": flt(current_liabilities, 2),
		},
		"as_of": nowdate(),
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_profitability_ratios",
	category="finance",
	description="Calculate profitability ratios: gross margin, net margin, and return on assets (ROA)",
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
)
def get_profitability_ratios(from_date=None, to_date=None, company=None):
	"""Gross Margin, Net Margin, ROA."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	# Revenue
	si = frappe.qb.DocType("Sales Invoice")
	rev_result = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.company == company)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
		.run(as_dict=True)
	)
	revenue = flt(rev_result[0].total) if rev_result else 0

	# COGS (Purchase Invoices as simplified proxy)
	pi = frappe.qb.DocType("Purchase Invoice")
	cogs_result = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
		.run(as_dict=True)
	)
	cogs = flt(cogs_result[0].total) if cogs_result else 0

	gross_profit = revenue - cogs
	net_profit = gross_profit  # simplified — same as gross for now

	gross_margin_pct = flt((gross_profit / revenue) * 100, 1) if revenue else 0
	net_margin_pct = flt((net_profit / revenue) * 100, 1) if revenue else 0

	# Total assets for ROA (sum of debit - credit for Asset root_type accounts)
	gle = frappe.qb.DocType("GL Entry")
	acc = frappe.qb.DocType("Account")

	asset_result = (
		frappe.qb.from_(gle)
		.join(acc)
		.on(gle.account == acc.name)
		.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("total_assets"))
		.where(gle.company == company)
		.where(acc.root_type == "Asset")
		.where(gle.is_cancelled == 0)
		.run(as_dict=True)
	)
	total_assets = flt(asset_result[0].total_assets) if asset_result else 0

	roa_pct = flt((net_profit / total_assets) * 100, 1) if total_assets else 0

	result = {
		"gross_margin_pct": gross_margin_pct,
		"net_margin_pct": net_margin_pct,
		"roa_pct": roa_pct,
		"revenue": flt(revenue, 2),
		"cogs": flt(cogs, 2),
		"gross_profit": flt(gross_profit, 2),
		"net_profit": flt(net_profit, 2),
		"total_assets": flt(total_assets, 2),
		"period": {"from": from_date, "to": to_date},
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_efficiency_ratios",
	category="finance",
	description="Calculate efficiency ratios: inventory turnover, receivable days (DSO), and payable days (DPO)",
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
)
def get_efficiency_ratios(from_date=None, to_date=None, company=None):
	"""Inventory Turnover, Receivable Days (DSO), Payable Days (DPO)."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	days_in_period = max(1, date_diff(to_date, from_date))

	# Revenue
	si = frappe.qb.DocType("Sales Invoice")
	rev_result = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.company == company)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
		.run(as_dict=True)
	)
	revenue = flt(rev_result[0].total) if rev_result else 0

	# COGS
	pi = frappe.qb.DocType("Purchase Invoice")
	cogs_result = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
		.run(as_dict=True)
	)
	cogs = flt(cogs_result[0].total) if cogs_result else 0

	# Average receivables
	recv_result = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.outstanding_amount).as_("total"))
		.where(si.docstatus == 1)
		.where(si.company == company)
		.where(si.outstanding_amount > 0)
		.run(as_dict=True)
	)
	avg_receivables = flt(recv_result[0].total) if recv_result else 0

	# Average inventory
	bin_table = frappe.qb.DocType("Bin")
	wh_table = frappe.qb.DocType("Warehouse")
	inv_result = (
		frappe.qb.from_(bin_table)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.select(fn.Sum(bin_table.stock_value).as_("total"))
		.where(wh_table.company == company)
		.run(as_dict=True)
	)
	avg_inventory = flt(inv_result[0].total) if inv_result else 0

	# Average payables
	pay_result = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.outstanding_amount).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.outstanding_amount > 0)
		.run(as_dict=True)
	)
	avg_payables = flt(pay_result[0].total) if pay_result else 0

	# Inventory Turnover = COGS / Avg Inventory
	inventory_turnover = flt(cogs / avg_inventory, 2) if avg_inventory else 0

	# DSO = (Avg Receivables / Revenue) * Days
	receivable_days = flt((avg_receivables / revenue) * days_in_period, 1) if revenue else 0

	# DPO = (Avg Payables / COGS) * Days
	payable_days = flt((avg_payables / cogs) * days_in_period, 1) if cogs else 0

	result = {
		"inventory_turnover": inventory_turnover,
		"receivable_days": receivable_days,
		"payable_days": payable_days,
		"days_in_period": days_in_period,
		"period": {"from": from_date, "to": to_date},
		"components": {
			"revenue": flt(revenue, 2),
			"cogs": flt(cogs, 2),
			"avg_receivables": flt(avg_receivables, 2),
			"avg_inventory": flt(avg_inventory, 2),
			"avg_payables": flt(avg_payables, 2),
		},
	}
	return build_currency_response(result, company)
