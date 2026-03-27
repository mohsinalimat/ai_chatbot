# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
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

	Skips fields that ERPNext auto-populates during ``doc.insert()``:
	- Fields with a default value (``df.default``)
	- Hidden mandatory fields (auto-set by hooks/controllers)
	- Fields whose values come from ERPNext settings (naming series,
	  currency, exchange rate, price list, conversion rates, etc.)
	- The ``company`` field (auto-injected by the CRUD tool)

	Args:
		doctype: DocType name.
		values: Dict of field→value to validate.

	Returns:
		List of missing mandatory field names (empty if all present).
	"""
	meta = frappe.get_meta(doctype)
	missing = []

	# Field names that ERPNext auto-populates from settings/hooks
	_AUTO_POPULATED = {
		"naming_series",
		"series",
		"currency",
		"conversion_rate",
		"exchange_rate",
		"price_list",
		"buying_price_list",
		"selling_price_list",
		"price_list_currency",
		"plc_conversion_rate",
		"price_list_exchange_rate",
		"company",
		"letter_head",
		"language",
		"tc_name",
		"taxes_and_charges",
		"set_warehouse",
	}

	for df in meta.fields:
		if not df.reqd or df.fieldname in values:
			continue

		# Skip fields with a default value set in DocType meta
		if df.default:
			continue

		# Skip hidden mandatory fields — they are auto-set by ERPNext
		# controllers during insert/validate (e.g. posting_date, fiscal_year)
		if df.hidden:
			continue

		# Skip known auto-populated fields
		if df.fieldname in _AUTO_POPULATED:
			continue

		# Skip Select fields with options — they default to the first option
		if df.fieldtype == "Select" and df.options:
			continue

		missing.append(df.fieldname)

	return missing


def validate_link_fields(doctype, values):
	"""Check that link field values reference existing documents.

	When a value is not found by exact match, performs a fuzzy lookup
	using ``_resolve_link_value``.  If exactly one match is found the
	value is **auto-corrected** in-place (mutates ``values``).

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
			if not value:
				continue

			# Exact match — OK
			if frappe.db.exists(df.options, value):
				continue

			# Try fuzzy resolution
			resolved = _resolve_link_value(df.options, df.fieldname, value)
			if resolved:
				values[df.fieldname] = resolved
			else:
				errors.append(f"{df.label or df.fieldname}: '{value}' not found in {df.options}")

	return errors


def validate_child_table_items(doctype, values):
	"""Validate child table entries for a DocType.

	Checks that link-type fields in child table rows reference existing
	documents.  For example, validates ``item_code`` exists in Item master
	for Sales Order Item rows.

	When a Link value is not found by exact match, performs a fuzzy lookup:
	- For ``item_code`` → Item: tries ``item_name`` and ``LIKE`` search
	- For other Link fields: tries ``LIKE`` search on the target DocType name

	If a fuzzy match resolves to exactly one record, the row value is
	**auto-corrected** in-place (mutates the ``values`` dict) so the
	downstream ``doc.insert()`` receives the correct name.

	Args:
		doctype: Parent DocType name.
		values: Dict of field→value including child table lists.

	Returns:
		List of error strings (empty if all valid).
	"""
	meta = frappe.get_meta(doctype)
	errors = []

	for df in meta.fields:
		if df.fieldtype != "Table" or df.fieldname not in values:
			continue

		rows = values[df.fieldname]
		if not isinstance(rows, list):
			continue

		child_meta = frappe.get_meta(df.options)

		for i, row in enumerate(rows, 1):
			if not isinstance(row, dict):
				continue
			for child_df in child_meta.fields:
				if child_df.fieldtype == "Link" and child_df.fieldname in row:
					val = row[child_df.fieldname]
					if not val:
						continue

					# Exact match — all good
					if frappe.db.exists(child_df.options, val):
						continue

					# Fuzzy resolution
					resolved = _resolve_link_value(child_df.options, child_df.fieldname, val)
					if resolved:
						# Auto-correct the row value in-place
						row[child_df.fieldname] = resolved
					else:
						errors.append(
							f"Row {i} ({df.label or df.fieldname}): "
							f"{child_df.label or child_df.fieldname} "
							f"'{val}' not found in {child_df.options}"
						)

	return errors


def _resolve_link_value(target_doctype, fieldname, value):
	"""Try to fuzzy-resolve a Link field value to an existing document name.

	Resolution strategies (tried in order):
	1. DocType-specific name field lookup (exact, then LIKE):
	   - Item → ``item_name``
	   - Customer → ``customer_name``
	   - Supplier → ``supplier_name``
	2. LIKE search on the target DocType ``name`` field

	Args:
		target_doctype: The linked DocType (e.g. "Item", "Customer").
		fieldname: The field name (e.g. "item_code", "customer").
		value: The user-provided value that didn't match.

	Returns:
		str or None: Resolved document name, or None if not found.
	"""
	# Map of DocType → human-readable name field for fuzzy lookup
	_NAME_FIELDS = {
		"Item": "item_name",
		"Customer": "customer_name",
		"Supplier": "supplier_name",
		"Lead": "lead_name",
		"Employee": "employee_name",
	}

	# Strategy 1: look up by the DocType's human-readable name field
	name_field = _NAME_FIELDS.get(target_doctype)
	if name_field:
		# Exact match on name field
		match = frappe.db.get_value(target_doctype, {name_field: value}, "name")
		if match:
			return match

		# LIKE match on name field
		matches = frappe.get_all(
			target_doctype,
			filters={name_field: ["like", f"%{value}%"]},
			fields=["name"],
			limit=2,
		)
		if len(matches) == 1:
			return matches[0].name

	# Strategy 2: LIKE search on name field of target DocType
	matches = frappe.get_all(
		target_doctype,
		filters={"name": ["like", f"%{value}%"]},
		fields=["name"],
		limit=2,
	)
	if len(matches) == 1:
		return matches[0].name

	return None


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
