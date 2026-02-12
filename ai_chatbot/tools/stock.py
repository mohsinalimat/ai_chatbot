"""
Stock Tools Module
Inventory and warehouse management tools for AI Chatbot
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_default_company
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
