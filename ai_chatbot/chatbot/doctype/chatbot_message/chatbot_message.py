# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ChatbotMessage(Document):
	"""Chatbot Message DocType Controller"""

	def before_insert(self):
		"""Called before document is inserted"""
		# Set timestamp
		if not self.timestamp:
			self.timestamp = now_datetime()

	def validate(self):
		"""Validate document before save"""
		# Validate role
		if self.role not in ["user", "assistant", "system", "tool"]:
			frappe.throw("Invalid message role")

		# Validate conversation exists
		if not frappe.db.exists("Chatbot Conversation", self.conversation):
			frappe.throw("Invalid conversation")

	def after_insert(self):
		"""Called after document is inserted"""
		# Update conversation message count and timestamp
		conversation = frappe.get_doc("Chatbot Conversation", self.conversation)
		conversation.update_message_count()

		# Update token usage if tokens were used
		if self.tokens_used:
			conversation.update_token_usage(self.tokens_used)
