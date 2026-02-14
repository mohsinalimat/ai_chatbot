"""
Centralized Configuration for AI Chatbot
Reads from Chatbot Settings DocType and user defaults.
"""

import frappe
from frappe.utils import add_days, nowdate


def get_default_company(company=None):
	"""Get the effective company — passed value, user default, or global default.

	Args:
		company: Explicitly passed company name. If provided and valid, returned as-is.

	Returns:
		Company name string.

	Raises:
		ai_chatbot.core.exceptions.CompanyRequiredError: If no company can be resolved.
	"""
	if company:
		return company

	company = frappe.defaults.get_user_default("Company")
	if company:
		return company

	company = frappe.defaults.get_global_default("company")
	if company:
		return company

	from ai_chatbot.core.exceptions import CompanyRequiredError

	raise CompanyRequiredError()


def get_fiscal_year_dates(company=None):
	"""Get the current fiscal year start and end dates for a company.

	Uses ERPNext's get_fiscal_year utility which respects company-specific
	fiscal year configurations via the Fiscal Year Company child table.

	Args:
		company: Company name. Resolved via get_default_company if not provided.

	Returns:
		Tuple of (from_date, to_date) as strings in YYYY-MM-DD format.
		Falls back to (today - 365 days, today) if no fiscal year is configured.
	"""
	company = get_default_company(company)

	try:
		from erpnext.accounts.utils import get_fiscal_year

		fy = get_fiscal_year(date=nowdate(), company=company)
		return (str(fy[1]), str(fy[2]))
	except Exception:
		# Fallback if no fiscal year is configured
		today = nowdate()
		return (str(add_days(today, -365)), today)


def get_company_currency(company):
	"""Get the default currency for a company.

	Args:
		company: Company name.

	Returns:
		Currency code string (e.g. "USD", "INR").
	"""
	return frappe.get_cached_value("Company", company, "default_currency")


def get_chatbot_settings():
	"""Get the Chatbot Settings singleton (cached per request).

	Returns:
		Chatbot Settings document.
	"""
	return frappe.get_single("Chatbot Settings")


def is_tool_category_enabled(category):
	"""Check if a tool category is enabled in settings.

	Args:
		category: Setting field name (e.g. "enable_crm_tools").

	Returns:
		bool
	"""
	settings = get_chatbot_settings()
	return bool(getattr(settings, category, False))
