"""
Custom Exceptions for AI Chatbot
"""


class ChatbotError(Exception):
	"""Base exception for all chatbot errors"""

	def __init__(self, message="An error occurred in the AI Chatbot", error_code=None):
		self.message = message
		self.error_code = error_code
		super().__init__(self.message)


class ToolExecutionError(ChatbotError):
	"""Raised when a tool fails to execute"""

	def __init__(self, tool_name, message=None, original_error=None):
		self.tool_name = tool_name
		self.original_error = original_error
		msg = message or f"Tool '{tool_name}' failed to execute"
		if original_error:
			msg += f": {original_error}"
		super().__init__(msg, error_code="TOOL_EXECUTION_ERROR")


class ProviderError(ChatbotError):
	"""Raised when an AI provider fails"""

	def __init__(self, provider_name, message=None, original_error=None):
		self.provider_name = provider_name
		self.original_error = original_error
		msg = message or f"AI provider '{provider_name}' failed"
		if original_error:
			msg += f": {original_error}"
		super().__init__(msg, error_code="PROVIDER_ERROR")


class CompanyRequiredError(ChatbotError):
	"""Raised when a company is required but not provided or configured"""

	def __init__(self):
		super().__init__(
			"No company specified and no default company set for the current user. "
			"Please specify a company or set a default company in your user settings.",
			error_code="COMPANY_REQUIRED",
		)


class ToolNotFoundError(ChatbotError):
	"""Raised when a requested tool does not exist in the registry"""

	def __init__(self, tool_name):
		self.tool_name = tool_name
		super().__init__(f"Tool '{tool_name}' not found in the registry", error_code="TOOL_NOT_FOUND")


class DocumentValidationError(ChatbotError):
	"""Raised when document validation fails (missing fields, invalid links, etc.)"""

	def __init__(self, doctype, errors):
		self.doctype = doctype
		self.errors = errors
		msg = f"Validation failed for {doctype}: {', '.join(errors)}"
		super().__init__(msg, error_code="DOCUMENT_VALIDATION_ERROR")
