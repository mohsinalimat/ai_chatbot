"""
Document Operations for AI Chatbot

Provides CRUD operations with permission checks and validation.
Used by the operation tools (create, update) to interact with ERPNext.
"""

import frappe

from ai_chatbot.core.config import get_default_company
from ai_chatbot.data.validators import check_permission, validate_link_fields


def create_document(doctype, values, company=None):
	"""Create a new document with permission checks and validation.

	Args:
		doctype: DocType name (e.g. "Lead", "Opportunity", "ToDo").
		values: Dict of field→value for the new document.
		company: Company name (auto-injected if the DocType has a company field).

	Returns:
		Dict with created document name and key fields.

	Raises:
		frappe.PermissionError: If user lacks create permission.
		frappe.ValidationError: If link field validation fails.
	"""
	if not check_permission(doctype, "create"):
		frappe.throw(f"You do not have permission to create {doctype}", frappe.PermissionError)

	# Auto-inject company if the DocType has a company field and none was provided
	if _doctype_has_field(doctype, "company") and "company" not in values:
		values["company"] = get_default_company(company)

	# Validate link fields before creating
	link_errors = validate_link_fields(doctype, values)
	if link_errors:
		frappe.throw(f"Validation failed: {'; '.join(link_errors)}", frappe.ValidationError)

	doc = frappe.new_doc(doctype)
	doc.update(values)
	doc.insert()
	frappe.db.commit()

	return {
		"doctype": doctype,
		"name": doc.name,
		"doc_url": _build_doc_url(doctype, doc.name),
		"message": f"{doctype} '{doc.name}' created successfully",
	}


def update_document(doctype, name, values):
	"""Update an existing document with permission checks.

	Args:
		doctype: DocType name.
		name: Document name to update.
		values: Dict of field→value to update.

	Returns:
		Dict with updated document name and changed fields.

	Raises:
		frappe.PermissionError: If user lacks write permission.
		frappe.DoesNotExistError: If document doesn't exist.
		frappe.ValidationError: If link field validation fails.
	"""
	if not frappe.db.exists(doctype, name):
		frappe.throw(f"{doctype} '{name}' does not exist", frappe.DoesNotExistError)

	if not check_permission(doctype, "write", name):
		frappe.throw(f"You do not have permission to update {doctype} '{name}'", frappe.PermissionError)

	# Validate link fields before updating
	link_errors = validate_link_fields(doctype, values)
	if link_errors:
		frappe.throw(f"Validation failed: {'; '.join(link_errors)}", frappe.ValidationError)

	doc = frappe.get_doc(doctype, name)
	doc.update(values)
	doc.save()
	frappe.db.commit()

	return {
		"doctype": doctype,
		"name": doc.name,
		"doc_url": _build_doc_url(doctype, doc.name),
		"updated_fields": list(values.keys()),
		"message": f"{doctype} '{doc.name}' updated successfully",
	}


def _build_doc_url(doctype, name):
	"""Build the full URL to a document in ERPNext.

	Example: _build_doc_url("Sales Invoice", "SINV-00001")
	         → "https://site.example.com/app/sales-invoice/SINV-00001"

	Args:
		doctype: DocType name (e.g. "Lead", "Sales Invoice").
		name: Document name/ID.

	Returns:
		str: Full URL to the document.
	"""
	from frappe.utils import get_url

	slug = frappe.scrub(doctype).replace("_", "-")
	return f"{get_url()}/app/{slug}/{name}"


def _doctype_has_field(doctype, fieldname):
	"""Check if a DocType has a specific field.

	Uses Frappe's meta cache for performance.

	Args:
		doctype: DocType name.
		fieldname: Field name to check.

	Returns:
		bool
	"""
	meta = frappe.get_meta(doctype)
	return meta.has_field(fieldname)
