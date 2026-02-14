"""
Document Validators for AI Chatbot

Provides validation helpers for CRUD operations:
- Mandatory field checks
- Link field validation
- Permission checks
"""

import frappe


def validate_mandatory_fields(doctype, values):
	"""Check that all mandatory fields have values.

	Args:
		doctype: DocType name.
		values: Dict of field→value to validate.

	Returns:
		List of missing mandatory field names (empty if all present).
	"""
	meta = frappe.get_meta(doctype)
	missing = []

	for df in meta.fields:
		if df.reqd and df.fieldname not in values:
			# Skip fields with default values
			if df.default:
				continue
			missing.append(df.fieldname)

	return missing


def validate_link_fields(doctype, values):
	"""Check that link field values reference existing documents.

	Args:
		doctype: DocType name.
		values: Dict of field→value to validate.

	Returns:
		List of error strings for invalid link references (empty if all valid).
	"""
	meta = frappe.get_meta(doctype)
	errors = []

	for df in meta.fields:
		if df.fieldtype == "Link" and df.fieldname in values:
			value = values[df.fieldname]
			if value and not frappe.db.exists(df.options, value):
				errors.append(f"{df.label or df.fieldname}: '{value}' not found in {df.options}")

	return errors


def check_permission(doctype, perm_type="read", name=None):
	"""Check if current user has permission for a DocType/document.

	Args:
		doctype: DocType name.
		perm_type: Permission type — "read", "write", "create", "delete".
		name: Document name (optional, for document-level checks).

	Returns:
		bool: True if user has permission.
	"""
	try:
		return frappe.has_permission(doctype, ptype=perm_type, doc=name)
	except Exception:
		return False
