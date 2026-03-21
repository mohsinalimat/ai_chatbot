# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Financial Ratio Tools
Unified liquidity, profitability, and efficiency ratios for AI Chatbot.

Phase 11D: Merged get_liquidity_ratios, get_profitability_ratios, and
get_efficiency_ratios into a single get_financial_ratios tool.
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import date_diff, flt, nowdate

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.finance.common import apply_company_filter, primary
from ai_chatbot.tools.registry import register_tool


def _get_current_assets_liabilities(company):
	"""Get current assets and liabilities components for ratio calculations.

	Args:
		company: Single company string or list of company strings.

	Returns:
		Dict with receivables, inventory, payables, cash_balance.
	"""
	# Receivables
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

	# Payables
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

	# Inventory
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

	# Cash/Bank balances
	acc = frappe.qb.DocType("Account")
	gle = frappe.qb.DocType("GL Entry")

	acc_q = (
		frappe.qb.from_(acc)
		.select(acc.name)
		.where(acc.account_type.isin(["Bank", "Cash"]))
		.where(acc.is_group == 0)
	)
	if isinstance(company, list):
		acc_q = acc_q.where(acc.company.isin(company))
	else:
		acc_q = acc_q.where(acc.company == company)
	cash_accounts = acc_q.run(as_list=True)
	cash_account_names = [a[0] for a in cash_accounts] if cash_accounts else []

	cash_balance = 0
	if cash_account_names:
		cash_q = (
			frappe.qb.from_(gle)
			.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("balance"))
			.where(gle.account.isin(cash_account_names))
			.where(gle.is_cancelled == 0)
		)
		cash_q = apply_company_filter(cash_q, gle, company)
		cash_result = cash_q.run(as_dict=True)
		cash_balance = flt(cash_result[0].balance) if cash_result else 0

	return {
		"receivables": receivables,
		"inventory": inventory,
		"payables": payables,
		"cash_balance": cash_balance,
	}


def _calc_liquidity(company):
	"""Calculate liquidity ratios: current ratio and quick ratio."""
	components = _get_current_assets_liabilities(company)

	current_assets = components["receivables"] + components["inventory"] + components["cash_balance"]
	current_liabilities = components["payables"]

	current_ratio = flt(current_assets / current_liabilities, 2) if current_liabilities else 0
	quick_ratio = (
		flt((current_assets - components["inventory"]) / current_liabilities, 2) if current_liabilities else 0
	)

	return {
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


def _calc_profitability_ratios(company, from_date, to_date, cost_center, department, project):
	"""Calculate profitability ratios: gross margin, net margin, ROA."""
	# Revenue
	si = frappe.qb.DocType("Sales Invoice")
	rev_q = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
	)
	rev_q = apply_company_filter(rev_q, si, company)
	rev_q = apply_dimension_filters(
		rev_q, si, cost_center=cost_center, department=department, project=project
	)
	rev_result = rev_q.run(as_dict=True)
	revenue = flt(rev_result[0].total) if rev_result else 0

	# COGS (Purchase Invoices as simplified proxy)
	pi = frappe.qb.DocType("Purchase Invoice")
	cogs_q = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
	)
	cogs_q = apply_company_filter(cogs_q, pi, company)
	cogs_q = apply_dimension_filters(
		cogs_q, pi, cost_center=cost_center, department=department, project=project
	)
	cogs_result = cogs_q.run(as_dict=True)
	cogs = flt(cogs_result[0].total) if cogs_result else 0

	gross_profit = revenue - cogs
	net_profit = gross_profit  # simplified — same as gross for now

	gross_margin_pct = flt((gross_profit / revenue) * 100, 1) if revenue else 0
	net_margin_pct = flt((net_profit / revenue) * 100, 1) if revenue else 0

	# Total assets for ROA (sum of debit - credit for Asset root_type accounts)
	gle = frappe.qb.DocType("GL Entry")
	acc = frappe.qb.DocType("Account")

	asset_q = (
		frappe.qb.from_(gle)
		.join(acc)
		.on(gle.account == acc.name)
		.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("total_assets"))
		.where(acc.root_type == "Asset")
		.where(gle.is_cancelled == 0)
	)
	asset_q = apply_company_filter(asset_q, gle, company)
	asset_result = asset_q.run(as_dict=True)
	total_assets = flt(asset_result[0].total_assets) if asset_result else 0

	roa_pct = flt((net_profit / total_assets) * 100, 1) if total_assets else 0

	return {
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


def _calc_efficiency(company, from_date, to_date, cost_center, department, project):
	"""Calculate efficiency ratios: inventory turnover, DSO, DPO."""
	days_in_period = max(1, date_diff(to_date, from_date))

	# Revenue
	si = frappe.qb.DocType("Sales Invoice")
	rev_q = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
	)
	rev_q = apply_company_filter(rev_q, si, company)
	rev_q = apply_dimension_filters(
		rev_q, si, cost_center=cost_center, department=department, project=project
	)
	rev_result = rev_q.run(as_dict=True)
	revenue = flt(rev_result[0].total) if rev_result else 0

	# COGS
	pi = frappe.qb.DocType("Purchase Invoice")
	cogs_q = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
	)
	cogs_q = apply_company_filter(cogs_q, pi, company)
	cogs_q = apply_dimension_filters(
		cogs_q, pi, cost_center=cost_center, department=department, project=project
	)
	cogs_result = cogs_q.run(as_dict=True)
	cogs = flt(cogs_result[0].total) if cogs_result else 0

	# Average receivables
	recv_q = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.outstanding_amount).as_("total"))
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
	)
	recv_q = apply_company_filter(recv_q, si, company)
	recv_q = apply_dimension_filters(
		recv_q, si, cost_center=cost_center, department=department, project=project
	)
	recv_result = recv_q.run(as_dict=True)
	avg_receivables = flt(recv_result[0].total) if recv_result else 0

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
	pay_q = apply_dimension_filters(
		pay_q, pi, cost_center=cost_center, department=department, project=project
	)
	pay_result = pay_q.run(as_dict=True)
	avg_payables = flt(pay_result[0].total) if pay_result else 0

	# Inventory Turnover = COGS / Avg Inventory
	inventory_turnover = flt(cogs / avg_inventory, 2) if avg_inventory else 0

	# DSO = (Avg Receivables / Revenue) * Days
	receivable_days = flt((avg_receivables / revenue) * days_in_period, 1) if revenue else 0

	# DPO = (Avg Payables / COGS) * Days
	payable_days = flt((avg_payables / cogs) * days_in_period, 1) if cogs else 0

	return {
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


@register_tool(
	name="get_financial_ratios",
	category="finance",
	description=(
		"Calculate financial ratios. Use type='liquidity' for current/quick ratio, "
		"type='profitability' for gross margin/net margin/ROA, "
		"type='efficiency' for inventory turnover/DSO/DPO, "
		"or type='all' for a complete set."
	),
	parameters={
		"type": {
			"type": "string",
			"description": "Ratio type: 'liquidity', 'profitability', 'efficiency', or 'all'",
			"enum": ["liquidity", "profitability", "efficiency", "all"],
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start. Not used for liquidity ratios.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end. Not used for liquidity ratios.",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
	},
	doctypes=["Sales Invoice", "Purchase Invoice", "GL Entry"],
)
def get_financial_ratios(
	type="all",
	from_date=None,
	to_date=None,
	company=None,
	cost_center=None,
	department=None,
	project=None,
):
	"""Unified financial ratios — replaces get_liquidity_ratios, get_profitability_ratios,
	and get_efficiency_ratios (Phase 11D consolidation).
	"""
	company = get_company_filter(company)

	# Resolve fiscal year dates for profitability/efficiency calculations
	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	result = {"type": type}

	if type in ("liquidity", "all"):
		result["liquidity"] = _calc_liquidity(company)

	if type in ("profitability", "all"):
		result["profitability"] = _calc_profitability_ratios(
			company, from_date, to_date, cost_center, department, project
		)

	if type in ("efficiency", "all"):
		result["efficiency"] = _calc_efficiency(company, from_date, to_date, cost_center, department, project)

	return build_currency_response(result, primary(company))
