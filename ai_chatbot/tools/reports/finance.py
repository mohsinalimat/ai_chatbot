# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Financial Report Tools (Phase 12B)

Thin wrappers around ERPNext's standard financial report execute() functions.
Each tool maps AI-friendly parameters to ERPNext filter format, calls the
report's execute function directly, and normalizes the result.

Reports covered:
1. General Ledger
2. Accounts Receivable (detail)
3. Accounts Receivable Summary
4. Accounts Payable (detail)
5. Accounts Payable Summary
6. Trial Balance
7. Profit and Loss Statement
8. Balance Sheet
9. Cash Flow Statement
10. Consolidated Financial Statement
11. Consolidated Trial Balance
12. Account Balance
"""

from __future__ import annotations

import frappe
from frappe.utils import nowdate

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.tools.common import primary
from ai_chatbot.tools.registry import register_tool
from ai_chatbot.tools.reports._base import (
	build_financial_filters,
	build_report_response,
	get_fiscal_year_name,
	run_report,
)

# ═══════════════════════════════════════════════════════════════════
# 1. General Ledger
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_general_ledger",
	category="finance",
	description=(
		"Run ERPNext General Ledger report — a detailed view of all accounting "
		"transactions posted to each account. Shows posting date, account, party, "
		"debit, credit, and running balance for every GL Entry. "
		"Use for detailed transaction history of specific accounts or parties."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — defaults to fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — defaults to fiscal year end.",
		},
		"account": {
			"type": "string",
			"description": "Filter by specific account name (e.g. 'Cash - TC', 'Debtors - TC').",
		},
		"party_type": {
			"type": "string",
			"description": "Filter by party type: 'Customer', 'Supplier', 'Employee'.",
		},
		"party": {
			"type": "string",
			"description": "Filter by specific party name.",
		},
	},
	doctypes=["GL Entry"],
)
def report_general_ledger(
	company=None,
	from_date=None,
	to_date=None,
	account=None,
	party_type=None,
	party=None,
):
	"""Run ERPNext General Ledger report."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	filters = {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
	}

	if account:
		filters["account"] = [account]
	if party_type:
		filters["party_type"] = party_type
	if party:
		filters["party"] = [party]

	from erpnext.accounts.report.general_ledger.general_ledger import execute

	result = run_report(execute, filters)
	result["period"] = {"from": from_date, "to": to_date}
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 2. Accounts Receivable (detail)
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_accounts_receivable",
	category="finance",
	description=(
		"Run ERPNext Accounts Receivable report — tracks invoice-wise outstanding "
		"amounts from Customers with aging analysis (0-30, 31-60, 61-90, 90+ days). "
		"Shows each outstanding invoice with amount, due date, and aging bucket. "
		"Use for detailed receivable analysis."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"report_date": {
			"type": "string",
			"description": "Report date (YYYY-MM-DD). Optional — defaults to today.",
		},
		"customer": {
			"type": "string",
			"description": "Filter by specific customer name.",
		},
	},
	doctypes=["Sales Invoice"],
)
def report_accounts_receivable(company=None, report_date=None, customer=None):
	"""Run ERPNext Accounts Receivable report."""
	company = get_default_company(company)
	report_date = report_date or nowdate()

	filters = {
		"company": company,
		"report_date": report_date,
		"ageing_based_on": "Due Date",
		"range1": 30,
		"range2": 60,
		"range3": 90,
		"range4": 120,
	}

	if customer:
		filters["party"] = [customer]

	from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 3. Accounts Receivable Summary
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_accounts_receivable_summary",
	category="finance",
	description=(
		"Run ERPNext Accounts Receivable Summary — shows total outstanding amount "
		"per Customer with aging buckets (0-30, 31-60, 61-90, 90+ days). "
		"A summarized view of receivables grouped by customer. "
		"Use to see which customers owe the most and how overdue they are."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"report_date": {
			"type": "string",
			"description": "Report date (YYYY-MM-DD). Optional — defaults to today.",
		},
		"customer": {
			"type": "string",
			"description": "Filter by specific customer name.",
		},
	},
	doctypes=["Sales Invoice"],
)
def report_accounts_receivable_summary(company=None, report_date=None, customer=None):
	"""Run ERPNext Accounts Receivable Summary report."""
	company = get_default_company(company)
	report_date = report_date or nowdate()

	filters = {
		"company": company,
		"report_date": report_date,
		"ageing_based_on": "Due Date",
		"range1": 30,
		"range2": 60,
		"range3": 90,
		"range4": 120,
	}

	if customer:
		filters["party"] = [customer]

	from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import (
		execute,
	)

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 4. Accounts Payable (detail)
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_accounts_payable",
	category="finance",
	description=(
		"Run ERPNext Accounts Payable report — tracks invoice-wise outstanding "
		"amounts owed to Suppliers with aging analysis (0-30, 31-60, 61-90, 90+ days). "
		"Shows each outstanding bill with amount, due date, and aging bucket. "
		"Use for detailed payable analysis."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"report_date": {
			"type": "string",
			"description": "Report date (YYYY-MM-DD). Optional — defaults to today.",
		},
		"supplier": {
			"type": "string",
			"description": "Filter by specific supplier name.",
		},
	},
	doctypes=["Purchase Invoice"],
)
def report_accounts_payable(company=None, report_date=None, supplier=None):
	"""Run ERPNext Accounts Payable report."""
	company = get_default_company(company)
	report_date = report_date or nowdate()

	filters = {
		"company": company,
		"report_date": report_date,
		"ageing_based_on": "Due Date",
		"range1": 30,
		"range2": 60,
		"range3": 90,
		"range4": 120,
	}

	if supplier:
		filters["party"] = [supplier]

	from erpnext.accounts.report.accounts_payable.accounts_payable import execute

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 5. Accounts Payable Summary
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_accounts_payable_summary",
	category="finance",
	description=(
		"Run ERPNext Accounts Payable Summary — shows total outstanding amount "
		"per Supplier with aging buckets (0-30, 31-60, 61-90, 90+ days). "
		"A summarized view of payables grouped by supplier. "
		"Use to see which suppliers are owed the most and how overdue the bills are."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"report_date": {
			"type": "string",
			"description": "Report date (YYYY-MM-DD). Optional — defaults to today.",
		},
		"supplier": {
			"type": "string",
			"description": "Filter by specific supplier name.",
		},
	},
	doctypes=["Purchase Invoice"],
)
def report_accounts_payable_summary(company=None, report_date=None, supplier=None):
	"""Run ERPNext Accounts Payable Summary report."""
	company = get_default_company(company)
	report_date = report_date or nowdate()

	filters = {
		"company": company,
		"report_date": report_date,
		"ageing_based_on": "Due Date",
		"range1": 30,
		"range2": 60,
		"range3": 90,
		"range4": 120,
	}

	if supplier:
		filters["party"] = [supplier]

	from erpnext.accounts.report.accounts_payable_summary.accounts_payable_summary import (
		execute,
	)

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 6. Trial Balance
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_trial_balance",
	category="finance",
	description=(
		"Run ERPNext Trial Balance report — lists account balances for all accounts "
		"(Ledger and Group) for a reporting period. Shows opening balance, period "
		"debit/credit, and closing balance. The fundamental accounting report to "
		"verify bookkeeping accuracy."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"fiscal_year": {
			"type": "string",
			"description": "Fiscal year name (e.g. '2025-2026'). Optional — defaults to current fiscal year.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — defaults to fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — defaults to fiscal year end.",
		},
		"cost_center": {
			"type": "string",
			"description": "Filter by cost center.",
		},
		"project": {
			"type": "string",
			"description": "Filter by project.",
		},
	},
	doctypes=["GL Entry"],
)
def report_trial_balance(
	company=None,
	fiscal_year=None,
	from_date=None,
	to_date=None,
	cost_center=None,
	project=None,
):
	"""Run ERPNext Trial Balance report."""
	company = get_default_company(company)
	fiscal_year = fiscal_year or get_fiscal_year_name(company)

	filters = {
		"company": company,
		"fiscal_year": fiscal_year,
	}

	if from_date:
		filters["from_date"] = from_date
	if to_date:
		filters["to_date"] = to_date
	if cost_center:
		filters["cost_center"] = cost_center
	if project:
		filters["project"] = project

	from erpnext.accounts.report.trial_balance.trial_balance import execute

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 7. Profit and Loss Statement
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_profit_and_loss",
	category="finance",
	description=(
		"Run ERPNext Profit and Loss Statement — summarizes all revenues and expenses "
		"for a period, showing net profit/loss. Supports monthly, quarterly, half-yearly, "
		"or yearly periodicity for trend analysis. The primary income statement report."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — defaults to fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — defaults to fiscal year end.",
		},
		"periodicity": {
			"type": "string",
			"description": "Period grouping: 'Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'. Default: 'Yearly'.",
		},
		"cost_center": {
			"type": "string",
			"description": "Filter by cost center.",
		},
		"project": {
			"type": "string",
			"description": "Filter by project.",
		},
	},
	doctypes=["GL Entry"],
)
def report_profit_and_loss(
	company=None,
	from_date=None,
	to_date=None,
	periodicity="Yearly",
	cost_center=None,
	project=None,
):
	"""Run ERPNext Profit and Loss Statement."""
	company = get_default_company(company)

	filters = build_financial_filters(
		company=company,
		from_date=from_date,
		to_date=to_date,
		periodicity=periodicity,
		cost_center=cost_center,
		project=project,
	)

	from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
		execute,
	)

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 8. Balance Sheet
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_balance_sheet",
	category="finance",
	description=(
		"Run ERPNext Balance Sheet — states assets, liabilities, and equity at a "
		"particular point in time. Can run across multiple periods to compare values "
		"and analyse financial position over time."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — defaults to fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — defaults to fiscal year end.",
		},
		"periodicity": {
			"type": "string",
			"description": "Period grouping: 'Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'. Default: 'Yearly'.",
		},
		"cost_center": {
			"type": "string",
			"description": "Filter by cost center.",
		},
		"project": {
			"type": "string",
			"description": "Filter by project.",
		},
	},
	doctypes=["GL Entry"],
)
def report_balance_sheet(
	company=None,
	from_date=None,
	to_date=None,
	periodicity="Yearly",
	cost_center=None,
	project=None,
):
	"""Run ERPNext Balance Sheet."""
	company = get_default_company(company)

	filters = build_financial_filters(
		company=company,
		from_date=from_date,
		to_date=to_date,
		periodicity=periodicity,
		cost_center=cost_center,
		project=project,
	)

	from erpnext.accounts.report.balance_sheet.balance_sheet import execute

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 9. Cash Flow Statement
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_cash_flow",
	category="finance",
	description=(
		"Run ERPNext Cash Flow Statement — shows incoming and outgoing cash or "
		"cash-equivalents for a company, based on GL entries. Used to analyse the "
		"liquidity position. Shows operating, investing, and financing activities."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — defaults to fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — defaults to fiscal year end.",
		},
		"periodicity": {
			"type": "string",
			"description": "Period grouping: 'Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'. Default: 'Yearly'.",
		},
	},
	doctypes=["GL Entry"],
)
def report_cash_flow(
	company=None,
	from_date=None,
	to_date=None,
	periodicity="Yearly",
):
	"""Run ERPNext Cash Flow Statement."""
	company = get_default_company(company)

	filters = build_financial_filters(
		company=company,
		from_date=from_date,
		to_date=to_date,
		periodicity=periodicity,
	)

	from erpnext.accounts.report.cash_flow.cash_flow import execute

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 10. Consolidated Financial Statement
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_consolidated_financial_statement",
	category="finance",
	description=(
		"Run ERPNext Consolidated Financial Statement — shows a consolidated view "
		"of Balance Sheet, Profit and Loss, or Cash Flow for a group company by merging "
		"financial statements of all subsidiary companies. Shows balances for each "
		"company and accumulated totals. Use for multi-company/group reporting."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Parent company name. Optional — omit to use user's default company.",
		},
		"report": {
			"type": "string",
			"description": "Report type: 'Profit and Loss Statement', 'Balance Sheet', or 'Cash Flow'. Default: 'Profit and Loss Statement'.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — defaults to fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — defaults to fiscal year end.",
		},
		"periodicity": {
			"type": "string",
			"description": "Period grouping: 'Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'. Default: 'Yearly'.",
		},
		"presentation_currency": {
			"type": "string",
			"description": "Currency for the report (e.g. 'USD'). Optional — defaults to parent company currency.",
		},
	},
	doctypes=["GL Entry", "Company"],
)
def report_consolidated_financial_statement(
	company=None,
	report="Profit and Loss Statement",
	from_date=None,
	to_date=None,
	periodicity="Yearly",
	presentation_currency=None,
):
	"""Run ERPNext Consolidated Financial Statement."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	fy_name = get_fiscal_year_name(company)

	filters = {
		"company": company,
		"filter_based_on": "Date Range",
		"period_start_date": from_date,
		"period_end_date": to_date,
		"from_fiscal_year": fy_name,
		"to_fiscal_year": fy_name,
		"report": report,
	}

	if presentation_currency:
		filters["presentation_currency"] = presentation_currency

	from erpnext.accounts.report.consolidated_financial_statement.consolidated_financial_statement import (
		execute,
	)

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 11. Consolidated Trial Balance
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_consolidated_trial_balance",
	category="finance",
	description=(
		"Run ERPNext Consolidated Trial Balance — shows a consolidated view of "
		"trial balance across selected companies. Useful for group-level accounting "
		"verification across multiple entities."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Parent company name (or comma-separated list of companies). Optional.",
		},
		"fiscal_year": {
			"type": "string",
			"description": "Fiscal year name (e.g. '2025-2026'). Optional — defaults to current.",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional.",
		},
		"presentation_currency": {
			"type": "string",
			"description": "Currency for the report (e.g. 'USD'). Optional.",
		},
	},
	doctypes=["GL Entry", "Company"],
)
def report_consolidated_trial_balance(
	company=None,
	fiscal_year=None,
	from_date=None,
	to_date=None,
	presentation_currency=None,
):
	"""Run ERPNext Consolidated Trial Balance."""
	company = get_default_company(company)
	fiscal_year = fiscal_year or get_fiscal_year_name(company)

	# The consolidated trial balance accepts company as a list
	filters = {
		"company": [company],
		"fiscal_year": fiscal_year,
	}

	if from_date:
		filters["from_date"] = from_date
	if to_date:
		filters["to_date"] = to_date
	if presentation_currency:
		filters["presentation_currency"] = presentation_currency

	from erpnext.accounts.report.consolidated_trial_balance.consolidated_trial_balance import (
		execute,
	)

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 12. Account Balance
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_account_balance",
	category="finance",
	description=(
		"Run ERPNext Account Balance report — shows group account balances of the "
		"company on a specific date in company currency. Useful for a quick snapshot "
		"of account balances by root type or account type."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"report_date": {
			"type": "string",
			"description": "Report date (YYYY-MM-DD). Optional — defaults to today.",
		},
		"root_type": {
			"type": "string",
			"description": "Filter by root type: 'Asset', 'Liability', 'Equity', 'Income', 'Expense'.",
		},
		"account_type": {
			"type": "string",
			"description": "Filter by account type: 'Bank', 'Cash', 'Receivable', 'Payable', etc.",
		},
	},
	doctypes=["GL Entry", "Account"],
)
def report_account_balance(
	company=None,
	report_date=None,
	root_type=None,
	account_type=None,
):
	"""Run ERPNext Account Balance report."""
	company = get_default_company(company)
	report_date = report_date or nowdate()

	filters = {
		"company": company,
		"report_date": report_date,
	}

	if root_type:
		filters["root_type"] = root_type
	if account_type:
		filters["account_type"] = account_type

	from erpnext.accounts.report.account_balance.account_balance import execute

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 13. Financial Ratios
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_financial_ratios",
	category="finance",
	description=(
		"Run ERPNext Financial Ratios report — calculates key financial ratios across "
		"periods. Includes Liquidity Ratios (Current Ratio, Quick Ratio), "
		"Solvency Ratios (Debt Equity, Gross Profit, Net Profit, ROA, ROE), and "
		"Turnover Ratios (Fixed Asset, Debtor, Creditor, Inventory Turnover). "
		"Use for ratio analysis, working capital assessment, and efficiency metrics."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"from_fiscal_year": {
			"type": "string",
			"description": "Start fiscal year name (e.g. '2024-2025'). Optional — defaults to current fiscal year.",
		},
		"to_fiscal_year": {
			"type": "string",
			"description": "End fiscal year name (e.g. '2025-2026'). Optional — defaults to current fiscal year.",
		},
		"periodicity": {
			"type": "string",
			"description": "Period grouping: 'Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'. Default: 'Yearly'.",
		},
	},
	doctypes=["GL Entry", "Account"],
)
def report_financial_ratios(
	company=None,
	from_fiscal_year=None,
	to_fiscal_year=None,
	periodicity="Yearly",
):
	"""Run ERPNext Financial Ratios report."""
	company = get_default_company(company)
	fy_name = from_fiscal_year or get_fiscal_year_name(company)
	to_fy = to_fiscal_year or fy_name

	filters = {
		"company": company,
		"from_fiscal_year": fy_name,
		"to_fiscal_year": to_fy,
		"periodicity": periodicity,
	}

	from erpnext.accounts.report.financial_ratios.financial_ratios import execute

	result = run_report(execute, filters)
	return build_report_response(result, company)


# ═══════════════════════════════════════════════════════════════════
# 14. Budget Variance
# ═══════════════════════════════════════════════════════════════════


@register_tool(
	name="report_budget_variance",
	category="finance",
	description=(
		"Run ERPNext Budget Variance report — compares budgeted amounts against actuals "
		"for each account, grouped by period. Shows budget, actual, and variance for "
		"every budgeted account across the fiscal year. "
		"Use for budget vs actual analysis and spending oversight."
	),
	parameters={
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"fiscal_year": {
			"type": "string",
			"description": "Fiscal year name (e.g. '2025-2026'). Optional — defaults to current fiscal year.",
		},
		"budget_against": {
			"type": "string",
			"description": "Budget dimension: 'Cost Center', 'Department', or 'Project'. Default: 'Cost Center'.",
		},
		"period": {
			"type": "string",
			"description": "Period grouping: 'Monthly', 'Quarterly', 'Half-Yearly', 'Yearly'. Default: 'Yearly'.",
		},
	},
	doctypes=["Budget", "GL Entry"],
)
def report_budget_variance(
	company=None,
	fiscal_year=None,
	budget_against="Cost Center",
	period="Yearly",
):
	"""Run ERPNext Budget Variance report."""
	company = get_default_company(company)
	fiscal_year = fiscal_year or get_fiscal_year_name(company)

	filters = {
		"company": company,
		"fiscal_year": fiscal_year,
		"budget_against": budget_against,
		"period": period,
	}

	from erpnext.accounts.report.budget_variance_report.budget_variance_report import (
		execute,
	)

	result = run_report(execute, filters)
	return build_report_response(result, company)
