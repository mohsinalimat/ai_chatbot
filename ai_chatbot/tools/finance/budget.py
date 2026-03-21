# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Budget Analysis Tools
Unified budget vs actual comparison and variance analysis for AI Chatbot.

Phase 11D: Merged get_budget_vs_actual and get_budget_variance into
a single get_budget_analysis tool.
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_multi_series_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.finance.common import apply_company_filter, primary
from ai_chatbot.tools.registry import register_tool


def _get_current_fiscal_year(company):
	"""Get the current fiscal year name for a company."""
	try:
		from erpnext.accounts.utils import get_fiscal_year
		from frappe.utils import nowdate

		fy = get_fiscal_year(date=nowdate(), company=company)
		return fy[0]  # fiscal year name
	except Exception:
		return None


def _budget_vs_actual(fiscal_year, company, cost_center, department, project):
	"""Compare budget vs actual by account for a fiscal year (summary view)."""
	fy_from, fy_to = get_fiscal_year_dates(primary(company))

	# Get budget amounts from Budget Account child table
	budget = frappe.qb.DocType("Budget")
	budget_acct = frappe.qb.DocType("Budget Account")

	budget_query = (
		frappe.qb.from_(budget)
		.join(budget_acct)
		.on(budget.name == budget_acct.parent)
		.select(
			budget_acct.account,
			fn.Sum(budget_acct.budget_amount).as_("budget_amount"),
		)
		.where(budget.fiscal_year == fiscal_year)
		.where(budget.docstatus == 1)
		.groupby(budget_acct.account)
	)
	budget_query = apply_company_filter(budget_query, budget, company)
	budget_query = apply_dimension_filters(
		budget_query, budget, cost_center=cost_center, department=department, project=project
	)
	budget_data = budget_query.run(as_dict=True)

	if not budget_data:
		return {
			"view": "summary",
			"items": [],
			"totals": {"budget": 0, "actual": 0, "variance": 0},
			"fiscal_year": fiscal_year,
			"message": "No budgets found for this fiscal year.",
		}

	budget_accounts = [b.account for b in budget_data]
	budget_map = {b.account: flt(b.budget_amount) for b in budget_data}

	# Get actual amounts from GL Entry
	gle = frappe.qb.DocType("GL Entry")

	actual_query = (
		frappe.qb.from_(gle)
		.select(
			gle.account,
			fn.Sum(gle.debit).as_("total_debit"),
			fn.Sum(gle.credit).as_("total_credit"),
		)
		.where(gle.account.isin(budget_accounts))
		.where(gle.posting_date >= fy_from)
		.where(gle.posting_date <= fy_to)
		.where(gle.is_cancelled == 0)
		.groupby(gle.account)
	)
	actual_query = apply_company_filter(actual_query, gle, company)
	actual_query = apply_dimension_filters(
		actual_query, gle, cost_center=cost_center, department=department, project=project
	)
	actual_data = actual_query.run(as_dict=True)

	actual_map = {a.account: flt(a.total_debit) - flt(a.total_credit) for a in actual_data}

	# Build comparison
	items = []
	total_budget = 0.0
	total_actual = 0.0

	for account in sorted(budget_accounts):
		b = flt(budget_map.get(account, 0), 2)
		a = flt(actual_map.get(account, 0), 2)
		variance = flt(b - a, 2)
		variance_pct = flt((variance / b) * 100, 1) if b else 0

		items.append(
			{
				"account": account,
				"budget": b,
				"actual": a,
				"variance": variance,
				"variance_pct": variance_pct,
			}
		)
		total_budget += b
		total_actual += a

	total_variance = flt(total_budget - total_actual, 2)
	total_variance_pct = flt((total_variance / total_budget) * 100, 1) if total_budget else 0

	# Chart — top 10 accounts by budget for readability
	chart_items = sorted(items, key=lambda x: x["budget"], reverse=True)[:10]
	categories = [i["account"].split(" - ")[0] for i in chart_items]
	series_list = [
		{"name": "Budget", "data": [i["budget"] for i in chart_items]},
		{"name": "Actual", "data": [i["actual"] for i in chart_items]},
	]

	return {
		"view": "summary",
		"items": items,
		"totals": {
			"budget": flt(total_budget, 2),
			"actual": flt(total_actual, 2),
			"variance": total_variance,
			"variance_pct": total_variance_pct,
		},
		"fiscal_year": fiscal_year,
		"cost_center": cost_center,
		"echart_option": build_multi_series_chart(
			title=f"Budget vs Actual — {fiscal_year}",
			categories=categories,
			series_list=series_list,
			y_axis_name="Amount",
			chart_type="bar",
		),
	}


def _budget_monthly_variance(fiscal_year, account, company, cost_center, department, project):
	"""Monthly budget vs actual variance breakdown (detail view)."""
	fy_from, fy_to = get_fiscal_year_dates(primary(company))

	budget = frappe.qb.DocType("Budget")
	budget_acct = frappe.qb.DocType("Budget Account")

	budget_query = (
		frappe.qb.from_(budget)
		.join(budget_acct)
		.on(budget.name == budget_acct.parent)
		.select(
			budget_acct.account,
			fn.Sum(budget_acct.budget_amount).as_("budget_amount"),
		)
		.where(budget.fiscal_year == fiscal_year)
		.where(budget.docstatus == 1)
		.groupby(budget_acct.account)
	)
	budget_query = apply_company_filter(budget_query, budget, company)

	if account:
		budget_query = budget_query.where(budget_acct.account == account)

	budget_query = apply_dimension_filters(
		budget_query, budget, cost_center=cost_center, department=department, project=project
	)
	budget_data = budget_query.run(as_dict=True)

	if not budget_data:
		return {
			"view": "monthly",
			"monthly": [],
			"fiscal_year": fiscal_year,
			"account": account,
			"message": "No budget data found.",
		}

	budget_accounts = [b.account for b in budget_data]
	total_annual_budget = sum(flt(b.budget_amount) for b in budget_data)
	monthly_budget = flt(total_annual_budget / 12, 2)

	# Monthly actuals from GL Entry
	gle = frappe.qb.DocType("GL Entry")
	month_expr = fn.DateFormat(gle.posting_date, "%Y-%m")

	actual_q = (
		frappe.qb.from_(gle)
		.select(
			month_expr.as_("month"),
			(fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("actual"),
		)
		.where(gle.account.isin(budget_accounts))
		.where(gle.posting_date >= fy_from)
		.where(gle.posting_date <= fy_to)
		.where(gle.is_cancelled == 0)
	)
	actual_q = apply_company_filter(actual_q, gle, company)
	actual_q = apply_dimension_filters(
		actual_q, gle, cost_center=cost_center, department=department, project=project
	)
	actual_rows = actual_q.groupby(month_expr).orderby(month_expr).run(as_dict=True)

	actual_map = {a.month: flt(a.actual, 2) for a in actual_rows}

	monthly = []
	for m in sorted(actual_map.keys()):
		actual_val = actual_map.get(m, 0)
		variance = flt(monthly_budget - actual_val, 2)
		monthly.append(
			{
				"month": m,
				"budget": monthly_budget,
				"actual": flt(actual_val, 2),
				"variance": variance,
			}
		)

	categories = [m["month"] for m in monthly]
	series_list = [
		{"name": "Budget", "data": [m["budget"] for m in monthly]},
		{"name": "Actual", "data": [m["actual"] for m in monthly]},
	]

	display_account = account or "All Budgeted Accounts"

	return {
		"view": "monthly",
		"monthly": monthly,
		"fiscal_year": fiscal_year,
		"account": display_account,
		"annual_budget": flt(total_annual_budget, 2),
		"echart_option": build_multi_series_chart(
			title="Budget vs Actual — Monthly",
			categories=categories,
			series_list=series_list,
			y_axis_name="Amount",
			chart_type="line",
		),
	}


@register_tool(
	name="get_budget_analysis",
	category="finance",
	description=(
		"Analyze budget vs actual spending. Use view='summary' for overall comparison by account, "
		"or view='monthly' for detailed monthly breakdown with variance tracking."
	),
	parameters={
		"view": {
			"type": "string",
			"description": "Analysis view: 'summary' for by-account comparison, 'monthly' for monthly breakdown",
			"enum": ["summary", "monthly"],
		},
		"fiscal_year": {
			"type": "string",
			"description": "Fiscal year name (e.g. '2025-2026'). Optional — omit to use current fiscal year.",
		},
		"account": {
			"type": "string",
			"description": "Filter by specific account name (used in monthly view)",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center name"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Budget", "GL Entry"],
)
def get_budget_analysis(
	view="summary",
	fiscal_year=None,
	account=None,
	cost_center=None,
	department=None,
	project=None,
	company=None,
):
	"""Unified budget analysis — replaces get_budget_vs_actual and
	get_budget_variance (Phase 11D consolidation).
	"""
	company = get_company_filter(company)

	if not fiscal_year:
		fiscal_year = _get_current_fiscal_year(primary(company))
		if not fiscal_year:
			result = {
				"view": view,
				"items": [] if view == "summary" else None,
				"monthly": [] if view == "monthly" else None,
				"message": "No fiscal year configured. Please specify a fiscal year.",
			}
			return build_currency_response(result, primary(company))

	if view == "monthly":
		result = _budget_monthly_variance(fiscal_year, account, company, cost_center, department, project)
	else:
		result = _budget_vs_actual(fiscal_year, company, cost_center, department, project)

	return build_currency_response(result, primary(company))
