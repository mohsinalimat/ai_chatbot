"""
Buying Tools Module
Purchase and supplier management tools for AI Chatbot
"""

import frappe
from frappe.utils import flt

from ai_chatbot.core.config import get_default_company
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_purchase_analytics",
	category="buying",
	description="Get purchase analytics including spending, orders, and supplier performance",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_purchase_analytics(from_date=None, to_date=None, company=None):
	"""Get purchase analytics with multi-company and base currency support."""
	company = get_default_company(company)

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
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
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
