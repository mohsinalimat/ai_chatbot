"""
Budget Analysis Tools
Budget vs actual comparison and variance analysis for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.data.charts import build_multi_series_chart
from ai_chatbot.data.currency import build_currency_response
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


@register_tool(
	name="get_budget_vs_actual",
	category="finance",
	description="Compare budgeted amounts vs actual spending by account for a fiscal year",
	parameters={
		"fiscal_year": {
			"type": "string",
			"description": "Fiscal year name (e.g. '2025-2026'). Optional — omit to use current fiscal year.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center name"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
)
def get_budget_vs_actual(fiscal_year=None, cost_center=None, company=None):
	"""Compare budget vs actual from Budget doctype and GL Entry."""
	company = get_default_company(company)

	if not fiscal_year:
		fiscal_year = _get_current_fiscal_year(company)
		if not fiscal_year:
			result = {
				"items": [],
				"totals": {"budget": 0, "actual": 0, "variance": 0},
				"message": "No fiscal year configured. Please specify a fiscal year.",
			}
			return build_currency_response(result, company)

	# Get fiscal year dates for GL query
	fy_from, fy_to = get_fiscal_year_dates(company)

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
		.where(budget.company == company)
		.where(budget.docstatus == 1)
		.groupby(budget_acct.account)
	)

	if cost_center:
		budget_query = budget_query.where(budget.cost_center == cost_center)

	budget_data = budget_query.run(as_dict=True)

	if not budget_data:
		result = {
			"items": [],
			"totals": {"budget": 0, "actual": 0, "variance": 0},
			"fiscal_year": fiscal_year,
			"message": "No budgets found for this fiscal year.",
		}
		return build_currency_response(result, company)

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
		.where(gle.company == company)
		.where(gle.account.isin(budget_accounts))
		.where(gle.posting_date >= fy_from)
		.where(gle.posting_date <= fy_to)
		.where(gle.is_cancelled == 0)
		.groupby(gle.account)
	)

	if cost_center:
		actual_query = actual_query.where(gle.cost_center == cost_center)

	actual_data = actual_query.run(as_dict=True)

	# For expense accounts, actual = debit - credit
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

		items.append({
			"account": account,
			"budget": b,
			"actual": a,
			"variance": variance,
			"variance_pct": variance_pct,
		})
		total_budget += b
		total_actual += a

	total_variance = flt(total_budget - total_actual, 2)
	total_variance_pct = flt((total_variance / total_budget) * 100, 1) if total_budget else 0

	# Build chart — top 10 accounts by budget for readability
	chart_items = sorted(items, key=lambda x: x["budget"], reverse=True)[:10]
	categories = [i["account"].split(" - ")[0] for i in chart_items]  # strip company suffix
	series_list = [
		{"name": "Budget", "data": [i["budget"] for i in chart_items]},
		{"name": "Actual", "data": [i["actual"] for i in chart_items]},
	]

	result = {
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
	return build_currency_response(result, company)


@register_tool(
	name="get_budget_variance",
	category="finance",
	description="Get detailed budget variance analysis with monthly breakdown for a specific account",
	parameters={
		"fiscal_year": {
			"type": "string",
			"description": "Fiscal year name (e.g. '2025-2026'). Optional — omit to use current fiscal year.",
		},
		"account": {"type": "string", "description": "Filter by specific account name"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
)
def get_budget_variance(fiscal_year=None, account=None, company=None):
	"""Get monthly budget vs actual variance for specific accounts."""
	company = get_default_company(company)

	if not fiscal_year:
		fiscal_year = _get_current_fiscal_year(company)
		if not fiscal_year:
			result = {
				"monthly": [],
				"message": "No fiscal year configured.",
			}
			return build_currency_response(result, company)

	fy_from, fy_to = get_fiscal_year_dates(company)

	# Get total budget for the account(s)
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
		.where(budget.company == company)
		.where(budget.docstatus == 1)
		.groupby(budget_acct.account)
	)

	if account:
		budget_query = budget_query.where(budget_acct.account == account)

	budget_data = budget_query.run(as_dict=True)

	if not budget_data:
		result = {
			"monthly": [],
			"fiscal_year": fiscal_year,
			"account": account,
			"message": "No budget data found.",
		}
		return build_currency_response(result, company)

	budget_accounts = [b.account for b in budget_data]
	# Spread annual budget evenly across 12 months (simplified)
	total_annual_budget = sum(flt(b.budget_amount) for b in budget_data)
	monthly_budget = flt(total_annual_budget / 12, 2)

	# Get monthly actuals from GL Entry
	gle = frappe.qb.DocType("GL Entry")
	month_expr = fn.DateFormat(gle.posting_date, "%Y-%m")

	actual_query = (
		frappe.qb.from_(gle)
		.select(
			month_expr.as_("month"),
			(fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("actual"),
		)
		.where(gle.company == company)
		.where(gle.account.isin(budget_accounts))
		.where(gle.posting_date >= fy_from)
		.where(gle.posting_date <= fy_to)
		.where(gle.is_cancelled == 0)
		.groupby(month_expr)
		.orderby(month_expr)
		.run(as_dict=True)
	)

	actual_map = {a.month: flt(a.actual, 2) for a in actual_query}

	# Build monthly breakdown
	monthly = []
	all_months = sorted(set(list(actual_map.keys())))

	for m in all_months:
		actual = actual_map.get(m, 0)
		variance = flt(monthly_budget - actual, 2)
		monthly.append({
			"month": m,
			"budget": monthly_budget,
			"actual": flt(actual, 2),
			"variance": variance,
		})

	# Build chart
	categories = [m["month"] for m in monthly]
	series_list = [
		{"name": "Budget", "data": [m["budget"] for m in monthly]},
		{"name": "Actual", "data": [m["actual"] for m in monthly]},
	]

	display_account = account or "All Budgeted Accounts"

	result = {
		"monthly": monthly,
		"fiscal_year": fiscal_year,
		"account": display_account,
		"annual_budget": flt(total_annual_budget, 2),
		"echart_option": build_multi_series_chart(
			title=f"Budget vs Actual — Monthly",
			categories=categories,
			series_list=series_list,
			y_axis_name="Amount",
			chart_type="line",
		),
	}
	return build_currency_response(result, company)
