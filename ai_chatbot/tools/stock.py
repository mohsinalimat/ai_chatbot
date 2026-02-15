"""
Stock Tools Module
Inventory and warehouse management tools for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import date_diff, flt, nowdate

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.core.constants import AGING_BUCKETS
from ai_chatbot.data.charts import build_bar_chart, build_multi_series_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_inventory_summary",
	category="inventory",
	description="Get inventory summary including stock levels and valuation",
	parameters={
		"warehouse": {"type": "string", "description": "Filter by warehouse"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_inventory_summary(warehouse=None, company=None):
	"""Get inventory summary using frappe.qb — no raw SQL."""
	company = get_default_company(company)

	bin_table = frappe.qb.DocType("Bin")
	wh_table = frappe.qb.DocType("Warehouse")

	query = (
		frappe.qb.from_(bin_table)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.select(
			fn.Count(bin_table.item_code).distinct().as_("item_count"),
			fn.Sum(bin_table.actual_qty).as_("total_qty"),
			fn.Sum(bin_table.stock_value).as_("total_value"),
		)
		.where(wh_table.company == company)
	)

	if warehouse:
		query = query.where(bin_table.warehouse == warehouse)

	result = query.run(as_dict=True)
	stock = result[0] if result else {"item_count": 0, "total_qty": 0, "total_value": 0}

	data = {
		"unique_items": stock.item_count or 0,
		"total_quantity": flt(stock.total_qty or 0),
		"total_value": flt(stock.total_value or 0),
		"warehouse": warehouse,
	}
	return build_currency_response(data, company)


@register_tool(
	name="get_low_stock_items",
	category="inventory",
	description="Get items with stock below reorder level",
	parameters={
		"limit": {"type": "integer", "description": "Maximum number of items to return (default 50)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_low_stock_items(limit=50, company=None):
	"""Get low stock items using frappe.qb — no raw SQL."""
	company = get_default_company(company)

	bin_table = frappe.qb.DocType("Bin")
	item_table = frappe.qb.DocType("Item")
	reorder_table = frappe.qb.DocType("Item Reorder")
	wh_table = frappe.qb.DocType("Warehouse")

	reorder_level = fn.Coalesce(reorder_table.warehouse_reorder_level, 10)

	query = (
		frappe.qb.from_(bin_table)
		.join(item_table)
		.on(bin_table.item_code == item_table.name)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.left_join(reorder_table)
		.on((bin_table.item_code == reorder_table.parent) & (bin_table.warehouse == reorder_table.warehouse))
		.select(
			bin_table.item_code,
			item_table.item_name,
			bin_table.warehouse,
			bin_table.actual_qty,
			reorder_level.as_("reorder_level"),
		)
		.where(wh_table.company == company)
		.where(bin_table.actual_qty < reorder_level)
		.orderby(bin_table.actual_qty)
		.limit(limit)
	)

	items = query.run(as_dict=True)

	return {
		"low_stock_items": items,
		"count": len(items),
		"company": company,
	}


@register_tool(
	name="get_stock_movement",
	category="inventory",
	description="Get stock movement (in/out quantities) for items over a period",
	parameters={
		"item_code": {"type": "string", "description": "Filter by specific item code"},
		"warehouse": {"type": "string", "description": "Filter by specific warehouse"},
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_stock_movement(item_code=None, warehouse=None, from_date=None, to_date=None, company=None):
	"""Get stock in/out movement from Stock Ledger Entry."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	# Resolve item_name to item_code if needed
	if item_code and not frappe.db.exists("Item", item_code):
		resolved = frappe.db.get_value("Item", {"item_name": ["like", f"%{item_code}%"]}, "name")
		if resolved:
			item_code = resolved

	sle = frappe.qb.DocType("Stock Ledger Entry")
	wh_table = frappe.qb.DocType("Warehouse")

	# If item_code specified, show monthly movement
	if item_code:
		month_expr = fn.DateFormat(sle.posting_date, "%Y-%m")

		query = (
			frappe.qb.from_(sle)
			.join(wh_table)
			.on(sle.warehouse == wh_table.name)
			.select(
				month_expr.as_("month"),
				fn.Sum(
					frappe.qb.terms.Case().when(sle.actual_qty > 0, sle.actual_qty).else_(0)
				).as_("stock_in"),
				fn.Sum(
					frappe.qb.terms.Case().when(sle.actual_qty < 0, fn.Abs(sle.actual_qty)).else_(0)
				).as_("stock_out"),
			)
			.where(sle.is_cancelled == 0)
			.where(wh_table.company == company)
			.where(sle.item_code == item_code)
			.where(sle.posting_date >= from_date)
			.where(sle.posting_date <= to_date)
			.groupby(month_expr)
			.orderby(month_expr)
		)

		if warehouse:
			query = query.where(sle.warehouse == warehouse)

		rows = query.run(as_dict=True)

		movements = [
			{
				"month": r.month,
				"stock_in": flt(r.stock_in),
				"stock_out": flt(r.stock_out),
				"net": flt(r.stock_in) - flt(r.stock_out),
			}
			for r in rows
		]

		categories = [m["month"] for m in movements]
		series_list = [
			{"name": "Stock In", "data": [m["stock_in"] for m in movements]},
			{"name": "Stock Out", "data": [m["stock_out"] for m in movements]},
		]

		total_in = sum(m["stock_in"] for m in movements)
		total_out = sum(m["stock_out"] for m in movements)

		result = {
			"item_code": item_code,
			"movements": movements,
			"total_in": flt(total_in),
			"total_out": flt(total_out),
			"net": flt(total_in - total_out),
			"period": {"from": from_date, "to": to_date},
			"echart_option": build_multi_series_chart(
				title=f"Stock Movement — {item_code}",
				categories=categories,
				series_list=series_list,
				y_axis_name="Qty",
				chart_type="bar",
			),
		}
	else:
		# Summary by item
		query = (
			frappe.qb.from_(sle)
			.join(wh_table)
			.on(sle.warehouse == wh_table.name)
			.select(
				sle.item_code,
				fn.Sum(
					frappe.qb.terms.Case().when(sle.actual_qty > 0, sle.actual_qty).else_(0)
				).as_("stock_in"),
				fn.Sum(
					frappe.qb.terms.Case().when(sle.actual_qty < 0, fn.Abs(sle.actual_qty)).else_(0)
				).as_("stock_out"),
			)
			.where(sle.is_cancelled == 0)
			.where(wh_table.company == company)
			.where(sle.posting_date >= from_date)
			.where(sle.posting_date <= to_date)
			.groupby(sle.item_code)
			.orderby(fn.Sum(fn.Abs(sle.actual_qty)), order=frappe.qb.desc)
			.limit(20)
		)

		if warehouse:
			query = query.where(sle.warehouse == warehouse)

		rows = query.run(as_dict=True)

		movements = [
			{
				"item_code": r.item_code,
				"stock_in": flt(r.stock_in),
				"stock_out": flt(r.stock_out),
				"net": flt(r.stock_in) - flt(r.stock_out),
			}
			for r in rows
		]

		total_in = sum(m["stock_in"] for m in movements)
		total_out = sum(m["stock_out"] for m in movements)

		result = {
			"movements": movements,
			"total_in": flt(total_in),
			"total_out": flt(total_out),
			"net": flt(total_in - total_out),
			"period": {"from": from_date, "to": to_date},
		}

	result["company"] = company
	return result


@register_tool(
	name="get_stock_ageing",
	category="inventory",
	description="Get age of stock in warehouse — how long items have been sitting",
	parameters={
		"warehouse": {"type": "string", "description": "Filter by specific warehouse"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_stock_ageing(warehouse=None, company=None):
	"""Stock age analysis — oldest receipt date per item with positive balance."""
	company = get_default_company(company)
	today = nowdate()

	bin_table = frappe.qb.DocType("Bin")
	wh_table = frappe.qb.DocType("Warehouse")
	sle = frappe.qb.DocType("Stock Ledger Entry")

	# Get items with positive stock
	bin_query = (
		frappe.qb.from_(bin_table)
		.join(wh_table)
		.on(bin_table.warehouse == wh_table.name)
		.select(bin_table.item_code, bin_table.warehouse, bin_table.actual_qty)
		.where(wh_table.company == company)
		.where(bin_table.actual_qty > 0)
	)

	if warehouse:
		bin_query = bin_query.where(bin_table.warehouse == warehouse)

	bins = bin_query.limit(100).run(as_dict=True)

	if not bins:
		result = {
			"items": [],
			"aging_summary": {b["label"]: {"count": 0, "total_qty": 0} for b in AGING_BUCKETS},
			"company": company,
		}
		return result

	# For each item+warehouse, find the oldest positive SLE (first receipt)
	item_ages = []
	for b in bins:
		oldest = (
			frappe.qb.from_(sle)
			.select(fn.Min(sle.posting_date).as_("oldest_date"))
			.where(sle.item_code == b.item_code)
			.where(sle.warehouse == b.warehouse)
			.where(sle.actual_qty > 0)
			.where(sle.is_cancelled == 0)
			.run(as_dict=True)
		)
		oldest_date = oldest[0].oldest_date if oldest and oldest[0].oldest_date else today
		age_days = max(0, date_diff(today, oldest_date))

		# Determine bucket
		bucket = "90+"
		for ab in AGING_BUCKETS:
			if ab["max"] is None:
				if age_days >= ab["min"]:
					bucket = ab["label"]
					break
			elif ab["min"] <= age_days <= ab["max"]:
				bucket = ab["label"]
				break

		item_ages.append({
			"item_code": b.item_code,
			"warehouse": b.warehouse,
			"qty": flt(b.actual_qty),
			"age_days": age_days,
			"bucket": bucket,
		})

	# Build aging summary
	aging_summary = {b["label"]: {"count": 0, "total_qty": 0} for b in AGING_BUCKETS}
	for item in item_ages:
		bucket = item["bucket"]
		if bucket in aging_summary:
			aging_summary[bucket]["count"] += 1
			aging_summary[bucket]["total_qty"] += item["qty"]

	# Chart
	categories = [b["label"] for b in AGING_BUCKETS]
	values = [aging_summary[b["label"]]["total_qty"] for b in AGING_BUCKETS]

	result = {
		"items": sorted(item_ages, key=lambda x: x["age_days"], reverse=True)[:20],
		"aging_summary": aging_summary,
		"total_items": len(item_ages),
		"company": company,
		"echart_option": build_bar_chart(
			title="Stock Aging by Quantity",
			categories=categories,
			series_data=values,
			y_axis_name="Qty",
			series_name="Stock Qty",
		),
	}
	return result
