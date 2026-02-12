"""
Structured Logging for AI Chatbot
Wraps frappe.log_error with consistent formatting.
"""

import frappe

from ai_chatbot.core.constants import LOG_TITLE


def log_error(message, title=None, reference_doctype=None, reference_name=None):
	"""Log an error with consistent formatting.

	Args:
		message: Error message or exception.
		title: Optional sub-title (appended to LOG_TITLE).
		reference_doctype: Optional linked doctype.
		reference_name: Optional linked document name.
	"""
	full_title = f"{LOG_TITLE} - {title}" if title else LOG_TITLE
	frappe.log_error(
		message=str(message),
		title=full_title,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
	)


def log_tool_error(tool_name, error, arguments=None):
	"""Log a tool execution error with context.

	Args:
		tool_name: Name of the tool that failed.
		error: The exception or error message.
		arguments: The arguments passed to the tool.
	"""
	msg = f"Tool: {tool_name}\nError: {error}"
	if arguments:
		msg += f"\nArguments: {arguments}"
	log_error(msg, title="Tool Execution")


def log_provider_error(provider_name, error):
	"""Log an AI provider error.

	Args:
		provider_name: Name of the provider (OpenAI, Claude).
		error: The exception or error message.
	"""
	log_error(f"Provider: {provider_name}\nError: {error}", title="AI Provider")
