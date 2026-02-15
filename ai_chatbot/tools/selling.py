"""
Selling Tools Module
Sales and customer analytics tools for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.data.analytics import get_grouped_sum, get_time_series
from ai_chatbot.data.charts import build_bar_chart, build_line_chart, build_pie_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_sales_analytics",
	category="selling",
	description="Get sales analytics including revenue, orders, and growth trends",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"customer": {"type": "string", "description": "Filter by customer name"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_sales_analytics(from_date=None, to_date=None, customer=None, company=None):
	"""Get sales analytics with multi-company and base currency support."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	filters = {"docstatus": 1}
	if customer:
		filters["customer"] = customer

	# Build list filters for date range to support both from_date and to_date
	list_filters = [["docstatus", "=", 1], ["company", "=", company]]
	if from_date:
		list_filters.append(["posting_date", ">=", from_date])
	if to_date:
		list_filters.append(["posting_date", "<=", to_date])
	if customer:
		list_filters.append(["customer", "=", customer])

	import frappe

	invoices = frappe.get_all(
		"Sales Invoice",
		filters=list_filters,
		fields=["base_grand_total"],
	)

	total_revenue = sum(flt(inv.base_grand_total) for inv in invoices)
	invoice_count = len(invoices)

	result = {
		"total_revenue": total_revenue,
		"invoice_count": invoice_count,
		"average_order_value": total_revenue / invoice_count if invoice_count else 0,
		"period": {"from": from_date, "to": to_date},
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_top_customers",
	category="selling",
	description="Get top customers by revenue",
	parameters={
		"limit": {"type": "integer", "description": "Number of customers to return (default 10)"},
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_top_customers(limit=10, from_date=None, to_date=None, company=None):
	"""Get top customers by revenue using the analytics data layer (no raw SQL)."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	filters = {"docstatus": 1, "posting_date": ["between", [from_date, to_date]]}

	customers = get_grouped_sum(
		doctype="Sales Invoice",
		sum_field="base_grand_total",
		group_field="customer",
		filters=filters,
		company=company,
		order_by_sum=True,
		limit=limit,
	)

	result = {
		"top_customers": [
			{
				"customer": c.customer,
				"total_revenue": flt(c.total),
				"order_count": c.count,
			}
			for c in customers
		],
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_sales_trend",
	category="selling",
	description="Get monthly sales revenue trend over time",
	parameters={
		"months": {"type": "integer", "description": "Number of months to show (default 12)"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_sales_trend(months=12, company=None):
	"""Monthly revenue time series from Sales Invoice."""
	company = get_default_company(company)

	data = get_time_series(
		doctype="Sales Invoice",
		value_field="base_grand_total",
		date_field="posting_date",
		filters={"docstatus": 1},
		company=company,
		months=months,
	)

	total_revenue = sum(flt(d.get("total", 0)) for d in data)
	categories = [d["month"] for d in data]
	values = [flt(d["total"], 2) for d in data]

	result = {
		"months": [
			{"month": d["month"], "revenue": flt(d["total"], 2), "invoice_count": d.get("count", 0)}
			for d in data
		],
		"total_revenue": flt(total_revenue, 2),
		"period_months": months,
		"echart_option": build_line_chart(
			title="Monthly Sales Revenue",
			categories=categories,
			series_data=values,
			y_axis_name="Revenue",
			series_name="Revenue",
		),
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_sales_by_territory",
	category="selling",
	description="Get sales breakdown by territory/region",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_sales_by_territory(from_date=None, to_date=None, company=None):
	"""Sales grouped by territory from Sales Invoice."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	filters = {"docstatus": 1, "posting_date": ["between", [from_date, to_date]]}

	territories = get_grouped_sum(
		doctype="Sales Invoice",
		sum_field="base_grand_total",
		group_field="territory",
		filters=filters,
		company=company,
		order_by_sum=True,
	)

	territory_data = [
		{
			"territory": t.territory or "Unknown",
			"total_revenue": flt(t.total, 2),
			"invoice_count": t.count,
		}
		for t in territories
	]

	pie_data = [{"name": t["territory"], "value": t["total_revenue"]} for t in territory_data]

	result = {
		"territories": territory_data,
		"period": {"from": from_date, "to": to_date},
		"echart_option": build_pie_chart(
			title="Sales by Territory",
			data=pie_data,
		),
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_sales_by_item_group",
	category="selling",
	description="Get sales breakdown by item group/product category",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"limit": {"type": "integer", "description": "Number of item groups to return (default 10)"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_sales_by_item_group(from_date=None, to_date=None, limit=10, company=None):
	"""Sales grouped by item_group from Sales Invoice Item."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")

	rows = (
		frappe.qb.from_(sii)
		.join(si)
		.on(sii.parent == si.name)
		.select(
			sii.item_group,
			fn.Sum(sii.base_amount).as_("total_amount"),
			fn.Sum(sii.stock_qty).as_("total_qty"),
			fn.Count("*").as_("line_count"),
		)
		.where(si.docstatus == 1)
		.where(si.company == company)
		.where(si.posting_date >= from_date)
		.where(si.posting_date <= to_date)
		.groupby(sii.item_group)
		.orderby(fn.Sum(sii.base_amount), order=frappe.qb.desc)
		.limit(limit)
		.run(as_dict=True)
	)

	item_groups = [
		{
			"item_group": r.item_group or "Unknown",
			"total_amount": flt(r.total_amount, 2),
			"total_qty": flt(r.total_qty),
		}
		for r in rows
	]

	categories = [ig["item_group"] for ig in item_groups]
	values = [ig["total_amount"] for ig in item_groups]

	result = {
		"item_groups": item_groups,
		"period": {"from": from_date, "to": to_date},
		"echart_option": build_bar_chart(
			title="Sales by Item Group",
			categories=categories,
			series_data=values,
			y_axis_name="Amount",
			series_name="Sales",
		),
	}
	return build_currency_response(result, company)
