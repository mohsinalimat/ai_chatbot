# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Prerequisite Detection & Execution for CRUD Operations

Detects missing master records (Customer, Supplier, Item, UOM) referenced
in a document's values and provides:
  1. A structured description of what's missing (for the frontend to render
     editable fields).
  2. An execution function that creates all prerequisites in dependency
     order before the main document is created.

The editable-field definitions follow a Frappe-like schema so the frontend
can dynamically render form inputs (text, checkbox, link).
"""

from __future__ import annotations

import frappe
from frappe.utils import cstr

from ai_chatbot.data.validators import _resolve_link_value

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# DocType field → linked master DocType
_PARTY_FIELD_MAP: dict[str, str] = {
	"customer": "Customer",
	"supplier": "Supplier",
}

# Sales-family → Customer, Purchase-family → Supplier
_SALES_DOCTYPES = {
	"Sales Order",
	"Sales Invoice",
	"Quotation",
	"Delivery Note",
}
_PURCHASE_DOCTYPES = {
	"Purchase Order",
	"Purchase Invoice",
	"Purchase Receipt",
	"Supplier Quotation",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_prerequisites(doctype: str, values: dict, company: str | None = None) -> dict:
	"""Detect missing master records referenced in *values*.

	Checks:
	- Party fields (customer / supplier) against their master DocType
	- Item codes in child table rows against the Item master
	- UOM values in child table rows against the UOM master
	- Account heads in child table rows against the Account master

	Returns a structured dict suitable for the ConfirmationCard frontend::

	        {
	            "has_prerequisites": True / False,
	            "missing_parties": [...],
	            "missing_items": [...],
	            "missing_uoms": [...],
	            "missing_accounts": [...],
	        }
	"""
	company = company or frappe.defaults.get_user_default("Company")
	missing_parties = _detect_missing_parties(doctype, values, company)
	missing_items, missing_uoms = _detect_missing_items(doctype, values, company)
	missing_accounts = _detect_missing_accounts(doctype, values, company)

	has_prereqs = bool(missing_parties or missing_items or missing_uoms or missing_accounts)

	return {
		"has_prerequisites": has_prereqs,
		"missing_parties": missing_parties,
		"missing_items": missing_items,
		"missing_uoms": missing_uoms,
		"missing_accounts": missing_accounts,
	}


def execute_prerequisites(prerequisites: dict, company: str | None = None) -> dict:
	"""Create missing master records in dependency order.

	Order: UOMs → Parties → Items  (Items depend on UOM existing).

	Each prerequisite entry may carry a ``user_overrides`` dict with
	field values edited by the user on the frontend form.

	Returns::

	        {
	            "success": True / False,
	            "created": ["Customer: Acme Corp", "Item: Widget A", ...],
	            "errors": [],
	            "name_map": {
	                "customer": {"Acme Corp": "Acme Corp"},
	                "item_code": {"Widget A": "ITEM-00001"},
	            },
	        }
	"""
	company = company or frappe.defaults.get_user_default("Company")
	created: list[str] = []
	name_map: dict[str, dict[str, str]] = {}

	try:
		# Phase 0 — Accounts (tax/GL accounts in taxes child table)
		for account in prerequisites.get("missing_accounts", []):
			overrides = account.get("user_overrides", {})
			result_name = _create_account(account["value"], overrides, company)
			created.append(f"Account: {result_name}")
			name_map.setdefault(account["field"], {})[account["value"]] = result_name

		# Phase 1 — UOMs (Items reference stock_uom)
		for uom in prerequisites.get("missing_uoms", []):
			result_name = _create_uom(uom["value"])
			created.append(f"UOM: {result_name}")

		# Phase 2 — Parties (no dependency on items)
		for party in prerequisites.get("missing_parties", []):
			overrides = party.get("user_overrides", {})
			result_name = _create_party(party["doctype"], party["value"], overrides, company)
			created.append(f"{party['doctype']}: {result_name}")
			name_map.setdefault(party["field"], {})[party["value"]] = result_name

		# Phase 3 — Items
		for item in prerequisites.get("missing_items", []):
			overrides = item.get("user_overrides", {})
			result_name = _create_item(item["value"], overrides, company)
			created.append(f"Item: {result_name}")
			name_map.setdefault("item_code", {})[item["value"]] = result_name

		frappe.db.commit()
		return {
			"success": True,
			"created": created,
			"errors": [],
			"name_map": name_map,
		}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(
			title="Prerequisite Creation Failed",
			message=f"Company: {company}\nCreated so far: {created}\nError: {cstr(e)}\n\n{frappe.get_traceback()}",
		)
		return {
			"success": False,
			"created": [],
			"errors": [cstr(e)],
			"name_map": {},
		}


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _detect_missing_parties(doctype: str, values: dict, company: str) -> list[dict]:
	"""Find party fields whose value does not exist as a master record."""
	missing = []

	for field, party_doctype in _PARTY_FIELD_MAP.items():
		value = values.get(field)
		if not value:
			continue

		# Check exact match
		if frappe.db.exists(party_doctype, value):
			continue

		# Try fuzzy resolution — if resolved, update values in-place and skip
		resolved = _resolve_link_value(party_doctype, field, value)
		if resolved:
			values[field] = resolved
			continue

		# Truly missing — build editable fields for the card
		editable = _get_party_editable_fields(party_doctype, company)
		missing.append(
			{
				"doctype": party_doctype,
				"field": field,
				"value": value,
				"editable_fields": editable,
			}
		)

	return missing


def _detect_missing_items(doctype: str, values: dict, company: str) -> tuple[list[dict], list[dict]]:
	"""Find item_code / uom values in child tables that don't exist.

	Returns (missing_items, missing_uoms).
	"""
	meta = frappe.get_meta(doctype)
	missing_items: list[dict] = []
	missing_uoms: list[dict] = []
	seen_items: set[str] = set()
	seen_uoms: set[str] = set()

	for df in meta.fields:
		if df.fieldtype != "Table" or df.fieldname not in values:
			continue

		rows = values[df.fieldname]
		if not isinstance(rows, list):
			continue

		child_meta = frappe.get_meta(df.options)

		# Check which child fields are Link→Item and Link→UOM
		item_fields = [
			cdf.fieldname for cdf in child_meta.fields if cdf.fieldtype == "Link" and cdf.options == "Item"
		]
		uom_fields = [
			cdf.fieldname for cdf in child_meta.fields if cdf.fieldtype == "Link" and cdf.options == "UOM"
		]

		for row_idx, row in enumerate(rows):
			if not isinstance(row, dict):
				continue

			# --- Items ---
			for ifield in item_fields:
				val = row.get(ifield)
				if not val or val in seen_items:
					continue

				if frappe.db.exists("Item", val):
					continue

				# Fuzzy
				resolved = _resolve_link_value("Item", ifield, val)
				if resolved:
					row[ifield] = resolved
					continue

				seen_items.add(val)
				# Infer UOM from the row if present
				row_uom = None
				for uf in uom_fields:
					if row.get(uf):
						row_uom = row[uf]
						break

				editable = _get_item_editable_fields(val, row_uom, company)
				missing_items.append(
					{
						"doctype": "Item",
						"value": val,
						"row_indices": [row_idx],
						"child_table_field": df.fieldname,
						"editable_fields": editable,
					}
				)

			# --- UOMs ---
			for ufield in uom_fields:
				val = row.get(ufield)
				if not val or val in seen_uoms:
					continue
				if frappe.db.exists("UOM", val):
					continue
				seen_uoms.add(val)
				missing_uoms.append(
					{
						"doctype": "UOM",
						"value": val,
					}
				)

	# Also check for items referenced in the same row with a
	# duplicate value (append row_indices)
	_deduplicate_items(missing_items)

	return missing_items, missing_uoms


def _detect_missing_accounts(doctype: str, values: dict, company: str) -> list[dict]:
	"""Find Account link values in child tables that don't exist.

	Scans child tables (especially taxes/charges) for Link→Account fields
	whose value doesn't match any existing Account record.
	"""
	meta = frappe.get_meta(doctype)
	missing: list[dict] = []
	seen: set[str] = set()

	for df in meta.fields:
		if df.fieldtype != "Table" or df.fieldname not in values:
			continue

		rows = values[df.fieldname]
		if not isinstance(rows, list):
			continue

		child_meta = frappe.get_meta(df.options)

		account_fields = [
			cdf.fieldname for cdf in child_meta.fields if cdf.fieldtype == "Link" and cdf.options == "Account"
		]

		for row in rows:
			if not isinstance(row, dict):
				continue

			for afield in account_fields:
				val = row.get(afield)
				if not val or val in seen:
					continue

				if frappe.db.exists("Account", val):
					continue

				# Try fuzzy resolution
				resolved = _resolve_link_value("Account", afield, val)
				if resolved:
					row[afield] = resolved
					continue

				seen.add(val)
				editable = _get_account_editable_fields(val, company)
				missing.append(
					{
						"doctype": "Account",
						"field": afield,
						"value": val,
						"child_table_field": df.fieldname,
						"editable_fields": editable,
					}
				)

	return missing


def _deduplicate_items(missing_items: list[dict]) -> None:
	"""Merge entries with the same item value (different rows)."""
	by_value: dict[str, dict] = {}
	to_remove: list[int] = []

	for idx, entry in enumerate(missing_items):
		val = entry["value"]
		if val in by_value:
			by_value[val]["row_indices"].extend(entry["row_indices"])
			to_remove.append(idx)
		else:
			by_value[val] = entry

	for idx in reversed(to_remove):
		missing_items.pop(idx)


# ---------------------------------------------------------------------------
# Editable field builders
# ---------------------------------------------------------------------------


def _get_party_editable_fields(party_doctype: str, company: str) -> list[dict]:
	"""Return editable field definitions for a missing party."""
	company_currency = frappe.get_cached_value("Company", company, "default_currency") if company else ""

	if party_doctype == "Customer":
		default_group = (
			frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"
		)
		default_territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
		return [
			{
				"fieldname": "customer_group",
				"label": "Customer Group",
				"fieldtype": "Data",
				"default": default_group,
			},
			{
				"fieldname": "territory",
				"label": "Territory",
				"fieldtype": "Data",
				"default": default_territory,
			},
			{
				"fieldname": "default_currency",
				"label": "Billing Currency",
				"fieldtype": "Data",
				"default": company_currency or "",
			},
		]

	if party_doctype == "Supplier":
		default_group = (
			frappe.db.get_single_value("Buying Settings", "supplier_group") or "All Supplier Groups"
		)
		return [
			{
				"fieldname": "supplier_group",
				"label": "Supplier Group",
				"fieldtype": "Data",
				"default": default_group,
			},
			{
				"fieldname": "default_currency",
				"label": "Billing Currency",
				"fieldtype": "Data",
				"default": company_currency or "",
			},
		]

	return []


def _get_item_editable_fields(item_value: str, row_uom: str | None, company: str) -> list[dict]:
	"""Return editable field definitions for a missing item."""
	default_group = frappe.db.get_single_value("Stock Settings", "item_group") or "Products"
	default_uom = row_uom or "Nos"

	return [
		{
			"fieldname": "is_stock_item",
			"label": "Stock Item",
			"fieldtype": "Check",
			"default": 1,
		},
		{
			"fieldname": "is_fixed_asset",
			"label": "Fixed Asset",
			"fieldtype": "Check",
			"default": 0,
			"hidden_when": "is_stock_item",
		},
		{
			"fieldname": "item_group",
			"label": "Item Group",
			"fieldtype": "Data",
			"default": default_group,
		},
		{
			"fieldname": "stock_uom",
			"label": "Default UOM",
			"fieldtype": "Data",
			"default": default_uom,
		},
	]


def _get_account_editable_fields(account_value: str, company: str) -> list[dict]:
	"""Return editable field definitions for a missing Account.

	Attempts to infer sensible defaults:
	- account_name: the core name extracted from the value
	- parent_account: "Duties and Taxes - ABBR" for tax-like names, else
	  "Expenses - ABBR" as a generic default
	- account_type: "Tax" if the name suggests a tax, otherwise empty
	"""
	abbr = ""
	if company:
		abbr = frappe.get_cached_value("Company", company, "abbr") or ""

	# Strip company abbreviation if present
	core_name = account_value.rsplit(" - ", 1)[0].strip() if " - " in account_value else account_value.strip()

	# Infer if this is a tax account
	tax_keywords = {"tax", "gst", "igst", "sgst", "cgst", "vat", "cess", "tds", "tcs", "duty", "excise"}
	is_tax = bool(tax_keywords & set(core_name.lower().split()))

	# Try to find a suitable parent account
	default_parent = ""
	if is_tax and abbr:
		# Look for "Duties and Taxes" parent
		candidate = frappe.db.get_value(
			"Account",
			{"account_name": "Duties and Taxes", "company": company, "is_group": 1},
			"name",
		)
		if candidate:
			default_parent = candidate
	if not default_parent and abbr:
		# Fallback: "Indirect Expenses" or first Expense group
		candidate = frappe.db.get_value(
			"Account",
			{"account_name": "Indirect Expenses", "company": company, "is_group": 1},
			"name",
		)
		if candidate:
			default_parent = candidate

	return [
		{
			"fieldname": "account_name",
			"label": "Account Name",
			"fieldtype": "Data",
			"default": core_name,
		},
		{
			"fieldname": "parent_account",
			"label": "Parent Account",
			"fieldtype": "Data",
			"default": default_parent,
		},
		{
			"fieldname": "account_type",
			"label": "Account Type",
			"fieldtype": "Data",
			"default": "Tax" if is_tax else "",
		},
	]


# ---------------------------------------------------------------------------
# Creation helpers
# ---------------------------------------------------------------------------


def _create_party(party_doctype: str, value: str, overrides: dict, company: str) -> str:
	"""Create a Customer or Supplier master record.

	Returns the created document's ``name``.
	"""
	name_field = {
		"Customer": "customer_name",
		"Supplier": "supplier_name",
	}.get(party_doctype, "name")

	doc_values = {name_field: value}

	if party_doctype == "Customer":
		doc_values["customer_group"] = (
			overrides.get("customer_group")
			or frappe.db.get_single_value("Selling Settings", "customer_group")
			or "All Customer Groups"
		)
		doc_values["territory"] = (
			overrides.get("territory")
			or frappe.db.get_single_value("Selling Settings", "territory")
			or "All Territories"
		)
		if overrides.get("default_currency"):
			doc_values["default_currency"] = overrides["default_currency"]

	elif party_doctype == "Supplier":
		doc_values["supplier_group"] = (
			overrides.get("supplier_group")
			or frappe.db.get_single_value("Buying Settings", "supplier_group")
			or "All Supplier Groups"
		)
		if overrides.get("default_currency"):
			doc_values["default_currency"] = overrides["default_currency"]

	doc = frappe.new_doc(party_doctype)
	doc.update(doc_values)
	doc.insert(ignore_permissions=False)
	return doc.name


def _create_item(item_value: str, overrides: dict, company: str) -> str:
	"""Create an Item master record.

	Returns the created document's ``name``.
	"""
	doc_values = {
		"item_code": item_value,
		"item_name": item_value,
		"item_group": (
			overrides.get("item_group")
			or frappe.db.get_single_value("Stock Settings", "item_group")
			or "Products"
		),
		"stock_uom": overrides.get("stock_uom") or "Nos",
		"is_stock_item": int(overrides.get("is_stock_item", 1)),
		"is_fixed_asset": int(overrides.get("is_fixed_asset", 0)),
	}

	doc = frappe.new_doc("Item")
	doc.update(doc_values)
	doc.insert(ignore_permissions=False)
	return doc.name


def _create_uom(uom_name: str) -> str:
	"""Create a UOM record if it doesn't exist.

	Returns the UOM name.
	"""
	if frappe.db.exists("UOM", uom_name):
		return uom_name

	doc = frappe.new_doc("UOM")
	doc.uom_name = uom_name
	doc.insert(ignore_permissions=False)
	return doc.name


def _create_account(account_value: str, overrides: dict, company: str) -> str:
	"""Create an Account master record.

	ERPNext Account ``name`` is auto-generated as ``account_name - ABBR``.

	Multi-company hierarchy handling:
	If the target company is a child in a company hierarchy, ERPNext requires
	the account to exist in the root company first.  We detect this and create
	the account in the root company — ERPNext auto-syncs it to all children.

	Args:
		account_value: The original value from the extracted data.
		overrides: User-edited fields (account_name, parent_account, account_type).
		company: Company for the account.

	Returns:
		The created Account's ``name`` (e.g., "IGST - TT").
	"""
	account_name = overrides.get("account_name") or account_value
	# Strip abbreviation suffix if the user left it in
	if " - " in account_name:
		account_name = account_name.rsplit(" - ", 1)[0].strip()

	parent_account = overrides.get("parent_account", "")
	account_type = overrides.get("account_type", "")

	# --- Multi-company hierarchy detection ---
	# If the target company is a child, create the account in the root company
	# first.  ERPNext will auto-sync it to all descendants.
	root_company = _get_root_company(company)
	creation_company = root_company or company

	# Resolve parent_account for the creation company.  The user-provided
	# parent_account has the *target* company's abbreviation (e.g.,
	# "Duties and Taxes - TTD").  If we're creating in the root company
	# instead, we need the root-company equivalent.
	if root_company and parent_account:
		parent_account = _find_parent_account_in_company(parent_account, root_company) or parent_account

	# Determine root_type from the parent account if possible
	root_type = ""
	if parent_account:
		root_type = frappe.get_cached_value("Account", parent_account, "root_type") or ""

	doc = frappe.new_doc("Account")
	doc.account_name = account_name
	doc.company = creation_company
	doc.parent_account = parent_account
	doc.account_type = account_type
	doc.root_type = root_type
	doc.is_group = 0
	doc.insert(ignore_permissions=False)

	# If created in the root company, return the auto-synced account
	# name in the target (child) company.
	if root_company:
		child_abbr = frappe.get_cached_value("Company", company, "abbr") or ""
		child_account_name = f"{account_name} - {child_abbr}" if child_abbr else account_name
		# Wait for the auto-sync: check if the account now exists in the child
		if frappe.db.exists("Account", child_account_name):
			return child_account_name
		# Fallback: return the root account name (the child may need a manual sync)
		return doc.name

	return doc.name


def _get_root_company(company: str) -> str | None:
	"""Return the root (topmost) company if *company* is a child, else None."""
	from frappe.utils.nestedset import get_ancestors_of

	try:
		ancestors = get_ancestors_of("Company", company, "lft asc")
		return ancestors[0] if ancestors else None
	except Exception:
		return None


def _find_parent_account_in_company(parent_account: str, target_company: str) -> str | None:
	"""Find the equivalent of *parent_account* in *target_company*.

	``parent_account`` is typically like "Duties and Taxes - TTD" (child company).
	We need the same account_name in the target (root) company.
	"""
	# Extract account_name from the parent_account identifier
	parent_name = frappe.get_cached_value("Account", parent_account, "account_name")
	if not parent_name:
		# parent_account might already be just a name without abbreviation
		parent_name = (
			parent_account.rsplit(" - ", 1)[0].strip() if " - " in parent_account else parent_account
		)

	# Look for the same account_name in the target company
	return frappe.db.get_value(
		"Account",
		{"account_name": parent_name, "company": target_company, "is_group": 1},
		"name",
	)
