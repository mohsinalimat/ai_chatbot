"""
Centralized Configuration for AI Chatbot
Reads from Chatbot Settings DocType and user defaults.
"""

import frappe


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
