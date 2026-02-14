"""
Update Tools Module
Document update tools for AI Chatbot (write operations)
"""

from ai_chatbot.data.operations import update_document
from ai_chatbot.tools.registry import register_tool

# Valid statuses for Lead
LEAD_STATUSES = [
	"Lead",
	"Open",
	"Replied",
	"Opportunity",
	"Quotation",
	"Lost Quotation",
	"Interested",
	"Converted",
	"Do Not Contact",
]

# Valid statuses for Opportunity
OPPORTUNITY_STATUSES = ["Open", "Quotation", "Converted", "Lost", "Replied", "Closed"]


@register_tool(
	name="update_lead_status",
	category="operations",
	description=(
		"Update the status of an existing Lead in ERPNext. "
		"IMPORTANT: Always confirm the change with the user before calling this tool."
	),
	parameters={
		"lead_name": {"type": "string", "description": "The Lead document name/ID (required)"},
		"status": {
			"type": "string",
			"description": (
				"New status. Valid values: Lead, Open, Replied, Opportunity, "
				"Quotation, Lost Quotation, Interested, Converted, Do Not Contact"
			),
		},
	},
)
def update_lead_status(lead_name=None, status=None):
	"""Update a Lead's status."""
	if not lead_name:
		return {"error": "lead_name is required"}
	if not status:
		return {"error": "status is required"}

	if status not in LEAD_STATUSES:
		return {"error": f"Invalid status '{status}'. Valid statuses: {', '.join(LEAD_STATUSES)}"}

	return update_document("Lead", lead_name, {"status": status})


@register_tool(
	name="update_opportunity_status",
	category="operations",
	description=(
		"Update the status of an existing Opportunity in ERPNext. "
		"IMPORTANT: Always confirm the change with the user before calling this tool."
	),
	parameters={
		"opportunity_name": {"type": "string", "description": "The Opportunity document name/ID (required)"},
		"status": {
			"type": "string",
			"description": "New status. Valid values: Open, Quotation, Converted, Lost, Replied, Closed",
		},
	},
)
def update_opportunity_status(opportunity_name=None, status=None):
	"""Update an Opportunity's status."""
	if not opportunity_name:
		return {"error": "opportunity_name is required"}
	if not status:
		return {"error": "status is required"}

	if status not in OPPORTUNITY_STATUSES:
		return {"error": f"Invalid status '{status}'. Valid statuses: {', '.join(OPPORTUNITY_STATUSES)}"}

	return update_document("Opportunity", opportunity_name, {"status": status})


@register_tool(
	name="update_todo",
	category="operations",
	description=(
		"Update an existing ToDo task in ERPNext. "
		"IMPORTANT: Always confirm the change with the user before calling this tool."
	),
	parameters={
		"todo_name": {"type": "string", "description": "The ToDo document name/ID (required)"},
		"status": {"type": "string", "description": "New status: 'Open', 'Closed', or 'Cancelled'"},
		"priority": {"type": "string", "description": "New priority: 'Low', 'Medium', or 'High'"},
		"description": {"type": "string", "description": "Updated task description"},
		"date": {"type": "string", "description": "Updated due date (YYYY-MM-DD)"},
	},
)
def update_todo(todo_name=None, status=None, priority=None, description=None, date=None):
	"""Update a ToDo task."""
	if not todo_name:
		return {"error": "todo_name is required"}

	values = {}
	if status:
		if status not in ("Open", "Closed", "Cancelled"):
			return {"error": f"Invalid status '{status}'. Valid: Open, Closed, Cancelled"}
		values["status"] = status
	if priority:
		if priority not in ("Low", "Medium", "High"):
			return {"error": f"Invalid priority '{priority}'. Valid: Low, Medium, High"}
		values["priority"] = priority
	if description:
		values["description"] = description
	if date:
		values["date"] = date

	if not values:
		return {"error": "No fields to update. Provide at least one of: status, priority, description, date"}

	return update_document("ToDo", todo_name, values)
