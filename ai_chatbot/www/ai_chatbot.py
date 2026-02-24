# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
import frappe


def get_context(context):
	"""Set context for AI Chatbot page"""
	context.no_cache = 1

	# Check if user is logged in
	if frappe.session.user == "Guest":
		frappe.throw("Please login to access AI Chatbot", frappe.PermissionError)

	# Pass site name to template (frappe.local is not directly accessible in Jinja2)
	context.site_name = frappe.local.site

	# Get user's desk theme preference for dark mode support
	desk_theme = frappe.db.get_value("User", frappe.session.user, "desk_theme") or "Light"
	context.desk_theme = desk_theme.lower()

	return context
