"""
Search Tools Module
Search and lookup tools for AI Chatbot (read-only operations)
"""

import frappe

from ai_chatbot.core.config import get_default_company
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="search_customers",
	category="operations",
	description="Search for customers by name, customer group, or territory. Returns matching customer records.",
	parameters={
		"query": {"type": "string", "description": "Search text to match against customer name"},
		"customer_group": {"type": "string", "description": "Filter by customer group"},
		"territory": {"type": "string", "description": "Filter by territory"},
		"limit": {"type": "integer", "description": "Maximum results to return (default 10)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def search_customers(query=None, customer_group=None, territory=None, limit=10, company=None):
	"""Search customers with fuzzy name matching and optional filters."""
	company = get_default_company(company)

	filters = {}
	or_filters = {}

	if query:
		or_filters = {
			"customer_name": ["like", f"%{query}%"],
			"name": ["like", f"%{query}%"],
		}

	if customer_group:
		filters["customer_group"] = customer_group
	if territory:
		filters["territory"] = territory

	customers = frappe.get_all(
		"Customer",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "customer_name", "customer_group", "territory", "customer_type"],
		limit=limit,
		order_by="customer_name asc",
	)

	return {
		"customers": customers,
		"count": len(customers),
		"company": company,
	}


@register_tool(
	name="search_items",
	category="operations",
	description="Search for items by name, item code, or item group. Returns matching item records.",
	parameters={
		"query": {"type": "string", "description": "Search text to match against item name or code"},
		"item_group": {"type": "string", "description": "Filter by item group"},
		"limit": {"type": "integer", "description": "Maximum results to return (default 10)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def search_items(query=None, item_group=None, limit=10, company=None):
	"""Search items by name, code, or group."""
	company = get_default_company(company)

	filters = {}
	or_filters = {}

	if query:
		or_filters = {
			"item_name": ["like", f"%{query}%"],
			"item_code": ["like", f"%{query}%"],
			"name": ["like", f"%{query}%"],
		}

	if item_group:
		filters["item_group"] = item_group

	items = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_name", "item_code", "item_group", "stock_uom", "is_stock_item"],
		limit=limit,
		order_by="item_name asc",
	)

	return {
		"items": items,
		"count": len(items),
		"company": company,
	}


@register_tool(
	name="search_documents",
	category="operations",
	description="Search for documents of any DocType by name or status. Useful for looking up specific records.",
	parameters={
		"doctype": {
			"type": "string",
			"description": "The DocType to search (e.g. 'Sales Invoice', 'Purchase Order', 'Lead', 'Opportunity')",
		},
		"query": {"type": "string", "description": "Search text to match against document name"},
		"status": {"type": "string", "description": "Filter by status field value"},
		"limit": {"type": "integer", "description": "Maximum results to return (default 10)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def search_documents(doctype=None, query=None, status=None, limit=10, company=None):
	"""Search documents of a specified DocType."""
	if not doctype:
		return {"error": "doctype parameter is required"}

	company = get_default_company(company)

	# Build filters
	filters = {}
	or_filters = {}
	meta = frappe.get_meta(doctype)

	# Add company filter if the DocType has a company field
	if meta.has_field("company"):
		filters["company"] = company

	if status and meta.has_field("status"):
		filters["status"] = status

	if query:
		or_filters["name"] = ["like", f"%{query}%"]
		# Also search title field if it exists
		if meta.has_field("title"):
			or_filters["title"] = ["like", f"%{query}%"]
		# Search common name-like fields
		for fname in ("customer_name", "supplier_name", "lead_name", "party_name", "item_name"):
			if meta.has_field(fname):
				or_filters[fname] = ["like", f"%{query}%"]

	# Determine display fields
	fields = ["name"]
	for fname in ("title", "status", "creation", "modified"):
		if meta.has_field(fname):
			fields.append(fname)
	# Add common name fields
	for fname in (
		"customer_name",
		"supplier_name",
		"lead_name",
		"party_name",
		"item_name",
		"first_name",
		"last_name",
	):
		if meta.has_field(fname):
			fields.append(fname)

	documents = frappe.get_all(
		doctype,
		filters=filters,
		or_filters=or_filters,
		fields=fields,
		limit=limit,
		order_by="modified desc",
	)

	return {
		"doctype": doctype,
		"documents": documents,
		"count": len(documents),
		"company": company,
	}
