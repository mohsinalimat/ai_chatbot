# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Shared Report Execution Infrastructure (Phase 12B)

Core helpers used by all report wrapper tools:
- run_report(): calls execute() and normalizes inconsistent return tuples
- normalize_columns(): handles ERPNext's mixed column format
- strip_columns_for_ai(): removes hidden/all-zero columns to save tokens
- get_fiscal_year_name(): resolves fiscal year name string
- build_financial_filters(): constructs the complex filter dict for P&L/BS/CF
- erpnext_chart_to_echart(): converts ERPNext chart format to ECharts option
- build_report_response(): assembles the final tool response dict
"""

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe.utils import flt, nowdate

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.data.charts import build_bar_chart, build_line_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.common import primary

# ── Column string pattern ──────────────────────────────────────────
# ERPNext sometimes returns column specs as strings like:
#   "posting_date:Date:90"
#   "account:Link/Account:200"
#   "debit:Currency/currency:120"
_COLUMN_STRING_RE = re.compile(
	r"^(?P<fieldname>[^:]+)"  # fieldname (before first colon)
	r"(?::(?P<fieldtype>[^/:]+))?"  # optional fieldtype
	r"(?:/(?P<options>[^:]+))?"  # optional /options
	r"(?::(?P<width>\d+))?$"  # optional :width
)


# ═══════════════════════════════════════════════════════════════════
# Column normalization
# ═══════════════════════════════════════════════════════════════════


def normalize_columns(raw_columns: list) -> list[dict]:
	"""Normalize ERPNext's mixed column format to consistent dicts.

	ERPNext reports return columns in two formats:
	1. Dict: {"fieldname": "account", "label": "Account", "fieldtype": "Link", ...}
	2. String: "account:Link/Account:200" or "posting_date:Date:90"

	Args:
		raw_columns: List of column definitions (mixed format).

	Returns:
		List of normalized column dicts with fieldname, label, fieldtype, options, width.
	"""
	normalized = []
	for col in raw_columns:
		if isinstance(col, dict):
			normalized.append(
				{
					"fieldname": col.get("fieldname", ""),
					"label": col.get("label", col.get("fieldname", "")),
					"fieldtype": col.get("fieldtype", "Data"),
					"options": col.get("options", ""),
					"width": col.get("width", 120),
					"hidden": col.get("hidden", False),
				}
			)
		elif isinstance(col, str):
			match = _COLUMN_STRING_RE.match(col)
			if match:
				fieldname = match.group("fieldname") or col
				fieldtype = match.group("fieldtype") or "Data"
				options = match.group("options") or ""
				width = int(match.group("width")) if match.group("width") else 120
				# Use fieldname as label, replacing underscores with spaces and title-casing
				label = fieldname.replace("_", " ").title()
				normalized.append(
					{
						"fieldname": fieldname,
						"label": label,
						"fieldtype": fieldtype,
						"options": options,
						"width": width,
						"hidden": False,
					}
				)
			else:
				normalized.append(
					{
						"fieldname": col,
						"label": col.replace("_", " ").title(),
						"fieldtype": "Data",
						"options": "",
						"width": 120,
						"hidden": False,
					}
				)
		else:
			continue

	return normalized


def strip_columns_for_ai(columns: list[dict], data: list[dict]) -> tuple[list[dict], list[dict]]:
	"""Remove hidden columns and columns with all-zero/empty values.

	Reduces token usage by stripping columns the AI doesn't need.

	Args:
		columns: Normalized column definitions.
		data: Report data rows.

	Returns:
		Tuple of (filtered_columns, filtered_data).
	"""
	if not columns or not data:
		return columns, data

	# Find columns to keep
	keep_fieldnames = []
	for col in columns:
		if col.get("hidden"):
			continue

		fieldname = col["fieldname"]

		# Check if column has any non-empty values
		has_value = False
		for row in data:
			val = row.get(fieldname)
			if val is not None and val != "" and val != 0 and val != 0.0:
				has_value = True
				break

		if has_value:
			keep_fieldnames.append(fieldname)

	# Filter columns
	filtered_columns = [c for c in columns if c["fieldname"] in keep_fieldnames]

	# Filter data to only include kept fieldnames
	filtered_data = []
	for row in data:
		filtered_row = {k: v for k, v in row.items() if k in keep_fieldnames}
		filtered_data.append(filtered_row)

	return filtered_columns, filtered_data


# ═══════════════════════════════════════════════════════════════════
# Report execution
# ═══════════════════════════════════════════════════════════════════


def run_report(
	execute_fn,
	filters: dict,
	max_rows: int = 50,
) -> dict[str, Any]:
	"""Execute an ERPNext report and normalize the result.

	Handles the inconsistent return tuples from different reports:
	- 2-tuple: (columns, data)
	- 4-tuple: (columns, data, message, chart)
	- 5-tuple: (columns, data, message, chart, report_summary)
	- 6-tuple: (columns, data, message, chart, report_summary, skip_total_row)

	Args:
		execute_fn: The report's execute() function.
		filters: Filter dict (report-specific).
		max_rows: Maximum data rows to return (truncates with metadata).

	Returns:
		Normalized dict with columns, data, row_count, and optional
		message, chart, report_summary fields.

	Raises:
		frappe.ValidationError: If the report raises a validation error.
	"""
	raw = execute_fn(frappe._dict(filters))

	# Handle None or empty result
	if not raw:
		return {
			"columns": [],
			"data": [],
			"row_count": 0,
			"message": "Report returned no data. It may be a Prepared Report that requires background processing.",
		}

	# Handle dict result (some reports return a dict directly)
	if isinstance(raw, dict):
		columns = normalize_columns(raw.get("columns", []))
		data = _normalize_data(raw.get("result", raw.get("data", [])), columns)
		return _build_result(
			columns,
			data,
			max_rows,
			message=raw.get("message"),
			chart=raw.get("chart"),
			report_summary=raw.get("report_summary"),
		)

	# Handle tuple results of varying length
	if not isinstance(raw, (tuple, list)):
		return {"columns": [], "data": [], "row_count": 0, "message": "Unexpected report result format"}

	length = len(raw)
	columns_raw = raw[0] if length > 0 else []
	data_raw = raw[1] if length > 1 else []
	message = raw[2] if length > 2 else None
	chart = raw[3] if length > 3 else None
	report_summary = raw[4] if length > 4 else None
	# raw[5] is skip_total_row — not needed for AI output

	columns = normalize_columns(columns_raw or [])
	data = _normalize_data(data_raw or [], columns)

	return _build_result(columns, data, max_rows, message=message, chart=chart, report_summary=report_summary)


def _normalize_data(data_raw: list, columns: list[dict]) -> list[dict]:
	"""Normalize report data rows to list of dicts.

	Some reports return data as list-of-lists (positional), others as
	list-of-dicts. Normalize to list-of-dicts using column fieldnames.

	Args:
		data_raw: Raw data from execute().
		columns: Normalized column definitions.

	Returns:
		List of dicts keyed by column fieldnames.
	"""
	if not data_raw:
		return []

	# Already list of dicts
	if isinstance(data_raw[0], dict):
		return [dict(row) for row in data_raw]

	# List of lists — map by column position
	fieldnames = [c["fieldname"] for c in columns]
	result = []
	for row in data_raw:
		if isinstance(row, (list, tuple)):
			row_dict = {}
			for i, val in enumerate(row):
				if i < len(fieldnames):
					row_dict[fieldnames[i]] = val
			result.append(row_dict)

	return result


def _build_result(
	columns: list[dict],
	data: list[dict],
	max_rows: int,
	message: Any = None,
	chart: Any = None,
	report_summary: Any = None,
) -> dict[str, Any]:
	"""Build the normalized result dict with truncation."""
	total_rows = len(data)

	# Round all float values
	data = _round_data(data)

	# Truncate
	truncated = False
	if max_rows and total_rows > max_rows:
		data = data[:max_rows]
		truncated = True

	result: dict[str, Any] = {
		"columns": columns,
		"data": data,
		"row_count": total_rows,
	}

	if truncated:
		result["_truncated"] = True
		result["_total_rows"] = total_rows

	if message:
		result["message"] = str(message) if not isinstance(message, str) else message

	if chart:
		result["chart"] = chart

	if report_summary:
		result["report_summary"] = report_summary

	return result


def _round_data(data: list[dict], precision: int = 2) -> list[dict]:
	"""Round all float values in data rows."""
	rounded = []
	for row in data:
		new_row = {}
		for k, v in row.items():
			if isinstance(v, float):
				new_row[k] = flt(v, precision)
			else:
				new_row[k] = v
		rounded.append(new_row)
	return rounded


# ═══════════════════════════════════════════════════════════════════
# Fiscal year helpers
# ═══════════════════════════════════════════════════════════════════


# ── Report template resolution (reserved for future use) ──────────
# When ERPNext's Financial Report Template and Account Category setup
# is properly configured, the template-based FinancialReportEngine
# code path can produce structured financial statements. Currently
# disabled because:
# 1. Account Category is a v17+ feature — may not be configured
# 2. The template path returns a 4-tuple (no report_summary),
#    while the standard path returns a 6-tuple (with report_summary)
#    which we rely on for CFO dashboard KPIs
#
# To re-enable: uncomment the constants and function below, add
# report_type parameter back to build_financial_filters(), and call
# resolve_report_template(report_type) to set filters["report_template"].
#
# _REPORT_TYPE_MAP = {
# 	"profit_and_loss": "Profit and Loss Statement",
# 	"balance_sheet": "Balance Sheet",
# 	"cash_flow": "Cash Flow",
# }
#
# _TEMPLATE_FALLBACKS = {
# 	"Profit and Loss Statement": "Default Profit and Loss Statement",
# 	"Balance Sheet": "Default Balance Sheet",
# 	"Cash Flow": "Default Cash Flow",
# }
#
#
# def resolve_report_template(report_type: str) -> str:
# 	"""Resolve the Financial Report Template name for a given report type.
#
# 	Looks up the standard template from the DB. Falls back to hardcoded
# 	default names if the DB lookup fails or returns nothing.
#
# 	Args:
# 		report_type: One of "profit_and_loss", "balance_sheet", "cash_flow".
#
# 	Returns:
# 		Financial Report Template name string, or empty string if not found.
# 	"""
# 	report_name = _REPORT_TYPE_MAP.get(report_type, "")
# 	if not report_name:
# 		return ""
#
# 	try:
# 		templates = frappe.get_all(
# 			"Financial Report Template",
# 			filters={"report": report_name},
# 			pluck="name",
# 			limit=1,
# 		)
# 		if templates:
# 			return templates[0]
# 	except Exception:
# 		pass
#
# 	return _TEMPLATE_FALLBACKS.get(report_name, "")


def get_fiscal_year_name(company: str | None = None) -> str:
	"""Get the fiscal year name string for the current date.

	Args:
		company: Company name. Resolved via get_default_company if not provided.

	Returns:
		Fiscal year name string (e.g. "2025-2026").
	"""
	company = get_default_company(company)
	try:
		from erpnext.accounts.utils import get_fiscal_year

		fy = get_fiscal_year(date=nowdate(), company=company)
		return str(fy[0])  # fy[0] is the fiscal year name
	except Exception:
		return ""


def build_financial_filters(
	company: str,
	from_date: str | None = None,
	to_date: str | None = None,
	periodicity: str = "Yearly",
	cost_center: str | None = None,
	project: str | None = None,
) -> dict:
	"""Build the complex filter dict required by P&L, Balance Sheet, Cash Flow reports.

	Uses the standard (non-template) code path which works on all ERPNext versions
	and does not require Account Category or Financial Report Template setup.
	The standard path returns a 6-tuple including report_summary, which the
	template-based FinancialReportEngine path (4-tuple) omits.

	Args:
		company: Company name.
		from_date: Start date (YYYY-MM-DD). Defaults to fiscal year start.
		to_date: End date (YYYY-MM-DD). Defaults to fiscal year end.
		periodicity: One of "Monthly", "Quarterly", "Half-Yearly", "Yearly".
		cost_center: Optional cost center filter.
		project: Optional project filter.

	Returns:
		Dict of filters ready for the report's execute() function.
	"""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	fy_name = get_fiscal_year_name(company)

	filters = {
		"company": company,
		"filter_based_on": "Date Range",
		"period_start_date": from_date,
		"period_end_date": to_date,
		"from_fiscal_year": fy_name,
		"to_fiscal_year": fy_name,
		"periodicity": periodicity,
	}

	if cost_center:
		filters["cost_center"] = cost_center
	if project:
		filters["project"] = project

	return filters


# ═══════════════════════════════════════════════════════════════════
# Chart conversion
# ═══════════════════════════════════════════════════════════════════


def erpnext_chart_to_echart(chart_data: dict | None) -> dict | None:
	"""Convert ERPNext's native chart format to ECharts option format.

	ERPNext charts use the format:
		{"data": {"labels": [...], "datasets": [{"name": ..., "values": [...]}]}, "type": "bar"}

	Converts to ECharts option using the existing data/charts.py builders.

	Args:
		chart_data: ERPNext chart dict, or None.

	Returns:
		ECharts option dict, or None if no valid chart data.
	"""
	if not chart_data or not isinstance(chart_data, dict):
		return None

	data = chart_data.get("data")
	if not data or not isinstance(data, dict):
		return None

	labels = data.get("labels", [])
	datasets = data.get("datasets", [])
	chart_type = chart_data.get("type", "bar")

	if not labels or not datasets:
		return None

	# Single dataset — use simple chart
	if len(datasets) == 1:
		ds = datasets[0]
		values = ds.get("values", [])
		name = ds.get("name", "Value")

		if chart_type == "line":
			return build_line_chart(
				title=name,
				categories=labels,
				series_data=values,
				y_axis_name="Amount",
				series_name=name,
			)
		else:
			return build_bar_chart(
				title=name,
				categories=labels,
				series_data=values,
				y_axis_name="Amount",
				series_name=name,
			)

	# Multiple datasets — use multi-series chart
	from ai_chatbot.data.charts import build_multi_series_chart

	series_list = [
		{"name": ds.get("name", f"Series {i}"), "data": ds.get("values", [])} for i, ds in enumerate(datasets)
	]

	return build_multi_series_chart(
		title="Report Chart",
		categories=labels,
		series_list=series_list,
		y_axis_name="Amount",
		chart_type="line" if chart_type == "line" else "bar",
	)


# ═══════════════════════════════════════════════════════════════════
# Response builder
# ═══════════════════════════════════════════════════════════════════


def get_report_data(
	execute_fn,
	filters: dict,
	max_rows: int = 200,
) -> dict[str, Any]:
	"""Execute an ERPNext report and return normalized data for internal consumption.

	Unlike build_report_response(), this returns the raw normalized result without
	currency metadata or column stripping — intended for composite tools (e.g. CFO
	dashboard) that extract specific values from multiple reports.

	Args:
		execute_fn: The report's execute() function.
		filters: Filter dict (report-specific).
		max_rows: Maximum data rows to return.

	Returns:
		Normalized dict from run_report() with columns, data, row_count,
		and optional message, chart, report_summary.
	"""
	return run_report(execute_fn, filters, max_rows=max_rows)


def build_report_response(
	report_result: dict,
	company: str | list[str],
	max_rows: int = 50,
) -> dict:
	"""Assemble the final tool response from a normalized report result.

	Applies column stripping, chart conversion, and adds standard
	company/currency metadata.

	Args:
		report_result: Normalized result from run_report().
		company: Company name or list of companies.
		max_rows: Maximum rows (already applied by run_report, used for reference).

	Returns:
		Final tool response dict with currency/company metadata.
	"""
	columns = report_result.get("columns", [])
	data = report_result.get("data", [])

	# Strip unnecessary columns for token efficiency
	columns, data = strip_columns_for_ai(columns, data)

	response: dict[str, Any] = {
		"data": data,
		"row_count": report_result.get("row_count", len(data)),
	}

	if report_result.get("_truncated"):
		response["_truncated"] = True
		response["_total_rows"] = report_result["_total_rows"]

	if report_result.get("message"):
		response["message"] = report_result["message"]

	if report_result.get("report_summary"):
		response["report_summary"] = report_result["report_summary"]

	# Convert chart to ECharts format
	chart = report_result.get("chart")
	if chart:
		echart = erpnext_chart_to_echart(chart)
		if echart:
			response["echart_option"] = echart

	return build_currency_response(response, primary(company))
