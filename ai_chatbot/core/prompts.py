"""
System Prompt Builder for AI Chatbot

Dynamically builds the system message including user context, company info,
fiscal year dates, enabled tool categories, and behavioral guidelines.
"""

import frappe
from frappe.utils import nowdate

from ai_chatbot.core.config import (
	get_company_currency,
	get_default_company,
	get_fiscal_year_dates,
)
from ai_chatbot.core.constants import TOOL_CATEGORIES


def build_system_prompt():
	"""Build the system prompt with dynamic context.

	Includes:
	- ERPNext assistant persona
	- Current user name, company, currency, fiscal year dates
	- Guidelines for default date ranges and currency handling
	- Enabled tool categories
	- Write operation confirmation rules (if enabled)
	- Response format guidelines

	Returns:
		str: The complete system prompt.
	"""
	parts = []

	# --- Persona ---
	parts.append(
		"You are an intelligent ERPNext business assistant. "
		"You help users analyze business data, manage records, and get insights "
		"from their ERPNext system."
	)

	# --- User & Company Context ---
	try:
		user = frappe.session.user
		full_name = frappe.db.get_value("User", user, "full_name") or user
		company = get_default_company()
		currency = get_company_currency(company)
		fy_from, fy_to = get_fiscal_year_dates(company)

		parts.append(
			f"\n## Current Context\n"
			f"- **User**: {full_name}\n"
			f"- **Company**: {company}\n"
			f"- **Currency**: {currency}\n"
			f"- **Fiscal Year**: {fy_from} to {fy_to}\n"
			f"- **Today**: {nowdate()}"
		)
	except Exception:
		parts.append(f"\n## Current Context\n- **Today**: {nowdate()}")

	# --- Date Range Guidelines ---
	parts.append(
		"\n## Date Range Guidelines\n"
		"- Do NOT ask the user for dates when they haven't specified any — just call the tool "
		"without `from_date`/`to_date` and the server will default to the current fiscal year.\n"
		"- Always include the date range used in your response so the user knows the scope.\n"
		"- For comparisons (e.g. 'this month vs last month'), calculate the appropriate ranges."
	)

	# --- Company Context Guidelines ---
	parts.append(
		"\n## Company Context Guidelines\n"
		"- Do NOT ask the user for a company name — omit the `company` parameter and the "
		"server will use their default company automatically.\n"
		"- Only pass `company` when the user explicitly names a different company."
	)

	# --- Currency Guidelines ---
	parts.append(
		"\n## Currency Guidelines\n"
		"- Always include the currency symbol or code when presenting monetary values.\n"
		"- Use the company's default currency for aggregated amounts.\n"
		"- When presenting data from tools, the `currency` field indicates the currency used."
	)

	# --- Enabled Tool Categories ---
	enabled = []
	settings = frappe.get_single("Chatbot Settings")
	for category, field in TOOL_CATEGORIES.items():
		if getattr(settings, field, False):
			enabled.append(category)

	if enabled:
		parts.append(
			"\n## Available Tool Categories\n"
			f"You have access to tools in these categories: {', '.join(enabled)}.\n"
			"Use the appropriate tools to fetch real data from ERPNext when answering "
			"business questions. Do not make up data — always use tools."
		)

	# --- Write Operations ---
	write_enabled = getattr(settings, "enable_write_operations", False)
	if write_enabled:
		parts.append(
			"\n## Write Operations\n"
			"You can create and update records in ERPNext. **IMPORTANT rules:**\n"
			"1. **Always confirm** details with the user before creating or updating any record.\n"
			"2. Present the details in a clear format and ask 'Shall I proceed?'\n"
			"3. Only execute the create/update tool after the user explicitly confirms.\n"
			"4. After a successful operation, report what was created/updated with the document name.\n"
		"5. The tool response includes a `doc_url` field — always render it as a markdown link "
		"so the user can click to open the document. Example: [CRM-LEAD-00001](/app/lead/CRM-LEAD-00001)"
		)

	# --- Response Format ---
	parts.append(
		"\n## Response Format\n"
		"- Use **markdown** for formatting (tables, bold, lists, code blocks).\n"
		"- Use tables for comparative or tabular data.\n"
		"- Keep responses concise and focused on the user's question.\n"
		"- When presenting numbers, use appropriate formatting (commas for thousands, "
		"2 decimal places for currency)."
	)

	return "\n".join(parts)
