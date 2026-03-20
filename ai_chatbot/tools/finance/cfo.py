# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
CFO Reporting Tools
Composite analysis tools that aggregate data from existing finance tools for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import add_months, add_years, flt, get_first_day, get_last_day, nowdate

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_bar_chart, build_multi_series_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


def _primary(company):
	"""Get primary company name (first in list or string as-is)."""
	return company[0] if isinstance(company, list) else company


def _apply_company_filter(query, doctype_ref, company):
	"""Apply single or multi-company filter to a query."""
	if isinstance(company, list):
		return query.where(doctype_ref.company.isin(company))
	return query.where(doctype_ref.company == company)


@register_tool(
	name="get_financial_overview",
	category="finance",
	description=(
		"Get a high-level financial overview with key KPIs and BI metric cards: revenue, COGS, "
		"gross profit, net profit, cash position, accounts receivable, and accounts payable. "
		"Prefer get_cfo_dashboard for comprehensive CFO-level analysis."
	),
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
	doctypes=["Sales Invoice", "Purchase Invoice", "GL Entry", "Account"],
)
def get_financial_overview(from_date=None, to_date=None, company=None):
	"""High-level financial KPIs aggregated from multiple sources."""
	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	# Revenue from Sales Invoices
	si = frappe.qb.DocType("Sales Invoice")
	rev_query = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("total"))
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
	)
	if isinstance(company, list):
		rev_query = rev_query.where(si.company.isin(company))
	else:
		rev_query = rev_query.where(si.company == company)
	rev_result = rev_query.run(as_dict=True)
	revenue = flt(rev_result[0].total) if rev_result else 0

	# COGS from Purchase Invoices
	pi = frappe.qb.DocType("Purchase Invoice")
	cogs_query = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
	)
	if isinstance(company, list):
		cogs_query = cogs_query.where(pi.company.isin(company))
	else:
		cogs_query = cogs_query.where(pi.company == company)
	cogs_result = cogs_query.run(as_dict=True)
	cogs = flt(cogs_result[0].total) if cogs_result else 0

	gross_profit = revenue - cogs
	gross_margin_pct = flt((gross_profit / revenue) * 100, 1) if revenue else 0

	# Accounts Receivable (outstanding)
	recv_query = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.outstanding_amount).as_("total"))
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
	)
	if isinstance(company, list):
		recv_query = recv_query.where(si.company.isin(company))
	else:
		recv_query = recv_query.where(si.company == company)
	recv_result = recv_query.run(as_dict=True)
	receivables = flt(recv_result[0].total) if recv_result else 0

	# Accounts Payable (outstanding)
	pay_query = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.outstanding_amount).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.outstanding_amount > 0)
	)
	if isinstance(company, list):
		pay_query = pay_query.where(pi.company.isin(company))
	else:
		pay_query = pay_query.where(pi.company == company)
	pay_result = pay_query.run(as_dict=True)
	payables = flt(pay_result[0].total) if pay_result else 0

	# Cash position from bank/cash GL accounts
	acc = frappe.qb.DocType("Account")
	gle = frappe.qb.DocType("GL Entry")
	cash_acc_query = (
		frappe.qb.from_(acc)
		.select(acc.name)
		.where(acc.account_type.isin(["Bank", "Cash"]))
		.where(acc.is_group == 0)
	)
	if isinstance(company, list):
		cash_acc_query = cash_acc_query.where(acc.company.isin(company))
	else:
		cash_acc_query = cash_acc_query.where(acc.company == company)
	cash_accounts = cash_acc_query.run(as_list=True)
	cash_account_names = [a[0] for a in cash_accounts] if cash_accounts else []

	cash_position = 0
	if cash_account_names:
		cash_query = (
			frappe.qb.from_(gle)
			.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("balance"))
			.where(gle.account.isin(cash_account_names))
			.where(gle.is_cancelled == 0)
		)
		if isinstance(company, list):
			cash_query = cash_query.where(gle.company.isin(company))
		else:
			cash_query = cash_query.where(gle.company == company)
		cash_result = cash_query.run(as_dict=True)
		cash_position = flt(cash_result[0].balance) if cash_result else 0

	# Build chart — KPI bar chart
	categories = ["Revenue", "COGS", "Gross Profit", "Cash", "AR", "AP"]
	values = [
		flt(revenue, 2),
		flt(cogs, 2),
		flt(gross_profit, 2),
		flt(cash_position, 2),
		flt(receivables, 2),
		flt(payables, 2),
	]

	# BI cards for visual display
	bi_cards = [
		{
			"label": "Revenue",
			"value": flt(revenue, 2),
			"change_pct": None,
			"change_period": None,
			"trend": "up" if revenue > 0 else "flat",
			"icon": "trending-up",
		},
		{
			"label": "Gross Profit",
			"value": flt(gross_profit, 2),
			"change_pct": gross_margin_pct,
			"change_period": "Margin %",
			"trend": "up" if gross_profit > 0 else "down",
			"icon": "bar-chart-3",
		},
		{
			"label": "Cash Position",
			"value": flt(cash_position, 2),
			"change_pct": None,
			"change_period": None,
			"trend": "up" if cash_position > 0 else "down",
			"icon": "wallet",
		},
		{
			"label": "Receivables",
			"value": flt(receivables, 2),
			"change_pct": None,
			"change_period": None,
			"trend": "flat",
			"icon": "arrow-up-right",
		},
		{
			"label": "Payables",
			"value": flt(payables, 2),
			"change_pct": None,
			"change_period": None,
			"trend": "flat",
			"icon": "arrow-down-right",
		},
	]

	result = {
		"bi_cards": bi_cards,
		"revenue": flt(revenue, 2),
		"cogs": flt(cogs, 2),
		"gross_profit": flt(gross_profit, 2),
		"gross_margin_pct": gross_margin_pct,
		"cash_position": flt(cash_position, 2),
		"receivables": flt(receivables, 2),
		"payables": flt(payables, 2),
		"net_working_capital": flt(receivables - payables, 2),
		"period": {"from": from_date, "to": to_date},
		"echart_option": build_bar_chart(
			title="Financial Overview",
			categories=categories,
			series_data=values,
			y_axis_name="Amount",
			series_name="Amount",
		),
	}
	return build_currency_response(result, _primary(company))


@register_tool(
	name="get_cfo_dashboard",
	category="finance",
	description=(
		"Get a comprehensive CFO dashboard with BI metric cards (Revenue, Net Profit, Cash, AR, AP "
		"with YoY comparisons), financial highlights, KPIs (margins, ratios, efficiency metrics), "
		"cash flow summary, receivables/payables aging, and budget variance. "
		"Use this tool when user asks for 'CFO dashboard', 'financial overview', 'financial dashboard', "
		"'show CFO dashboard', or any comprehensive financial summary request."
	),
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
	doctypes=["Sales Invoice", "Purchase Invoice", "GL Entry", "Account", "Budget", "Payment Entry"],
)
def get_cfo_dashboard(from_date=None, to_date=None, company=None):
	"""Comprehensive CFO dashboard aggregating data from multiple finance tools."""
	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	from frappe.utils import date_diff

	days_in_period = max(1, date_diff(to_date, from_date))

	# --- Income Statement Data ---
	si = frappe.qb.DocType("Sales Invoice")
	pi = frappe.qb.DocType("Purchase Invoice")

	rev_query = (
		frappe.qb.from_(si)
		.select(
			fn.Sum(si.base_grand_total).as_("revenue"),
			fn.Count("*").as_("invoice_count"),
		)
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
	)
	rev_query = _apply_company_filter(rev_query, si, company)
	rev_result = rev_query.run(as_dict=True)
	revenue = flt(rev_result[0].revenue) if rev_result else 0
	invoice_count = rev_result[0].invoice_count if rev_result else 0

	cogs_query = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("cogs"))
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
	)
	cogs_query = _apply_company_filter(cogs_query, pi, company)
	cogs_result = cogs_query.run(as_dict=True)
	cogs = flt(cogs_result[0].cogs) if cogs_result else 0

	gross_profit = revenue - cogs
	net_profit = gross_profit  # simplified — expenses beyond COGS not tracked separately

	# --- Receivables ---
	recv_query = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.outstanding_amount).as_("total"))
		.where(si.docstatus == 1)
		.where(si.outstanding_amount > 0)
	)
	recv_query = _apply_company_filter(recv_query, si, company)
	recv_result = recv_query.run(as_dict=True)
	total_receivables = flt(recv_result[0].total) if recv_result else 0

	# --- Payables ---
	pay_query = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.outstanding_amount).as_("total"))
		.where(pi.docstatus == 1)
		.where(pi.outstanding_amount > 0)
	)
	pay_query = _apply_company_filter(pay_query, pi, company)
	pay_result = pay_query.run(as_dict=True)
	total_payables = flt(pay_result[0].total) if pay_result else 0

	# --- Inventory ---
	bin_table = frappe.qb.DocType("Bin")
	wh_table = frappe.qb.DocType("Warehouse")
	inv_query = (
		frappe.qb.from_(bin_table)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.select(fn.Sum(bin_table.stock_value).as_("total"))
	)
	inv_query = _apply_company_filter(inv_query, wh_table, company)
	inv_result = inv_query.run(as_dict=True)
	inventory = flt(inv_result[0].total) if inv_result else 0

	# --- Cash Position ---
	acc = frappe.qb.DocType("Account")
	gle = frappe.qb.DocType("GL Entry")
	cash_acc_query = (
		frappe.qb.from_(acc)
		.select(acc.name)
		.where(acc.account_type.isin(["Bank", "Cash"]))
		.where(acc.is_group == 0)
	)
	cash_acc_query = _apply_company_filter(cash_acc_query, acc, company)
	cash_accounts = cash_acc_query.run(as_list=True)
	cash_account_names = [a[0] for a in cash_accounts] if cash_accounts else []

	cash_position = 0
	if cash_account_names:
		cash_query = (
			frappe.qb.from_(gle)
			.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("balance"))
			.where(gle.account.isin(cash_account_names))
			.where(gle.is_cancelled == 0)
		)
		cash_query = _apply_company_filter(cash_query, gle, company)
		cash_result = cash_query.run(as_dict=True)
		cash_position = flt(cash_result[0].balance) if cash_result else 0

	# --- Total Assets for ROA ---
	asset_query = (
		frappe.qb.from_(gle)
		.join(acc)
		.on(gle.account == acc.name)
		.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("total_assets"))
		.where(acc.root_type == "Asset")
		.where(gle.is_cancelled == 0)
	)
	asset_query = _apply_company_filter(asset_query, gle, company)
	asset_result = asset_query.run(as_dict=True)
	total_assets = flt(asset_result[0].total_assets) if asset_result else 0

	# --- Cash Flow Summary (Payment Entry) ---
	pe = frappe.qb.DocType("Payment Entry")

	cf_in_query = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Receive")
		.where(pe.posting_date >= from_date)
		.where(pe.posting_date <= to_date)
	)
	cf_in_query = _apply_company_filter(cf_in_query, pe, company)
	cf_inflow = cf_in_query.run(as_dict=True)
	cash_inflow = flt(cf_inflow[0].total) if cf_inflow else 0

	cf_out_query = (
		frappe.qb.from_(pe)
		.select(fn.Sum(pe.base_paid_amount).as_("total"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Pay")
		.where(pe.posting_date >= from_date)
		.where(pe.posting_date <= to_date)
	)
	cf_out_query = _apply_company_filter(cf_out_query, pe, company)
	cf_outflow = cf_out_query.run(as_dict=True)
	cash_outflow = flt(cf_outflow[0].total) if cf_outflow else 0

	# --- Budget Summary ---
	budget_summary = _get_budget_summary(_primary(company))

	# --- Calculate KPIs ---
	gross_margin_pct = flt((gross_profit / revenue) * 100, 1) if revenue else 0
	net_margin_pct = flt((net_profit / revenue) * 100, 1) if revenue else 0
	roa_pct = flt((net_profit / total_assets) * 100, 1) if total_assets else 0

	# Liquidity
	current_assets = total_receivables + inventory + cash_position
	current_liabilities = total_payables
	current_ratio = flt(current_assets / current_liabilities, 2) if current_liabilities else 0
	quick_ratio = flt((current_assets - inventory) / current_liabilities, 2) if current_liabilities else 0

	# Efficiency
	dso = flt((total_receivables / revenue) * days_in_period, 1) if revenue else 0
	dio = flt((inventory / cogs) * days_in_period, 1) if cogs else 0
	dpo = flt((total_payables / cogs) * days_in_period, 1) if cogs else 0
	ccc = flt(dso + dio - dpo, 1)
	inventory_turnover = flt(cogs / inventory, 2) if inventory else 0

	# --- Build KPI chart ---
	kpi_categories = ["Gross Margin %", "Net Margin %", "ROA %", "Current Ratio", "Quick Ratio"]
	kpi_values = [gross_margin_pct, net_margin_pct, roa_pct, current_ratio, quick_ratio]

	# --- YoY Comparison for BI Cards ---
	prior_from = str(add_years(from_date, -1))
	prior_to = str(add_years(to_date, -1))

	prev_rev_query = (
		frappe.qb.from_(si)
		.select(fn.Sum(si.base_grand_total).as_("revenue"))
		.where(si.docstatus == 1)
		.where(si.posting_date >= prior_from)
		.where(si.posting_date <= prior_to)
	)
	prev_rev_query = _apply_company_filter(prev_rev_query, si, company)
	prev_rev_result = prev_rev_query.run(as_dict=True)
	prev_revenue = flt(prev_rev_result[0].revenue) if prev_rev_result else 0

	prev_cogs_query = (
		frappe.qb.from_(pi)
		.select(fn.Sum(pi.base_grand_total).as_("cogs"))
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= prior_from)
		.where(pi.posting_date <= prior_to)
	)
	prev_cogs_query = _apply_company_filter(prev_cogs_query, pi, company)
	prev_cogs_result = prev_cogs_query.run(as_dict=True)
	prev_cogs = flt(prev_cogs_result[0].cogs) if prev_cogs_result else 0
	prev_net_profit = prev_revenue - prev_cogs

	rev_yoy = flt(((revenue - prev_revenue) / prev_revenue) * 100, 1) if prev_revenue else None
	profit_yoy = (
		flt(((net_profit - prev_net_profit) / abs(prev_net_profit)) * 100, 1) if prev_net_profit else None
	)

	def _trend(change_pct):
		if change_pct is None:
			return "flat"
		return "up" if change_pct > 0 else ("down" if change_pct < 0 else "flat")

	bi_cards = [
		{
			"label": "Revenue",
			"value": flt(revenue, 2),
			"change_pct": rev_yoy,
			"change_period": "YoY",
			"trend": _trend(rev_yoy),
			"icon": "trending-up",
		},
		{
			"label": "Net Profit",
			"value": flt(net_profit, 2),
			"change_pct": profit_yoy,
			"change_period": "YoY",
			"trend": _trend(profit_yoy),
			"icon": "bar-chart-3",
		},
		{
			"label": "Cash Position",
			"value": flt(cash_position, 2),
			"change_pct": None,
			"change_period": None,
			"trend": "up" if cash_position > 0 else "down",
			"icon": "wallet",
		},
		{
			"label": "AR Outstanding",
			"value": flt(total_receivables, 2),
			"change_pct": None,
			"change_period": None,
			"trend": "flat",
			"icon": "arrow-up-right",
		},
		{
			"label": "AP Outstanding",
			"value": flt(total_payables, 2),
			"change_pct": None,
			"change_period": None,
			"trend": "flat",
			"icon": "arrow-down-right",
		},
	]

	result = {
		"bi_cards": bi_cards,
		"financial_highlights": {
			"revenue": flt(revenue, 2),
			"cogs": flt(cogs, 2),
			"gross_profit": flt(gross_profit, 2),
			"net_profit": flt(net_profit, 2),
			"cash_position": flt(cash_position, 2),
			"total_invoices": invoice_count,
		},
		"kpis": {
			"financial": {
				"gross_margin_pct": gross_margin_pct,
				"net_margin_pct": net_margin_pct,
				"roa_pct": roa_pct,
			},
			"operational": {
				"dso": dso,
				"dio": dio,
				"dpo": dpo,
				"cash_conversion_cycle": ccc,
				"inventory_turnover": inventory_turnover,
			},
			"liquidity": {
				"current_ratio": current_ratio,
				"quick_ratio": quick_ratio,
			},
		},
		"cash_flow": {
			"inflow": flt(cash_inflow, 2),
			"outflow": flt(cash_outflow, 2),
			"net": flt(cash_inflow - cash_outflow, 2),
		},
		"receivables_summary": {
			"total_outstanding": flt(total_receivables, 2),
		},
		"payables_summary": {
			"total_outstanding": flt(total_payables, 2),
		},
		"balance_sheet_snapshot": {
			"current_assets": flt(current_assets, 2),
			"receivables": flt(total_receivables, 2),
			"inventory": flt(inventory, 2),
			"cash": flt(cash_position, 2),
			"current_liabilities": flt(current_liabilities, 2),
			"net_working_capital": flt(current_assets - current_liabilities, 2),
			"total_assets": flt(total_assets, 2),
		},
		"budget_summary": budget_summary,
		"period": {"from": from_date, "to": to_date},
		"echart_option": build_bar_chart(
			title="Financial KPIs",
			categories=kpi_categories,
			series_data=kpi_values,
			y_axis_name="Value",
			series_name="KPI",
		),
	}
	return build_currency_response(result, _primary(company))


def _get_budget_summary(company):
	"""Get budget vs actual summary for the current fiscal year."""
	try:
		from erpnext.accounts.utils import get_fiscal_year

		fy = get_fiscal_year(date=nowdate(), company=company)
		fiscal_year = fy[0]
	except Exception:
		return {"message": "No fiscal year configured"}

	fy_from, fy_to = get_fiscal_year_dates(company)

	budget = frappe.qb.DocType("Budget")
	budget_acct = frappe.qb.DocType("Budget Account")

	budget_result = (
		frappe.qb.from_(budget)
		.join(budget_acct)
		.on(budget.name == budget_acct.parent)
		.select(fn.Sum(budget_acct.budget_amount).as_("total_budget"))
		.where(budget.fiscal_year == fiscal_year)
		.where(budget.company == company)
		.where(budget.docstatus == 1)
		.run(as_dict=True)
	)
	total_budget = flt(budget_result[0].total_budget) if budget_result else 0

	if not total_budget:
		return {"total_budget": 0, "total_actual": 0, "variance": 0, "fiscal_year": fiscal_year}

	# Get budget account names
	budget_accounts = (
		frappe.qb.from_(budget)
		.join(budget_acct)
		.on(budget.name == budget_acct.parent)
		.select(budget_acct.account)
		.where(budget.fiscal_year == fiscal_year)
		.where(budget.company == company)
		.where(budget.docstatus == 1)
		.distinct()
		.run(as_list=True)
	)
	account_names = [a[0] for a in budget_accounts] if budget_accounts else []

	total_actual = 0
	if account_names:
		gle = frappe.qb.DocType("GL Entry")
		actual_result = (
			frappe.qb.from_(gle)
			.select((fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("actual"))
			.where(gle.company == company)
			.where(gle.account.isin(account_names))
			.where(gle.posting_date >= fy_from)
			.where(gle.posting_date <= fy_to)
			.where(gle.is_cancelled == 0)
			.run(as_dict=True)
		)
		total_actual = flt(actual_result[0].actual) if actual_result else 0

	variance = flt(total_budget - total_actual, 2)
	variance_pct = flt((variance / total_budget) * 100, 1) if total_budget else 0

	return {
		"total_budget": flt(total_budget, 2),
		"total_actual": flt(total_actual, 2),
		"variance": variance,
		"variance_pct": variance_pct,
		"fiscal_year": fiscal_year,
	}


@register_tool(
	name="get_monthly_comparison",
	category="finance",
	description=(
		"Get month-over-month comparison of revenue, expenses, and net profit. "
		"Shows monthly amounts and variance (change) from previous month."
	),
	parameters={
		"months": {
			"type": "integer",
			"description": "Number of recent months to compare (default 6, max 12)",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Sales Invoice", "Purchase Invoice"],
)
def get_monthly_comparison(months=6, company=None):
	"""Month-over-month revenue, expenses, and net profit comparison."""
	company = get_company_filter(company)
	months = min(months or 6, 12)

	si = frappe.qb.DocType("Sales Invoice")
	pi = frappe.qb.DocType("Purchase Invoice")

	start_date = get_first_day(add_months(nowdate(), -months + 1))
	end_date = get_last_day(nowdate())

	# Monthly revenue
	si_month = fn.DateFormat(si.posting_date, "%Y-%m")
	rev_query = (
		frappe.qb.from_(si)
		.select(
			si_month.as_("month"),
			fn.Sum(si.base_grand_total).as_("revenue"),
			fn.Count("*").as_("invoice_count"),
		)
		.where(si.docstatus == 1)
		.where(si.posting_date >= start_date)
		.where(si.posting_date <= end_date)
		.groupby(si_month)
		.orderby(si_month)
	)
	rev_query = _apply_company_filter(rev_query, si, company)
	rev_data = rev_query.run(as_dict=True)

	# Monthly expenses
	pi_month = fn.DateFormat(pi.posting_date, "%Y-%m")
	exp_query = (
		frappe.qb.from_(pi)
		.select(
			pi_month.as_("month"),
			fn.Sum(pi.base_grand_total).as_("expenses"),
		)
		.where(pi.docstatus == 1)
		.where(pi.posting_date >= start_date)
		.where(pi.posting_date <= end_date)
		.groupby(pi_month)
		.orderby(pi_month)
	)
	exp_query = _apply_company_filter(exp_query, pi, company)
	exp_data = exp_query.run(as_dict=True)

	rev_map = {r.month: {"revenue": flt(r.revenue), "count": r.invoice_count} for r in rev_data}
	exp_map = {e.month: flt(e.expenses) for e in exp_data}

	all_months = sorted(set(list(rev_map.keys()) + list(exp_map.keys())))

	monthly = []
	prev_revenue = None
	prev_expenses = None
	prev_net = None

	for m in all_months:
		revenue = flt(rev_map.get(m, {}).get("revenue", 0), 2)
		expenses = flt(exp_map.get(m, 0), 2)
		net_profit = flt(revenue - expenses, 2)

		entry = {
			"month": m,
			"revenue": revenue,
			"expenses": expenses,
			"net_profit": net_profit,
			"invoice_count": rev_map.get(m, {}).get("count", 0),
		}

		# MoM variance
		if prev_revenue is not None:
			entry["revenue_change"] = flt(revenue - prev_revenue, 2)
			entry["revenue_change_pct"] = (
				flt(((revenue - prev_revenue) / prev_revenue) * 100, 1) if prev_revenue else 0
			)
			entry["expenses_change"] = flt(expenses - prev_expenses, 2)
			entry["net_profit_change"] = flt(net_profit - prev_net, 2)

		prev_revenue = revenue
		prev_expenses = expenses
		prev_net = net_profit

		monthly.append(entry)

	# Build multi-series chart
	categories = [m["month"] for m in monthly]
	series_list = [
		{"name": "Revenue", "data": [m["revenue"] for m in monthly]},
		{"name": "Expenses", "data": [m["expenses"] for m in monthly]},
		{"name": "Net Profit", "data": [m["net_profit"] for m in monthly]},
	]

	result = {
		"monthly": monthly,
		"period_months": months,
		"period": {"from": str(start_date), "to": str(end_date)},
		"echart_option": build_multi_series_chart(
			title="Monthly Financial Comparison",
			categories=categories,
			series_list=series_list,
			y_axis_name="Amount",
			chart_type="line",
		),
	}
	return build_currency_response(result, _primary(company))
