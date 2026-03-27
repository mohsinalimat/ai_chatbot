# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Maximum safe value for Int fields — prevents orjson "Integer exceeds 64-bit range"
# errors when serializing the response. MariaDB BIGINT max is 2^63-1.
_MAX_INT = 2**63 - 1


class ChatbotSettings(Document):
	"""Chatbot Settings DocType Controller"""

	def validate(self):
		"""Validate settings before save."""
		self._clamp_int_fields()

	def _clamp_int_fields(self):
		"""Clamp all Int fields to safe 64-bit range.

		Frappe's cint() can produce arbitrarily large Python ints from
		user input. orjson (used for JSON responses) rejects integers
		outside the signed 64-bit range, causing a TypeError on save.
		"""
		for df in self.meta.get("fields", {"fieldtype": "Int"}):
			value = self.get(df.fieldname)
			if isinstance(value, int) and abs(value) > _MAX_INT:
				self.set(df.fieldname, _MAX_INT if value > 0 else -_MAX_INT)

	def on_update(self):
		"""Called after document is saved."""
		frappe.cache().delete_value("ai_chatbot_settings")

		# Clear circuit breaker state for all providers when settings change
		# (e.g. API key was corrected, provider was switched)
		for provider in ("OpenAIProvider", "ClaudeProvider", "GeminiProvider"):
			prefix = f"ai_chatbot:cb:{provider}"
			for suffix in (":failures", ":open_until", ":probe"):
				frappe.cache().delete_value(f"{prefix}{suffix}")
