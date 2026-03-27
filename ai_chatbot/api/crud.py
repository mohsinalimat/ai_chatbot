# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
CRUD Confirmation API Endpoints (Phase 13B)

Provides ``@frappe.whitelist()`` endpoints that the frontend calls when
the user clicks Confirm, Cancel, or Undo on a ConfirmationCard.

- ``confirm_action`` — execute a previously proposed write action
- ``cancel_action`` — discard a proposed action (user declined)
- ``undo_action`` — reverse a recently confirmed action (5-min TTL)
"""

import json
import uuid

import frappe

from ai_chatbot.core.logger import log_error, log_info
from ai_chatbot.data.operations import (
	cancel_document,
	create_document,
	get_document_values,
	submit_document,
	update_document,
)
from ai_chatbot.data.validators import check_permission
from ai_chatbot.tools.crud import (
	delete_pending_confirmation,
	load_pending_confirmation,
)

# Redis prefix and TTL for undo tokens
_UNDO_PREFIX = "chatbot_undo:"
_UNDO_TTL = 300  # 5 minutes


@frappe.whitelist()
def confirm_action(confirmation_id: str) -> dict:
	"""Execute a previously proposed write action after user confirmation.

	Loads the pending confirmation from Redis, re-validates permissions,
	executes the action, stores undo metadata, and returns the result.

	Args:
		confirmation_id: UUID of the pending confirmation.

	Returns:
		dict with success status, document info, and undo token.
	"""
	try:
		payload = load_pending_confirmation(confirmation_id)
		if not payload:
			return {
				"success": False,
				"error": "This confirmation has expired. Please ask the AI to propose the action again.",
			}

		action = payload.get("action")
		doctype = payload.get("doctype")
		name = payload.get("name")
		values = payload.get("values", {})

		# Check for blocking validation errors
		errors = payload.get("errors", [])
		if errors:
			return {
				"success": False,
				"error": f"Cannot proceed: {'; '.join(errors)}",
			}

		result = None
		undo_token = None
		undo_expires = None

		if action == "create":
			# Re-check create permission
			if not check_permission(doctype, "create"):
				return {"success": False, "error": f"You no longer have permission to create {doctype}"}

			result = create_document(doctype, values)
			undo_token = _store_undo_metadata(action, doctype, result["name"], previous_values=None)
			undo_expires = _undo_expiry_iso()

		elif action == "update":
			if not name:
				return {"success": False, "error": "Document name is missing"}

			# Re-check write permission
			if not check_permission(doctype, "write", name):
				return {
					"success": False,
					"error": f"You no longer have permission to update {doctype} '{name}'",
				}

			# Capture current values for undo before updating
			if values:
				prev = get_document_values(doctype, name, list(values.keys()))
			else:
				prev = {}

			result = update_document(doctype, name, values)
			undo_token = _store_undo_metadata(action, doctype, name, previous_values=prev)
			undo_expires = _undo_expiry_iso()

		elif action == "submit":
			if not name:
				return {"success": False, "error": "Document name is missing"}

			result = submit_document(doctype, name)
			# Submit cannot be undone via chatbot
			undo_token = None

		elif action == "cancel":
			if not name:
				return {"success": False, "error": "Document name is missing"}

			result = cancel_document(doctype, name)
			# Cancel cannot be undone via chatbot
			undo_token = None

		else:
			return {"success": False, "error": f"Unknown action: {action}"}

		# Clean up the pending confirmation from Redis
		delete_pending_confirmation(confirmation_id)

		# Update the message's confirmation_state
		_update_confirmation_state(confirmation_id, "confirmed", result, undo_token, undo_expires)

		log_info(
			"CRUD action confirmed",
			action=action,
			doctype=doctype,
			name=result.get("name") if result else name,
			user=frappe.session.user,
		)

		return {
			"success": True,
			"action": action,
			"doctype": doctype,
			"name": result.get("name") if result else name,
			"doc_url": result.get("doc_url", ""),
			"message": result.get("message", ""),
			"undo_token": undo_token,
			"undo_expires": undo_expires,
		}

	except Exception as e:
		log_error(f"CRUD confirm_action error: {e!s}", title="CRUD Confirm")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def cancel_action(confirmation_id: str) -> dict:
	"""Cancel a proposed action (user clicked Cancel).

	Removes the pending confirmation from Redis and updates the
	message's confirmation_state.

	Args:
		confirmation_id: UUID of the pending confirmation.

	Returns:
		dict with success status.
	"""
	try:
		delete_pending_confirmation(confirmation_id)
		_update_confirmation_state(confirmation_id, "declined")

		log_info("CRUD action declined", confirmation_id=confirmation_id, user=frappe.session.user)

		return {"success": True, "message": "Action cancelled."}

	except Exception as e:
		log_error(f"CRUD cancel_action error: {e!s}", title="CRUD Cancel")
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def undo_action(undo_token: str) -> dict:
	"""Undo a previously confirmed action.

	Validates the undo token hasn't expired (5-minute TTL) and
	executes the reverse operation.

	- Create undo: deletes the draft document (if still docstatus=0)
	- Update undo: reverts to previous field values
	- Submit/Cancel: cannot be undone via chatbot

	Args:
		undo_token: UUID of the undo metadata.

	Returns:
		dict with success status.
	"""
	try:
		key = f"{_UNDO_PREFIX}{undo_token}"
		data = frappe.cache.get_value(key)
		if not data:
			return {
				"success": False,
				"error": "Undo is no longer available (expired after 5 minutes).",
			}

		metadata = json.loads(data) if isinstance(data, str) else data
		action = metadata.get("action")
		doctype = metadata.get("doctype")
		name = metadata.get("name")

		if action == "create":
			# Undo create = delete the draft document
			if not frappe.db.exists(doctype, name):
				return {"success": False, "error": f"{doctype} '{name}' no longer exists."}

			doc = frappe.get_doc(doctype, name)
			if doc.docstatus != 0:
				return {
					"success": False,
					"error": f"Cannot undo: {doctype} '{name}' has been submitted (docstatus={doc.docstatus}).",
				}

			if not check_permission(doctype, "delete", name):
				return {
					"success": False,
					"error": f"You do not have permission to delete {doctype} '{name}'.",
				}

			frappe.delete_doc(doctype, name, force=True)
			frappe.db.commit()

			log_info("CRUD undo create", doctype=doctype, name=name, user=frappe.session.user)

		elif action == "update":
			# Undo update = revert to previous values
			previous_values = metadata.get("previous_values", {})
			if not previous_values:
				return {"success": False, "error": "No previous values stored for undo."}

			if not frappe.db.exists(doctype, name):
				return {"success": False, "error": f"{doctype} '{name}' no longer exists."}

			if not check_permission(doctype, "write", name):
				return {
					"success": False,
					"error": f"You do not have permission to update {doctype} '{name}'.",
				}

			update_document(doctype, name, previous_values)

			log_info("CRUD undo update", doctype=doctype, name=name, user=frappe.session.user)

		else:
			return {"success": False, "error": f"'{action}' actions cannot be undone via chatbot."}

		# Remove the undo token
		frappe.cache.delete_value(key)

		return {
			"success": True,
			"message": f"Successfully undone: {action} {doctype} '{name}'.",
		}

	except Exception as e:
		log_error(f"CRUD undo_action error: {e!s}", title="CRUD Undo")
		return {"success": False, "error": str(e)}


# ── Internal Helpers ─────────────────────────────────────────────────


def _store_undo_metadata(action, doctype, name, previous_values=None):
	"""Store undo metadata in Redis with 5-minute TTL.

	Args:
		action: "create" or "update".
		doctype: DocType name.
		name: Document name.
		previous_values: Dict of previous field values (for update undo).

	Returns:
		str: Undo token UUID.
	"""
	token = str(uuid.uuid4())
	key = f"{_UNDO_PREFIX}{token}"
	metadata = {
		"action": action,
		"doctype": doctype,
		"name": name,
		"previous_values": previous_values,
		"user": frappe.session.user,
	}
	frappe.cache.set_value(key, json.dumps(metadata, default=str), expires_in_sec=_UNDO_TTL)
	return token


def _undo_expiry_iso():
	"""Return the ISO timestamp when the undo token will expire (now + 5 min)."""
	from frappe.utils import add_to_date, now_datetime

	return add_to_date(now_datetime(), minutes=5).isoformat()


def _update_confirmation_state(confirmation_id, state, result=None, undo_token=None, undo_expires=None):
	"""Update the confirmation_state JSON field on the associated Chatbot Message.

	Supports multiple confirmations per message by storing state as a dict
	keyed by ``confirmation_id``.  Each entry has the shape::

		{
			"state": "confirmed" | "declined" | "expired",
			"result": { ... },
			"undo_token": "...",
			"undo_expires": "..."
		}

	Args:
		confirmation_id: UUID string.
		state: "confirmed", "declined", or "expired".
		result: Dict with action result (for confirmed state).
		undo_token: Undo token UUID (if applicable).
		undo_expires: ISO timestamp of undo expiry.
	"""
	try:
		# Find the message containing this confirmation_id in tool_results
		messages = frappe.get_all(
			"Chatbot Message",
			filters={
				"role": "assistant",
				"tool_results": ["like", f"%{confirmation_id}%"],
			},
			fields=["name", "confirmation_state"],
			limit=1,
			order_by="creation desc",
		)

		if not messages:
			return

		msg_name = messages[0].name

		# Load existing state (supports multiple confirmations per message)
		existing = {}
		raw = messages[0].confirmation_state
		if raw:
			try:
				parsed = json.loads(raw) if isinstance(raw, str) else raw
				# Migrate old single-confirmation format to multi-key format
				if isinstance(parsed, dict) and "confirmation_id" in parsed:
					old_id = parsed["confirmation_id"]
					existing[old_id] = {
						k: v for k, v in parsed.items() if k != "confirmation_id"
					}
				elif isinstance(parsed, dict):
					existing = parsed
			except (json.JSONDecodeError, TypeError):
				pass

		# Build entry for this confirmation_id
		entry = {"state": state}

		if result:
			entry["result"] = {
				"doctype": result.get("doctype"),
				"name": result.get("name"),
				"doc_url": result.get("doc_url"),
				"message": result.get("message"),
			}

		if undo_token:
			entry["undo_token"] = undo_token
			entry["undo_expires"] = undo_expires

		existing[confirmation_id] = entry

		frappe.db.set_value(
			"Chatbot Message",
			msg_name,
			"confirmation_state",
			json.dumps(existing, default=str),
		)
		frappe.db.commit()

	except Exception:
		# Non-critical — don't fail the main action
		log_error(
			f"Failed to update confirmation_state for {confirmation_id}",
			title="CRUD Confirmation State",
		)
