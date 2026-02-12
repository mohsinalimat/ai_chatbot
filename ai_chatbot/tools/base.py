"""
Base Tool Module
Backward-compatible wrapper around the tool registry.

chat.py imports `get_all_tools_schema` and `BaseTool.execute_tool` from here.
Both now delegate to the registry.
"""

from ai_chatbot.tools.registry import execute_tool as _registry_execute_tool
from ai_chatbot.tools.registry import get_all_tools_schema as _registry_get_all_tools_schema


class BaseTool:
	"""Backward-compatible base class. Delegates to the registry."""

	@staticmethod
	def execute_tool(tool_name: str, arguments: dict) -> dict:
		"""Execute a tool by name via the registry."""
		return _registry_execute_tool(tool_name, arguments)


def get_all_tools_schema() -> list[dict]:
	"""Get combined schema from all enabled tool modules via the registry."""
	return _registry_get_all_tools_schema()
