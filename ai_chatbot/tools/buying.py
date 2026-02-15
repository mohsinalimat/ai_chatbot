"""
Buying Tools Module
Purchase and supplier management tools for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.data.analytics import get_time_series
from ai_chatbot.data.charts import build_bar_chart, build_line_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_purchase_analytics",
	category="buying",
	description="Get purchase analytics including spending, orders, and supplier performance",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_purchase_analytics(from_date=None, to_date=None, company=None):
	"""Get purchase analytics with multi-company and base currency support."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	list_filters = [["docstatus", "=", 1], ["company", "=", company]]
	if from_date:
		list_filters.append(["posting_date", ">=", from_date])
	if to_date:
		list_filters.append(["posting_date", "<=", to_date])

	invoices = frappe.get_all(
		"Purchase Invoice",
		filters=list_filters,
		fields=["base_grand_total"],
	)

	total_spending = sum(flt(inv.base_grand_total) for inv in invoices)
	invoice_count = len(invoices)

	result = {
		"total_spending": total_spending,
		"invoice_count": invoice_count,
		"average_order_value": total_spending / invoice_count if invoice_count else 0,
		"period": {"from": from_date, "to": to_date},
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_supplier_performance",
	category="buying",
	description="Analyze supplier performance metrics",
	parameters={
		"supplier": {"type": "string", "description": "Supplier name"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_supplier_performance(supplier=None, company=None):
	"""Get supplier performance metrics with multi-company support."""
	company = get_default_company(company)

	filters = {"docstatus": 1, "company": company}
	if supplier:
		filters["supplier"] = supplier

	purchases = frappe.get_all(
		"Purchase Order",
		filters=filters,
		fields=["supplier", "base_grand_total", "status", "transaction_date"],
	)

	total_value = sum(flt(p.base_grand_total) for p in purchases)

	result = {
		"total_orders": len(purchases),
		"total_value": total_value,
		"supplier": supplier,
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_purchase_trend",
	category="buying",
	description="Get monthly purchase spending trend over time",
	parameters={
		"months": {"type": "integer", "description": "Number of months to show (default 12)"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_purchase_trend(months=12, company=None):
	"""Monthly spending time series from Purchase Invoice."""
	company = get_default_company(company)

	data = get_time_series(
		doctype="Purchase Invoice",
		value_field="base_grand_total",
		date_field="posting_date",
		filters={"docstatus": 1},
		company=company,
		months=months,
	)

	total_spending = sum(flt(d.get("total", 0)) for d in data)
	categories = [d["month"] for d in data]
	values = [flt(d["total"], 2) for d in data]

	result = {
		"months": [
			{"month": d["month"], "spending": flt(d["total"], 2), "invoice_count": d.get("count", 0)}
			for d in data
		],
		"total_spending": flt(total_spending, 2),
		"period_months": months,
		"echart_option": build_line_chart(
			title="Monthly Purchase Spending",
			categories=categories,
			series_data=values,
			y_axis_name="Spending",
			series_name="Spending",
		),
	}
	return build_currency_response(result, company)


@register_tool(
	name="get_purchase_by_item_group",
	category="buying",
	description="Get purchase breakdown by item group/product category",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"limit": {"type": "integer", "description": "Number of item groups to return (default 10)"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_purchase_by_item_group(from_date=None, to_date=None, limit=10, company=None):
	"""Purchases grouped by item_group from Purchase Invoice Item."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	pi = frappe.qb.DocType("Purchase Invoice")
	pii = frappe.qb.DocType("Purchase Invoice Item")

	rows = (
		frappe.qb.from_(pii)
		.join(pi)
		.on(pii.parent == pi.name)
		.select(
			pii.item_group,
			fn.Sum(pii.base_amount).as_("total_amount"),
			fn.Sum(pii.qty).as_("total_qty"),
			fn.Count("*").as_("line_count"),
		)
		.where(pi.docstatus == 1)
		.where(pi.company == company)
		.where(pi.posting_date >= from_date)
		.where(pi.posting_date <= to_date)
		.groupby(pii.item_group)
		.orderby(fn.Sum(pii.base_amount), order=frappe.qb.desc)
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
			title="Purchases by Item Group",
			categories=categories,
			series_data=values,
			y_axis_name="Amount",
			series_name="Purchases",
		),
	}
	return build_currency_response(result, company)
