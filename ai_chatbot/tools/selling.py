"""
Selling Tools Module
Sales and customer analytics tools for AI Chatbot
"""

from frappe.utils import flt

from ai_chatbot.core.config import get_default_company
from ai_chatbot.data.analytics import get_grouped_sum
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_sales_analytics",
	category="selling",
	description="Get sales analytics including revenue, orders, and growth trends",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
		"customer": {"type": "string", "description": "Filter by customer name"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_sales_analytics(from_date=None, to_date=None, customer=None, company=None):
	"""Get sales analytics with multi-company and base currency support."""
	company = get_default_company(company)

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
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
		"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
	},
)
def get_top_customers(limit=10, from_date=None, company=None):
	"""Get top customers by revenue using the analytics data layer (no raw SQL)."""
	company = get_default_company(company)

	filters = {"docstatus": 1}
	if from_date:
		filters["posting_date"] = [">=", from_date]

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
