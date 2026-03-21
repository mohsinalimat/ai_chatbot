# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Profitability Analysis Tools
Unified profitability by customer, item, or territory for AI Chatbot.

Phase 11D: Merged get_profitability_by_customer, get_profitability_by_item,
and get_profitability_by_territory into a single get_profitability tool.
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_fiscal_year_dates, get_top_n_limit
from ai_chatbot.core.dimensions import apply_dimension_filters
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_horizontal_bar, build_pie_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.finance.common import primary
from ai_chatbot.tools.registry import register_tool


def _get_profitability_data(group_field, from_date, to_date, company, limit=None, **dimensions):
	"""Shared query for profitability analysis grouped by a Sales Invoice field.

	Revenue comes from Sales Invoice Item base_amount.
	Cost uses incoming_rate * stock_qty (valuation rate captured on the invoice item,
	populated when perpetual inventory is enabled).

	Args:
		group_field: Field name on Sales Invoice to group by (e.g. "customer", "territory").
		from_date: Start date.
		to_date: End date.
		company: Company name.
		limit: Max rows (None = all).

	Returns:
		List of dicts with group, revenue, cost, margin, margin_pct.
	"""
	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")

	revenue_expr = fn.Sum(sii.base_amount).as_("revenue")
	cost_expr = fn.Sum(sii.incoming_rate * sii.stock_qty).as_("cost")

	query = (
		frappe.qb.from_(sii)
		.join(si)
		.on(sii.parent == si.name)
		.select(
			si[group_field].as_("group_value"),
			revenue_expr,
			cost_expr,
			fn.Count(si.name).distinct().as_("invoice_count"),
		)
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
		.groupby(si[group_field])
		.orderby(revenue_expr, order=frappe.qb.desc)
	)

	if isinstance(company, list):
		query = query.where(si.company.isin(company))
	else:
		query = query.where(si.company == company)

	query = apply_dimension_filters(query, si, **dimensions)

	if limit:
		query = query.limit(limit)

	rows = query.run(as_dict=True)

	results = []
	for r in rows:
		revenue = flt(r.revenue, 2)
		cost = flt(r.cost, 2)
		margin = flt(revenue - cost, 2)
		margin_pct = flt((margin / revenue) * 100, 1) if revenue else 0

		results.append(
			{
				"name": r.group_value or "Unknown",
				"revenue": revenue,
				"cost": cost,
				"margin": margin,
				"margin_pct": margin_pct,
				"invoice_count": r.invoice_count,
			}
		)

	return results


def _get_profitability_by_item(from_date, to_date, company, limit=None, **dimensions):
	"""Profitability query grouped by item_code (uses child table field, not parent)."""
	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")

	revenue_expr = fn.Sum(sii.base_amount).as_("revenue")
	cost_expr = fn.Sum(sii.incoming_rate * sii.stock_qty).as_("cost")

	query = (
		frappe.qb.from_(sii)
		.join(si)
		.on(sii.parent == si.name)
		.select(
			sii.item_code,
			sii.item_name,
			revenue_expr,
			cost_expr,
			fn.Sum(sii.stock_qty).as_("total_qty"),
		)
		.where(si.docstatus == 1)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
	)

	if isinstance(company, list):
		query = query.where(si.company.isin(company))
	else:
		query = query.where(si.company == company)
	query = apply_dimension_filters(query, si, **dimensions)
	rows = (
		query.groupby(sii.item_code, sii.item_name)
		.orderby(revenue_expr, order=frappe.qb.desc)
		.limit(limit)
		.run(as_dict=True)
	)

	items = []
	for r in rows:
		revenue = flt(r.revenue, 2)
		cost = flt(r.cost, 2)
		margin = flt(revenue - cost, 2)
		margin_pct = flt((margin / revenue) * 100, 1) if revenue else 0
		items.append(
			{
				"item_code": r.item_code,
				"item_name": r.item_name,
				"revenue": revenue,
				"cost": cost,
				"margin": margin,
				"margin_pct": margin_pct,
				"total_qty": flt(r.total_qty),
			}
		)

	return items


@register_tool(
	name="get_profitability",
	category="finance",
	description=(
		"Analyze profitability by a chosen dimension — customer, item, or territory. "
		"Shows revenue, cost, and profit margin for each group."
	),
	parameters={
		"dimension": {
			"type": "string",
			"description": "Dimension to group by: 'customer', 'item', or 'territory'",
			"enum": ["customer", "item", "territory"],
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end.",
		},
		"limit": {"type": "integer", "description": "Number of results to return (default 10)"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
		"cost_center": {"type": "string", "description": "Filter by cost center"},
		"department": {"type": "string", "description": "Filter by department"},
		"project": {"type": "string", "description": "Filter by project"},
	},
	doctypes=["Sales Invoice"],
)
def get_profitability(
	dimension="customer",
	from_date=None,
	to_date=None,
	limit=10,
	company=None,
	cost_center=None,
	department=None,
	project=None,
):
	"""Unified profitability analysis — replaces get_profitability_by_customer,
	get_profitability_by_item, and get_profitability_by_territory (Phase 11D).
	"""
	if dimension != "territory":
		limit = get_top_n_limit(limit)
	else:
		limit = None  # territory returns all rows

	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	dim_kwargs = dict(cost_center=cost_center, department=department, project=project)

	if dimension == "item":
		data = _get_profitability_by_item(from_date, to_date, company, limit, **dim_kwargs)
		# Chart — horizontal bar of margins
		item_labels = [i["item_name"] or i["item_code"] for i in reversed(data)]
		margins = [i["margin"] for i in reversed(data)]
		result = {
			"dimension": dimension,
			"items": data,
			"period": {"from": from_date, "to": to_date},
			"echart_option": build_horizontal_bar(
				title="Profitability by Item",
				categories=item_labels,
				series_data=margins,
				x_axis_name="Margin",
				series_name="Profit Margin",
			),
		}
	elif dimension == "territory":
		data = _get_profitability_data("territory", from_date, to_date, company, limit=None, **dim_kwargs)
		pie_data = [{"name": d["name"], "value": d["margin"]} for d in data if d["margin"] > 0]
		result = {
			"dimension": dimension,
			"territories": data,
			"period": {"from": from_date, "to": to_date},
			"echart_option": build_pie_chart(
				title="Profit Margin by Territory",
				data=pie_data,
			),
		}
	else:
		# customer (default)
		data = _get_profitability_data("customer", from_date, to_date, company, limit, **dim_kwargs)
		customers_chart = [d["name"] for d in reversed(data)]
		margins = [d["margin"] for d in reversed(data)]
		result = {
			"dimension": dimension,
			"customers": data,
			"period": {"from": from_date, "to": to_date},
			"echart_option": build_horizontal_bar(
				title="Profitability by Customer",
				categories=customers_chart,
				series_data=margins,
				x_axis_name="Margin",
				series_name="Profit Margin",
			),
		}

	return build_currency_response(result, primary(company))
