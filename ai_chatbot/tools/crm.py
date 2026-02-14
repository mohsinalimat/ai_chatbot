"""
CRM Tools Module
Customer Relationship Management tools for AI Chatbot
"""

import frappe
from frappe.utils import flt

from ai_chatbot.core.config import get_company_currency, get_default_company, get_fiscal_year_dates
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_lead_statistics",
	category="crm",
	description="Get statistics about leads including count, status breakdown, and conversion rates",
	parameters={
		"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start."},
		"to_date": {"type": "string", "description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end."},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_lead_statistics(from_date=None, to_date=None, company=None):
	"""Get lead statistics with multi-company support."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	filters = [["company", "=", company]]
	if from_date:
		filters.append(["creation", ">=", from_date])
	if to_date:
		filters.append(["creation", "<=", to_date])

	leads = frappe.get_all("Lead", filters=filters, fields=["status"])

	status_count = {}
	for lead in leads:
		status = lead.status
		status_count[status] = status_count.get(status, 0) + 1

	return {
		"total_leads": len(leads),
		"status_breakdown": status_count,
		"period": {"from": from_date, "to": to_date},
		"company": company,
	}


@register_tool(
	name="get_opportunity_pipeline",
	category="crm",
	description="Get sales opportunity pipeline with stages and values",
	parameters={
		"status": {"type": "string", "description": "Filter by status (Open, Converted, Lost)"},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def get_opportunity_pipeline(status=None, company=None):
	"""Get opportunity pipeline with multi-company and currency support."""
	company = get_default_company(company)
	currency = get_company_currency(company)

	filters = {"company": company}
	if status:
		filters["status"] = status

	opportunities = frappe.get_all(
		"Opportunity",
		filters=filters,
		fields=["name", "opportunity_amount", "currency", "status", "sales_stage", "party_name"],
	)

	# Sum with currency conversion — Opportunity doesn't have base_* fields
	total_value = 0
	for opp in opportunities:
		opp_currency = opp.get("currency")
		amount = flt(opp.get("opportunity_amount", 0))
		if opp_currency and opp_currency != currency and amount:
			from ai_chatbot.data.currency import get_exchange_rate

			rate = get_exchange_rate(opp_currency, currency)
			total_value += amount * rate
		else:
			total_value += amount

	result = {
		"opportunities": opportunities,
		"total_value": total_value,
		"count": len(opportunities),
	}
	return build_currency_response(result, company)
