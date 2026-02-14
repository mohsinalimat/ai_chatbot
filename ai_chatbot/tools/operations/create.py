"""
Create Tools Module
Document creation tools for AI Chatbot (write operations)
"""

import frappe

from ai_chatbot.data.operations import create_document
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="create_lead",
	category="operations",
	description=(
		"Create a new Lead in ERPNext. "
		"IMPORTANT: Always confirm details with the user before calling this tool."
	),
	parameters={
		"first_name": {"type": "string", "description": "First name of the lead (required)"},
		"last_name": {"type": "string", "description": "Last name of the lead"},
		"company_name": {"type": "string", "description": "Company/organization name of the lead"},
		"email_id": {"type": "string", "description": "Email address"},
		"mobile_no": {"type": "string", "description": "Mobile phone number"},
		"source": {
			"type": "string",
			"description": "Lead source (e.g. 'Website', 'Referral', 'Campaign', 'Cold Calling')",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
)
def create_lead(
	first_name=None,
	last_name=None,
	company_name=None,
	email_id=None,
	mobile_no=None,
	source=None,
	company=None,
):
	"""Create a new Lead record."""
	if not first_name:
		return {"error": "first_name is required to create a Lead"}

	values = {"first_name": first_name}
	if last_name:
		values["last_name"] = last_name
	if company_name:
		values["company_name"] = company_name
	if email_id:
		values["email_id"] = email_id
	if mobile_no:
		values["mobile_no"] = mobile_no
	if source:
		values["source"] = source

	return create_document("Lead", values, company=company)


@register_tool(
	name="create_opportunity",
	category="operations",
	description=(
		"Create a new Opportunity in ERPNext. "
		"You can pass either the document ID (e.g. 'CRM-LEAD-2026-00001') or a human name "
		"(e.g. 'John Smith') as party_name — the tool will resolve it automatically. "
		"IMPORTANT: Always confirm details with the user before calling this tool."
	),
	parameters={
		"party_name": {
			"type": "string",
			"description": (
				"Customer or Lead reference (required). "
				"Accepts a document ID (e.g. 'CRM-LEAD-2026-00001', 'CUST-00001') or "
				"a human name (e.g. 'John Smith') — the tool will search and resolve it."
			),
		},
		"opportunity_from": {
			"type": "string",
			"description": "Source type: 'Customer' or 'Lead' (default: 'Lead')",
		},
		"opportunity_amount": {"type": "number", "description": "Expected opportunity value"},
		"currency": {"type": "string", "description": "Currency code (e.g. 'USD', 'INR')"},
		"sales_stage": {
			"type": "string",
			"description": "Sales stage (e.g. 'Prospecting', 'Qualification', 'Proposal/Price Quote')",
		},
		"company": {"type": "string", "description": "Company name. Optional — omit to use user's default company."},
	},
)
def create_opportunity(
	party_name=None,
	opportunity_from="Lead",
	opportunity_amount=None,
	currency=None,
	sales_stage=None,
	company=None,
):
	"""Create a new Opportunity record.

	Resolves party_name if a human name is given instead of a document ID.
	"""
	if not party_name:
		return {"error": "party_name is required to create an Opportunity"}

	# Resolve human name → document ID if needed
	resolved = _resolve_party_name(party_name, opportunity_from)
	if resolved.get("error"):
		return resolved
	party_name = resolved["name"]
	opportunity_from = resolved["opportunity_from"]

	values = {
		"party_name": party_name,
		"opportunity_from": opportunity_from,
	}
	if opportunity_amount is not None:
		values["opportunity_amount"] = opportunity_amount
	if currency:
		values["currency"] = currency
	if sales_stage:
		values["sales_stage"] = sales_stage

	return create_document("Opportunity", values, company=company)


def _resolve_party_name(party_name, opportunity_from):
	"""Resolve a human-readable name to a document ID.

	If party_name already matches an existing document, return it as-is.
	Otherwise, search by display name fields (lead_name, customer_name).

	Returns:
		dict with 'name' and 'opportunity_from', or 'error'.
	"""
	doctype = opportunity_from or "Lead"

	# 1. Exact match on document name — already a valid ID
	if frappe.db.exists(doctype, party_name):
		return {"name": party_name, "opportunity_from": doctype}

	# 2. Try the other party type as exact match
	other = "Customer" if doctype == "Lead" else "Lead"
	if frappe.db.exists(other, party_name):
		return {"name": party_name, "opportunity_from": other}

	# 3. Search by human-readable name in the requested type first
	name_field = "lead_name" if doctype == "Lead" else "customer_name"
	match = frappe.db.get_value(doctype, {name_field: party_name}, "name")
	if match:
		return {"name": match, "opportunity_from": doctype}

	# 4. Search the other type
	other_name_field = "customer_name" if doctype == "Lead" else "lead_name"
	match = frappe.db.get_value(other, {other_name_field: party_name}, "name")
	if match:
		return {"name": match, "opportunity_from": other}

	# 5. Fuzzy search (LIKE) — try both types
	for dt, field in [(doctype, name_field), (other, other_name_field)]:
		matches = frappe.get_all(
			dt,
			filters={field: ["like", f"%{party_name}%"]},
			fields=["name", field],
			limit=5,
		)
		if len(matches) == 1:
			return {"name": matches[0].name, "opportunity_from": dt}
		if matches:
			suggestions = [f"{m.name} ({m.get(field)})" for m in matches]
			return {
				"error": (
					f"Multiple {dt} records match '{party_name}'. "
					f"Please specify one of: {', '.join(suggestions)}"
				)
			}

	return {
		"error": (
			f"No Customer or Lead found matching '{party_name}'. "
			f"Please create a Lead first using create_lead, or provide an exact document ID."
		)
	}


@register_tool(
	name="create_todo",
	category="operations",
	description=(
		"Create a new ToDo task in ERPNext. "
		"IMPORTANT: Always confirm details with the user before calling this tool."
	),
	parameters={
		"description": {"type": "string", "description": "Task description (required)"},
		"allocated_to": {
			"type": "string",
			"description": "Email of the user to assign the task to (defaults to current user)",
		},
		"date": {"type": "string", "description": "Due date (YYYY-MM-DD)"},
		"priority": {
			"type": "string",
			"description": "Priority: 'Low', 'Medium', or 'High' (default: 'Medium')",
		},
	},
)
def create_todo(description=None, allocated_to=None, date=None, priority="Medium"):
	"""Create a new ToDo task."""
	if not description:
		return {"error": "description is required to create a ToDo"}

	import frappe

	values = {
		"description": description,
		"priority": priority,
		"allocated_to": allocated_to or frappe.session.user,
	}
	if date:
		values["date"] = date

	return create_document("ToDo", values)
