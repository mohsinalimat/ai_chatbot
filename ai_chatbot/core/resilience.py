# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Resilience Layer for AI Chatbot

Provides retry/fallback logic for LLM API calls, a circuit breaker for
external APIs, structured tool error classification, and a duplicate
tool-call loop guard.

Phase 13D — Error Recovery & Resilience.
"""

from __future__ import annotations

import hashlib
import json
import time

import frappe
import requests

from ai_chatbot.core.exceptions import ProviderAPIError
from ai_chatbot.core.logger import log_error, log_info, log_warning

# ── Error Classification for Retry ───────────────────────────────────


def classify_error_for_retry(
	error: Exception,
) -> tuple[str, float | None]:
	"""Classify an error to determine retry strategy.

	Returns:
		Tuple of (error_type, retry_after_seconds).
		error_type is one of: "rate_limit", "server_error", "timeout", "auth", "other".
		retry_after_seconds is the recommended wait time (or None).
	"""
	if isinstance(error, ProviderAPIError):
		status = error.status_code
		if status == 429:
			return ("rate_limit", error.retry_after)
		if status in (500, 502, 503):
			return ("server_error", None)
		if status in (401, 403):
			return ("auth", None)
		return ("other", None)

	if isinstance(error, requests.exceptions.RequestException):
		resp = getattr(error, "response", None)
		if resp is not None:
			status = resp.status_code
			retry_after = _parse_retry_after(resp)
			if status == 429:
				return ("rate_limit", retry_after)
			if status in (500, 502, 503):
				return ("server_error", None)
			if status in (401, 403):
				return ("auth", None)

	if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
		return ("timeout", None)

	msg = str(error).lower()
	if "timeout" in msg or "timed out" in msg:
		return ("timeout", None)

	return ("other", None)


def _parse_retry_after(response: requests.Response) -> float | None:
	"""Extract Retry-After header value in seconds."""
	header = response.headers.get("Retry-After")
	if not header:
		return None
	try:
		return float(header)
	except (ValueError, TypeError):
		return None


# ── LLM Call with Retry & Fallback ───────────────────────────────────


class LLMCallWithRetry:
	"""Wraps LLM API calls with retry logic and optional provider fallback.

	Retry policy:
		- Rate limit (429): Retry after Retry-After header value, up to max_retries.
		- Server error (500/502/503): Exponential backoff, up to max_retries.
		- Timeout: Retry once with a longer timeout.
		- Auth error (401/403): No retry — raise immediately.
		- Provider fallback: If configured, try fallback after primary exhausts retries.
	"""

	def __init__(
		self,
		primary_provider,
		fallback_provider=None,
		max_retries: int = 2,
		backoff_base: float = 1.0,
	):
		self.primary = primary_provider
		self.fallback = fallback_provider
		self.max_retries = max_retries
		self.backoff_base = backoff_base

		# Circuit breakers (keyed by provider class name)
		self._primary_cb = CircuitBreaker(type(primary_provider).__name__)
		self._fallback_cb = CircuitBreaker(type(fallback_provider).__name__) if fallback_provider else None

	def call(self, messages, tools=None, **kwargs) -> dict:
		"""Non-streaming call with retry + fallback.

		Returns the provider response dict on success.
		Raises ProviderAPIError or CircuitBreakerOpenError on failure.
		"""
		# Try primary provider
		result = self._attempt_call(self.primary, self._primary_cb, messages, tools, **kwargs)
		if result is not None:
			return result

		# Try fallback provider if configured
		if self.fallback and self._fallback_cb:
			log_warning(
				"Primary provider exhausted retries, trying fallback",
				primary=type(self.primary).__name__,
				fallback=type(self.fallback).__name__,
			)
			result = self._attempt_call(self.fallback, self._fallback_cb, messages, tools, **kwargs)
			if result is not None:
				return result

		raise ProviderAPIError(
			type(self.primary).__name__,
			status_code=0,
			message="All providers failed after retries.",
		)

	def call_stream(self, messages, tools=None, **kwargs):
		"""Streaming call — yields events; retries on retryable errors.

		On a retryable error before any tokens are yielded, restarts the
		generator. If tokens were already yielded, raises so partial
		content is preserved by the caller.
		"""
		# Try primary provider
		yield from self._attempt_stream(self.primary, self._primary_cb, messages, tools, **kwargs)

	def _attempt_call(self, provider, circuit_breaker, messages, tools, **kwargs):
		"""Try a non-streaming call with retries against a single provider."""
		provider_name = type(provider).__name__

		if circuit_breaker.is_open():
			if not circuit_breaker.allow_probe():
				log_warning(f"Circuit breaker open for {provider_name}, skipping")
				return None
			log_info(f"Circuit breaker allowing probe request for {provider_name}")

		timeout_retried = False

		for attempt in range(self.max_retries + 1):
			try:
				result = provider.chat_completion(messages, tools=tools, **kwargs)
				circuit_breaker.record_success()
				return result
			except Exception as e:
				error_type, retry_after = classify_error_for_retry(e)

				log_warning(
					f"Provider call failed (attempt {attempt + 1}/{self.max_retries + 1})",
					provider=provider_name,
					error_type=error_type,
					error=str(e)[:200],
				)

				circuit_breaker.record_failure()

				# Auth errors — never retry
				if error_type == "auth":
					raise

				# No more retries
				if attempt >= self.max_retries:
					break

				# Rate limit — honour Retry-After or use backoff
				if error_type == "rate_limit":
					wait = retry_after or (self.backoff_base * (2**attempt))
					# Cap wait at 30 seconds
					wait = min(wait, 30.0)
					log_info(f"Rate limited, waiting {wait:.1f}s before retry")
					time.sleep(wait)
					continue

				# Server error — exponential backoff
				if error_type == "server_error":
					wait = self.backoff_base * (2**attempt)
					log_info(f"Server error, backing off {wait:.1f}s")
					time.sleep(wait)
					continue

				# Timeout — retry once with original timeout (provider handles timeout)
				if error_type == "timeout" and not timeout_retried:
					timeout_retried = True
					log_info("Timeout, retrying once")
					continue

				# Other errors — don't retry
				break

		return None

	def _attempt_stream(self, provider, circuit_breaker, messages, tools, **kwargs):
		"""Try a streaming call with retries against a single provider.

		Yields events from the provider. On retryable errors before any
		tokens are yielded, retries transparently. After tokens are
		yielded, falls through to fallback or raises.
		"""
		provider_name = type(provider).__name__
		use_fallback = False

		if circuit_breaker.is_open():
			if not circuit_breaker.allow_probe():
				log_warning(f"Circuit breaker open for {provider_name} (stream)")
				use_fallback = True
			else:
				log_info(f"Circuit breaker probe for {provider_name} (stream)")

		if not use_fallback:
			timeout_retried = False
			tokens_yielded = False

			for attempt in range(self.max_retries + 1):
				try:
					for event in provider.chat_completion_stream(messages, tools=tools):
						event_type = event.get("type")

						if event_type == "error":
							# Stream-level error — classify and possibly retry
							error_content = event.get("content", "")
							status_code = event.get("status_code", 0)
							retry_after_val = event.get("retry_after")
							err = ProviderAPIError(
								provider_name,
								status_code=status_code,
								message=error_content,
								retry_after=retry_after_val,
							)

							if tokens_yielded:
								# Can't retry — content already sent to user
								circuit_breaker.record_failure()
								yield event
								return

							err_type, wait_after = classify_error_for_retry(err)
							circuit_breaker.record_failure()

							if err_type == "auth":
								yield event
								return

							if attempt < self.max_retries:
								if err_type == "rate_limit":
									wait = wait_after or (self.backoff_base * (2**attempt))
									wait = min(wait, 30.0)
									log_info(f"Stream rate limited, waiting {wait:.1f}s")
									time.sleep(wait)
								elif err_type == "server_error":
									wait = self.backoff_base * (2**attempt)
									log_info(f"Stream server error, backing off {wait:.1f}s")
									time.sleep(wait)
								elif err_type == "timeout" and not timeout_retried:
									timeout_retried = True
									log_info("Stream timeout, retrying once")
								else:
									yield event
									return
								break  # Break inner for loop to retry outer loop
							else:
								# Exhausted retries on primary
								use_fallback = True
								break
						else:
							if event_type == "token":
								tokens_yielded = True
							yield event

					else:
						# Stream completed normally (for loop ran to completion)
						circuit_breaker.record_success()
						return

					# If we broke out of the inner loop to retry, continue outer loop
					if use_fallback:
						break
					continue

				except requests.exceptions.RequestException as e:
					err_type, wait_after = classify_error_for_retry(e)
					circuit_breaker.record_failure()
					log_warning(
						f"Stream request error (attempt {attempt + 1})",
						provider=provider_name,
						error_type=err_type,
					)

					if err_type == "auth" or tokens_yielded:
						raise

					if attempt >= self.max_retries:
						use_fallback = True
						break

					if err_type == "rate_limit":
						wait = wait_after or (self.backoff_base * (2**attempt))
						time.sleep(min(wait, 30.0))
					elif err_type == "server_error":
						time.sleep(self.backoff_base * (2**attempt))
					elif err_type == "timeout" and not timeout_retried:
						timeout_retried = True
					else:
						use_fallback = True
						break

		# Fallback provider
		if use_fallback and self.fallback and self._fallback_cb:
			log_warning(
				"Primary stream exhausted retries, trying fallback",
				primary=type(self.primary).__name__,
				fallback=type(self.fallback).__name__,
			)
			yield from self._attempt_stream(self.fallback, self._fallback_cb, messages, tools, **kwargs)
			return

		if use_fallback:
			# No fallback configured — yield error
			yield {
				"type": "error",
				"content": "The AI service is temporarily unavailable. Please try again in a few minutes.",
			}


# ── Circuit Breaker ──────────────────────────────────────────────────


class CircuitBreaker:
	"""Redis-backed circuit breaker for LLM provider APIs.

	States:
		CLOSED (default) — all requests pass. On failure, record it.
			If failures in window >= threshold → trip to OPEN.
		OPEN — reject requests immediately.
			After cooldown_seconds → allow one probe (HALF_OPEN).
		HALF_OPEN — one request passes.
			On success → CLOSED. On failure → OPEN again.
	"""

	FAILURE_THRESHOLD = 5
	WINDOW_SECONDS = 60
	COOLDOWN_SECONDS = 60

	def __init__(self, provider_name: str):
		self.provider_name = provider_name
		self._key_prefix = f"ai_chatbot:cb:{provider_name}"

	def record_failure(self) -> None:
		"""Record a failure and possibly trip the circuit breaker."""
		cache = frappe.cache()
		now = time.time()
		failures_key = f"{self._key_prefix}:failures"
		open_key = f"{self._key_prefix}:open_until"

		# Add current timestamp to failures list
		failures_raw = cache.get_value(failures_key) or "[]"
		try:
			failures = json.loads(failures_raw) if isinstance(failures_raw, str) else failures_raw
		except (json.JSONDecodeError, TypeError):
			failures = []

		failures.append(now)

		# Prune entries older than the window
		cutoff = now - self.WINDOW_SECONDS
		failures = [ts for ts in failures if ts > cutoff]

		cache.set_value(failures_key, json.dumps(failures), expires_in_sec=self.WINDOW_SECONDS * 2)

		# Check if threshold is reached
		if len(failures) >= self.FAILURE_THRESHOLD:
			open_until = now + self.COOLDOWN_SECONDS
			cache.set_value(open_key, str(open_until), expires_in_sec=self.COOLDOWN_SECONDS * 2)
			log_error(
				f"Circuit breaker TRIPPED for {self.provider_name}: "
				f"{len(failures)} failures in {self.WINDOW_SECONDS}s window. "
				f"Circuit open until {open_until:.0f}.",
				title="Circuit Breaker",
			)

	def record_success(self) -> None:
		"""Record a success — reset the circuit breaker to CLOSED."""
		cache = frappe.cache()
		# Clear failure history and open state
		cache.delete_value(f"{self._key_prefix}:failures")
		cache.delete_value(f"{self._key_prefix}:open_until")
		cache.delete_value(f"{self._key_prefix}:probe")

	def is_open(self) -> bool:
		"""Check if the circuit breaker is in OPEN state."""
		cache = frappe.cache()
		open_until_raw = cache.get_value(f"{self._key_prefix}:open_until")
		if not open_until_raw:
			return False

		try:
			open_until = float(open_until_raw)
		except (ValueError, TypeError):
			return False

		return time.time() < open_until

	def allow_probe(self) -> bool:
		"""Check if a probe request should be allowed (HALF_OPEN state).

		Returns True once per cooldown period to allow a single test request.
		"""
		cache = frappe.cache()
		open_until_raw = cache.get_value(f"{self._key_prefix}:open_until")
		if not open_until_raw:
			return True

		try:
			open_until = float(open_until_raw)
		except (ValueError, TypeError):
			return True

		now = time.time()
		if now < open_until:
			return False

		# Cooldown has elapsed — allow one probe (use atomic-ish set)
		probe_key = f"{self._key_prefix}:probe"
		probe_val = cache.get_value(probe_key)
		if probe_val:
			return False  # Another worker already probing

		cache.set_value(probe_key, "1", expires_in_sec=30)
		return True

	def reset(self) -> None:
		"""Manually reset the circuit breaker to CLOSED state."""
		cache = frappe.cache()
		cache.delete_value(f"{self._key_prefix}:failures")
		cache.delete_value(f"{self._key_prefix}:open_until")
		cache.delete_value(f"{self._key_prefix}:probe")


# ── Structured Tool Error Classification ─────────────────────────────


def classify_tool_error(error: Exception, tool_name: str, arguments: dict | None = None) -> dict:
	"""Classify a tool execution error into a structured error dict.

	Returns a dict with:
		error (bool): Always True.
		error_type (str): Category of the error.
		message (str): Human-readable error message.
		suggestion (str): Guidance for the AI on how to handle this error.

	Args:
		error: The exception that was raised.
		tool_name: Name of the tool that failed.
		arguments: The arguments passed to the tool.
	"""
	error_msg = str(error)

	# Permission denied
	if isinstance(error, frappe.PermissionError):
		# Try to extract doctype from error message
		doctype = _extract_doctype_from_error(error_msg)
		return {
			"error": True,
			"error_type": "permission_denied",
			"message": f"Permission denied: {error_msg}",
			"suggestion": (
				f"The user doesn't have access to {doctype}. "
				"Inform them that they need the appropriate role/permission."
				if doctype
				else "The user doesn't have the required permissions. Inform them."
			),
		}

	# Document not found
	if isinstance(error, frappe.DoesNotExistError):
		return {
			"error": True,
			"error_type": "not_found",
			"message": f"Not found: {error_msg}",
			"suggestion": (
				"No record found matching the criteria. Ask the user to verify the name or identifier."
			),
		}

	# Validation error
	if isinstance(error, frappe.ValidationError):
		return {
			"error": True,
			"error_type": "validation_error",
			"message": f"Validation failed: {error_msg}",
			"suggestion": (
				f"Validation failed: {error_msg}. Check the input values and try again with corrected data."
			),
		}

	# Timeout-like errors
	error_lower = error_msg.lower()
	if "timeout" in error_lower or "timed out" in error_lower:
		return {
			"error": True,
			"error_type": "timeout",
			"message": f"The operation timed out: {error_msg}",
			"suggestion": (
				"The query took too long. Try narrowing the date range or adding more specific filters."
			),
		}

	# Generic execution error
	# Truncate very long error messages
	display_msg = error_msg[:300] if len(error_msg) > 300 else error_msg
	return {
		"error": True,
		"error_type": "execution_error",
		"message": f"Tool execution failed: {display_msg}",
		"suggestion": (
			f"Tool '{tool_name}' encountered an error: {display_msg}. "
			"Try a different approach or inform the user of the issue."
		),
	}


def _extract_doctype_from_error(error_msg: str) -> str:
	"""Try to extract a DocType name from a Frappe permission/existence error message."""
	# Common patterns: "No permission for Page: ..." or "... not permitted for ..."
	import re

	# "No permission for <DocType> ..." or "<DocType> <name> not found"
	patterns = [
		r"No permission for (\w[\w\s]*?)(?:\s*:|\s*$)",
		r"(\w[\w\s]*?) .+ not found",
		r"not permitted.*?(\w[\w\s]*?)(?:\s*$)",
	]
	for pattern in patterns:
		match = re.search(pattern, error_msg)
		if match:
			return match.group(1).strip()
	return ""


# ── Tool Call Loop Guard ─────────────────────────────────────────────


class ToolCallLoopGuard:
	"""Detects when the same tool is called repeatedly with identical arguments.

	The AI sometimes retries a failing tool call in a loop. This guard
	tracks (tool_name, args_hash) counts and signals when the max is reached.
	"""

	MAX_DUPLICATE_CALLS = 2

	def __init__(self):
		self._call_counts: dict[str, int] = {}

	def _make_key(self, tool_name: str, arguments: dict) -> str:
		"""Create a hashable key from tool name and arguments."""
		args_str = json.dumps(arguments, sort_keys=True, default=str)
		args_hash = hashlib.md5(args_str.encode()).hexdigest()[:12]
		return f"{tool_name}:{args_hash}"

	def record_call(self, tool_name: str, arguments: dict) -> None:
		"""Record a tool call."""
		key = self._make_key(tool_name, arguments)
		self._call_counts[key] = self._call_counts.get(key, 0) + 1

	def is_stuck(self, tool_name: str, arguments: dict) -> bool:
		"""Check if this tool+args combo has been called too many times."""
		key = self._make_key(tool_name, arguments)
		return self._call_counts.get(key, 0) >= self.MAX_DUPLICATE_CALLS

	def get_stuck_tools(self) -> list[str]:
		"""Return tool names that have exceeded the duplicate call limit."""
		stuck = []
		for key, count in self._call_counts.items():
			if count >= self.MAX_DUPLICATE_CALLS:
				tool_name = key.split(":")[0]
				if tool_name not in stuck:
					stuck.append(tool_name)
		return stuck
