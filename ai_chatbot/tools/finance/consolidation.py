# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Multi-Company Consolidation Tool

Provides a tool that aggregates data from any registered tool
across a parent company and all its subsidiaries.
"""

import frappe
from frappe.utils import flt

from ai_chatbot.core.config import get_company_currency, get_default_company
from ai_chatbot.core.consolidation import get_child_companies, get_consolidated_data, is_parent_company
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_consolidated_report",
	category="finance",
	description=(
		"Run any analytics tool across a parent company and all its subsidiaries, "
		"then consolidate the results. Use this when the user wants consolidated/group data "
		"across multiple companies. Pass the name of the tool to consolidate "
		"(e.g. 'get_sales_analytics') and any parameters that tool accepts."
	),
	parameters={
		"tool_name": {
			"type": "string",
			"description": (
				"Name of the registered tool to run across companies "
				"(e.g. 'get_sales_analytics', 'get_receivable_aging', 'get_financial_overview')"
			),
		},
		"tool_params": {
			"type": "object",
			"description": (
				'Parameters to pass to the tool (e.g. {"from_date": "2025-04-01", '
				'"to_date": "2026-03-31"}). Do NOT include \'company\' — it is set '
				"automatically for each subsidiary."
			),
		},
		"target_currency": {
			"type": "string",
			"description": (
				"Currency to display results in. Optional — defaults to the parent company's currency."
			),
		},
		"company": {
			"type": "string",
			"description": ("Parent company name. Optional — defaults to user's default company."),
		},
	},
	doctypes=["Company"],
)
def get_consolidated_report(tool_name=None, tool_params=None, target_currency=None, company=None):
	"""Consolidate a tool's output across a parent company and its subsidiaries.

	Args:
		tool_name: Name of the registered tool to execute.
		tool_params: Dict of parameters to pass to the tool (excluding 'company').
		target_currency: Currency for the consolidated view. Defaults to parent company currency.
		company: Parent company. Defaults to user's default company.

	Returns:
		Dict with per-company results, exchange rates, and a summary.
	"""
	if not tool_name:
		return {"error": "tool_name is required"}

	company = get_default_company(company)
	tool_params = tool_params or {}

	# Remove company from tool_params if accidentally included
	tool_params.pop("company", None)

	# Verify this is a parent company
	if not is_parent_company(company):
		return {
			"error": f'"{company}" is not a parent company (no subsidiaries found). '
			f"Use the tool directly instead of consolidation.",
		}

	# Look up the tool function from the registry
	from ai_chatbot.tools.registry import get_tool_info

	tool_info = get_tool_info(tool_name)
	if not tool_info:
		return {"error": f"Tool '{tool_name}' not found in registry"}

	tool_func = tool_info["function"]

	# Execute across all companies
	consolidated = get_consolidated_data(tool_func, company, **tool_params)

	# Override target currency if user specified one
	parent_currency = get_company_currency(company)
	display_currency = target_currency or parent_currency

	if display_currency != parent_currency:
		# Recalculate exchange rates to the requested currency
		from ai_chatbot.core.consolidation import _get_exchange_rate

		for entry in consolidated["companies"]:
			if entry["currency"] != display_currency:
				entry["exchange_rate"] = _get_exchange_rate(entry["currency"], display_currency)
			else:
				entry["exchange_rate"] = 1.0
		consolidated["target_currency"] = display_currency

	# Build summary
	children = get_child_companies(company)
	consolidated["summary"] = {
		"parent_company": company,
		"subsidiaries": list(children),
		"total_companies": len(consolidated["companies"]),
		"target_currency": consolidated["target_currency"],
		"tool_used": tool_name,
	}

	return consolidated
