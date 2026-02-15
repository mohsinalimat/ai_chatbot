"""
Tool Registry for AI Chatbot

Provides a decorator-based registration system for tools.
Tools self-register with metadata (name, category, description, schema).
The registry handles discovery, filtering by settings, and execution.
"""

from typing import Any

import frappe

from ai_chatbot.core.config import is_tool_category_enabled
from ai_chatbot.core.constants import TOOL_CATEGORIES
from ai_chatbot.core.exceptions import ToolExecutionError, ToolNotFoundError
from ai_chatbot.core.logger import log_tool_error

# Global tool store — populated by @register_tool decorator at import time
_TOOL_REGISTRY = {}


def register_tool(name, category, description, parameters=None):
	"""Decorator to register a tool function.

	Usage:
		@register_tool(
			name="get_sales_analytics",
			category="selling",
			description="Get sales analytics including revenue and orders",
			parameters={
				"from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
				"to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
				"company": {"type": "string", "description": "Company name. Defaults to user's default company."},
			}
		)
		def get_sales_analytics(from_date=None, to_date=None, company=None):
			...

	Args:
		name: Unique tool name (must match function name).
		category: Tool category key (e.g. "crm", "selling", "buying", "finance", "inventory").
		description: Human-readable description for the LLM.
		parameters: Dict of parameter definitions for OpenAI function calling schema.
	"""

	def decorator(func):
		_TOOL_REGISTRY[name] = {
			"name": name,
			"category": category,
			"description": description,
			"parameters": parameters or {},
			"function": func,
		}
		return func

	return decorator


def get_all_tools_schema():
	"""Get OpenAI function calling schema for all enabled tools.

	Checks Chatbot Settings to determine which categories are enabled,
	then builds the schema from registered tools in those categories.

	Returns:
		List of dicts in OpenAI function calling format.
	"""
	_ensure_tools_loaded()

	tools = []
	for _tool_name, tool_info in _TOOL_REGISTRY.items():
		category = tool_info["category"]
		settings_field = TOOL_CATEGORIES.get(category)

		# If the category has a settings flag, check it
		if settings_field and not is_tool_category_enabled(settings_field):
			continue

		tools.append(_build_schema(tool_info))

	return tools


def execute_tool(tool_name: str, arguments: dict) -> dict:
	"""Execute a registered tool by name.

	Args:
		tool_name: The registered tool name.
		arguments: Dict of arguments to pass to the tool function.

	Returns:
		Dict with "success" (bool) and "data" or "error".
	"""
	_ensure_tools_loaded()

	tool_info = _TOOL_REGISTRY.get(tool_name)
	if not tool_info:
		log_tool_error(tool_name, "Tool not found", arguments)
		return {"success": False, "error": f"Tool '{tool_name}' not found"}

	try:
		result = tool_info["function"](**arguments)
		return {"success": True, "data": result}
	except Exception as e:
		log_tool_error(tool_name, e, arguments)
		return {"success": False, "error": str(e)}


def get_tool_info(tool_name: str) -> dict | None:
	"""Get metadata for a registered tool.

	Args:
		tool_name: The registered tool name.

	Returns:
		Tool info dict or None if not found.
	"""
	_ensure_tools_loaded()
	return _TOOL_REGISTRY.get(tool_name)


def get_registered_tools():
	"""Get all registered tool names and categories.

	Returns:
		Dict of {tool_name: category}.
	"""
	_ensure_tools_loaded()
	return {name: info["category"] for name, info in _TOOL_REGISTRY.items()}


def _build_schema(tool_info):
	"""Build OpenAI function calling schema for a tool.

	Args:
		tool_info: Tool registry entry dict.

	Returns:
		Dict in OpenAI function calling format.
	"""
	return {
		"type": "function",
		"function": {
			"name": tool_info["name"],
			"description": tool_info["description"],
			"parameters": {
				"type": "object",
				"properties": tool_info["parameters"],
			},
		},
	}


def _ensure_tools_loaded():
	"""Import all tool modules to trigger @register_tool decorators.

	Called lazily on first access. Module imports are idempotent —
	Python caches them after first import.
	"""
	if _TOOL_REGISTRY:
		return

	# Import all tool modules — their @register_tool decorators populate _TOOL_REGISTRY
	import ai_chatbot.tools.account
	import ai_chatbot.tools.buying
	import ai_chatbot.tools.crm
	import ai_chatbot.tools.hrms
	import ai_chatbot.tools.operations.create
	import ai_chatbot.tools.operations.search
	import ai_chatbot.tools.operations.update
	import ai_chatbot.tools.selling
	import ai_chatbot.tools.stock

	# Phase 4: Finance tools
	import ai_chatbot.tools.finance.budget
	import ai_chatbot.tools.finance.cash_flow
	import ai_chatbot.tools.finance.payables
	import ai_chatbot.tools.finance.profitability
	import ai_chatbot.tools.finance.ratios
	import ai_chatbot.tools.finance.receivables
	import ai_chatbot.tools.finance.working_capital
