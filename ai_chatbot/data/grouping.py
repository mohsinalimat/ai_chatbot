# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Multi-Dimensional Grouping Engine for AI Chatbot

Provides hierarchical data aggregation across multiple dimensions
(territory, customer_group, item_group, etc.) and time periods
(monthly, quarterly, yearly) using frappe.qb. No raw SQL.
"""

from collections import OrderedDict

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates

# Metric definitions — maps metric names to their source doctypes and fields
METRIC_CONFIG = {
	"revenue": {
		"doctype": "Sales Invoice",
		"sum_field": "base_grand_total",
		"date_field": "posting_date",
		"base_filters": {"docstatus": 1},
	},
	"expenses": {
		"doctype": "Purchase Invoice",
		"sum_field": "base_grand_total",
		"date_field": "posting_date",
		"base_filters": {"docstatus": 1},
	},
	"profit": None,  # computed: revenue - expenses
	"orders": {
		"doctype": "Sales Order",
		"sum_field": "base_grand_total",
		"date_field": "transaction_date",
		"base_filters": {"docstatus": 1},
	},
}

# Dimension definitions — maps dimension names to doctype fields
# Dimensions with "child_table" require a JOIN to that child table
DIMENSION_FIELDS = {
	"company": {"field": "company", "label": "Company"},
	"territory": {"field": "territory", "label": "Territory"},
	"customer_group": {"field": "customer_group", "label": "Customer Group"},
	"customer": {"field": "customer", "label": "Customer"},
	"item_group": {
		"field": "item_group",
		"label": "Item Group",
		"child_table": {
			"Sales Invoice": "Sales Invoice Item",
			"Purchase Invoice": "Purchase Invoice Item",
			"Sales Order": "Sales Order Item",
		},
		"child_sum_field": "base_amount",
	},
	"cost_center": {"field": "cost_center", "label": "Cost Center"},
	"department": {"field": "department", "label": "Department"},
}

# Period format strings for frappe.qb DateFormat
PERIOD_FORMATS = {
	"monthly": "%Y-%m",
	"yearly": "%Y",
	# quarterly handled via custom function
}

MAX_DIMENSIONS = 3


def _get_accounting_dimensions():
	"""Discover accounting dimensions created in ERPNext.

	Returns a dict of dimension definitions in the same format as DIMENSION_FIELDS,
	keyed by fieldname. Only returns non-disabled dimensions.
	"""
	try:
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			get_accounting_dimensions,
		)
	except ImportError:
		return {}

	dims = get_accounting_dimensions(as_list=False)
	result = {}
	for d in dims:
		fieldname = d.get("fieldname")
		label = d.get("label")
		if fieldname and label:
			result[fieldname] = {"field": fieldname, "label": label}
	return result


def get_all_dimensions():
	"""Return all available dimensions: built-in + accounting dimensions.

	This is the authoritative source of supported dimensions for tools.
	"""
	all_dims = dict(DIMENSION_FIELDS)
	all_dims.update(_get_accounting_dimensions())
	return all_dims


def resolve_dimension_name(name, all_dims):
	"""Resolve a user-provided dimension name to the actual fieldname.

	Handles common variations:
	- Exact match: "territory" → "territory"
	- Space to underscore: "business vertical" → "business_vertical"
	- Case insensitive: "Business Vertical" → "business_vertical"
	- Label match: "Business Vertical" matches dim with label "Business Vertical"
	- Suffix/partial match: "vertical" → "business_vertical", "segment" → "business_segment"

	Returns the resolved fieldname or None if no match.
	"""
	# Exact match
	if name in all_dims:
		return name

	# Normalize: lowercase, replace spaces/hyphens with underscores
	normalized = name.lower().strip().replace(" ", "_").replace("-", "_")
	if normalized in all_dims:
		return normalized

	# Match by label (case-insensitive)
	name_lower = name.lower().strip()
	for key, config in all_dims.items():
		if config.get("label", "").lower() == name_lower:
			return key

	# Suffix match on fieldname: "vertical" matches "business_vertical"
	suffix_matches = [key for key in all_dims if key.endswith(f"_{normalized}") or key == normalized]
	if len(suffix_matches) == 1:
		return suffix_matches[0]

	# Partial word match on label: "vertical" matches "Business Vertical"
	label_matches = [
		key
		for key, config in all_dims.items()
		if normalized.replace("_", " ") in config.get("label", "").lower().split()
	]
	if len(label_matches) == 1:
		return label_matches[0]

	# Contains match on fieldname: "vertical" is contained in "business_vertical"
	contains_matches = [key for key in all_dims if normalized in key]
	if len(contains_matches) == 1:
		return contains_matches[0]

	return None


def _validate_dimension_on_doctype(dim_config, doctype):
	"""Check if a dimension field actually exists on the given doctype.

	Returns True if the field exists (either as a standard or custom field).
	"""
	field_name = dim_config["field"]
	# child_table dimensions are on the child, not the parent
	if "child_table" in dim_config:
		child_dt = dim_config["child_table"].get(doctype)
		if child_dt:
			meta = frappe.get_meta(child_dt)
		else:
			return False
	else:
		meta = frappe.get_meta(doctype)
	return meta.has_field(field_name)


def get_grouped_metric(
	metric: str,
	group_by: list[str],
	period: str = "quarterly",
	from_date: str | None = None,
	to_date: str | None = None,
	company: str | None = None,
) -> dict:
	"""Execute a multi-dimensional grouped aggregation.

	Args:
		metric: What to measure — "revenue", "expenses", "profit", "orders".
		group_by: List of dimension names to group by (max 3).
		period: Time grouping — "monthly", "quarterly", "yearly".
		from_date: Start date (YYYY-MM-DD). Defaults to fiscal year start.
		to_date: End date (YYYY-MM-DD). Defaults to fiscal year end.
		company: Company name. Defaults to user's default.

	Returns:
		Dict with "headers" (list[str]) and "rows" (list[dict]).
		Each row: {description, level, is_group, values: [total, period1, ...]}.
	"""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	# Determine companies to query (parent + subsidiaries if session says so)
	conversation_id = getattr(frappe.flags, "current_conversation_id", None)
	query_companies = company
	if conversation_id:
		try:
			from ai_chatbot.core.session_context import get_companies_for_query

			companies_list = get_companies_for_query(company, conversation_id)
			if len(companies_list) > 1:
				query_companies = companies_list
		except Exception:
			pass

	# Validate inputs
	if metric not in METRIC_CONFIG:
		frappe.throw(f"Unsupported metric: {metric}. Supported: {', '.join(METRIC_CONFIG.keys())}")

	all_dims = get_all_dimensions()

	# Resolve dimension names (handle spaces, case variations, labels)
	resolved_group_by = []
	for dim in group_by:
		resolved = resolve_dimension_name(dim, all_dims)
		if resolved is None:
			frappe.throw(f"Unsupported dimension: {dim}. Supported: {', '.join(all_dims.keys())}")
		resolved_group_by.append(resolved)
	group_by = resolved_group_by

	# When grouping by "company", auto-expand to include subsidiaries so there
	# is meaningful cross-company data to group.  Only expands if the current
	# query_companies is still a single company (i.e. session didn't already
	# include subsidiaries).
	if "company" in group_by and not isinstance(query_companies, (list, tuple)):
		try:
			from ai_chatbot.core.consolidation import get_child_companies, is_parent_company

			if is_parent_company(company):
				children = get_child_companies(company)
				if children:
					query_companies = [company, *list(children)]
		except Exception:
			pass

	if len(group_by) > MAX_DIMENSIONS:
		frappe.throw(f"Maximum {MAX_DIMENSIONS} dimensions allowed, got {len(group_by)}")

	# For non-profit metrics, validate dimension fields exist on the target doctype
	if metric != "profit":
		config = METRIC_CONFIG[metric]
		for dim in group_by:
			dim_config = all_dims[dim]
			if not _validate_dimension_on_doctype(dim_config, config["doctype"]):
				frappe.throw(
					f"Dimension '{dim}' (field: {dim_config['field']}) does not exist on "
					f"{config['doctype']}. It may not be set up as an accounting dimension for this doctype."
				)

	period_columns = _build_period_columns(from_date, to_date, period)

	if metric == "profit":
		return _get_profit_grouped(
			group_by, period, from_date, to_date, query_companies, period_columns, all_dims
		)

	config = METRIC_CONFIG[metric]
	flat_rows = _build_and_run_query(config, group_by, period, from_date, to_date, query_companies, all_dims)
	hierarchical = _pivot_to_hierarchical(flat_rows, group_by, period_columns)

	# Build headers: "Particular" as first column + "Total" + period columns
	headers = ["Particular", "Total", *period_columns]

	return {"headers": headers, "rows": hierarchical}


def _get_profit_grouped(group_by, period, from_date, to_date, company, period_columns, all_dims):
	"""Compute profit as revenue - expenses, both grouped identically."""
	rev_config = METRIC_CONFIG["revenue"]
	exp_config = METRIC_CONFIG["expenses"]

	# Validate dimensions exist on both doctypes
	for dim in group_by:
		dim_config = all_dims[dim]
		for config in (rev_config, exp_config):
			if not _validate_dimension_on_doctype(dim_config, config["doctype"]):
				frappe.throw(
					f"Dimension '{dim}' (field: {dim_config['field']}) does not exist on "
					f"{config['doctype']}. It may not be set up as an accounting dimension for this doctype."
				)

	rev_rows = _build_and_run_query(rev_config, group_by, period, from_date, to_date, company, all_dims)
	exp_rows = _build_and_run_query(exp_config, group_by, period, from_date, to_date, company, all_dims)

	# Index expense rows by (dimension values, period) for fast lookup
	exp_map = {}
	for row in exp_rows:
		dims = tuple(row.get(f"dim_{i}") for i in range(len(group_by)))
		p = row.get("period_label", "")
		exp_map[(dims, p)] = flt(row.get("total", 0))

	# Subtract expenses from revenue
	profit_rows = []
	for row in rev_rows:
		dims = tuple(row.get(f"dim_{i}") for i in range(len(group_by)))
		p = row.get("period_label", "")
		revenue = flt(row.get("total", 0))
		expense = exp_map.get((dims, p), 0)
		row["total"] = flt(revenue - expense, 2)
		profit_rows.append(row)

	hierarchical = _pivot_to_hierarchical(profit_rows, group_by, period_columns)

	headers = ["Particular", "Total", *period_columns]

	return {"headers": headers, "rows": hierarchical}


def _build_period_columns(from_date, to_date, period):
	"""Generate ordered period labels between from_date and to_date.

	Args:
		from_date: Start date string.
		to_date: End date string.
		period: "monthly", "quarterly", "yearly".

	Returns:
		List of period label strings, e.g. ["2025-Q1", "2025-Q2", ...].
	"""
	start = getdate(from_date)
	end = getdate(to_date)
	columns = []

	if period == "yearly":
		year = start.year
		while year <= end.year:
			columns.append(str(year))
			year += 1

	elif period == "quarterly":
		# Iterate month-by-month, track quarters
		current = get_first_day(start)
		seen = set()
		while getdate(current) <= end:
			q = (getdate(current).month - 1) // 3 + 1
			label = f"{getdate(current).year}-Q{q}"
			if label not in seen:
				columns.append(label)
				seen.add(label)
			current = add_months(current, 1)

	else:  # monthly
		current = get_first_day(start)
		while getdate(current) <= end:
			columns.append(getdate(current).strftime("%Y-%m"))
			current = add_months(current, 1)

	return columns


def _build_and_run_query(config, group_by, period, from_date, to_date, company, all_dims=None):
	"""Build and execute the frappe.qb query for a metric with grouping.

	Returns flat rows with dim_0, dim_1, ..., period_label, total columns.
	"""
	if all_dims is None:
		all_dims = get_all_dimensions()

	doctype = config["doctype"]
	sum_field = config["sum_field"]
	date_field = config["date_field"]
	base_filters = config.get("base_filters", {})

	parent_table = frappe.qb.DocType(doctype)
	needs_child_join = False
	child_table = None
	actual_sum_field = sum_field

	# Check if any dimension requires a child table join
	for dim_name in group_by:
		dim_config = all_dims[dim_name]
		if "child_table" in dim_config:
			child_doctype = dim_config["child_table"].get(doctype)
			if child_doctype:
				needs_child_join = True
				child_table = frappe.qb.DocType(child_doctype)
				actual_sum_field = dim_config.get("child_sum_field", "base_amount")
				break

	# Build period expression
	period_expr = _build_period_expr(parent_table, date_field, period)

	# Build SELECT columns
	select_cols = []
	group_cols = []

	for i, dim_name in enumerate(group_by):
		dim_config = all_dims[dim_name]
		field_name = dim_config["field"]

		if "child_table" in dim_config and child_table is not None:
			col = child_table[field_name]
		else:
			col = parent_table[field_name]

		select_cols.append(col.as_(f"dim_{i}"))
		group_cols.append(col)

	select_cols.append(period_expr.as_("period_label"))
	group_cols.append(period_expr)

	# SUM field
	if needs_child_join and child_table is not None:
		total_expr = fn.Sum(child_table[actual_sum_field]).as_("total")
	else:
		total_expr = fn.Sum(parent_table[actual_sum_field]).as_("total")

	select_cols.append(total_expr)

	# Build query
	query = frappe.qb.from_(parent_table)

	if needs_child_join and child_table is not None:
		query = query.join(child_table).on(child_table.parent == parent_table.name)

	for col in select_cols:
		query = query.select(col)

	# Apply base filters
	for field, value in base_filters.items():
		query = query.where(parent_table[field] == value)

	# Company filter — supports single company or list of companies
	if isinstance(company, (list, tuple)) and len(company) > 1:
		query = query.where(parent_table.company.isin(company))
	elif isinstance(company, (list, tuple)):
		query = query.where(parent_table.company == company[0])
	else:
		query = query.where(parent_table.company == company)

	# Date range
	query = query.where(parent_table[date_field] >= from_date)
	query = query.where(parent_table[date_field] <= to_date)

	# GROUP BY
	for col in group_cols:
		query = query.groupby(col)

	# ORDER BY dimensions then period
	for col in group_cols:
		query = query.orderby(col)

	return query.run(as_dict=True)


def _build_period_expr(table, date_field, period):
	"""Build the period expression for GROUP BY based on period type."""
	if period == "yearly":
		return fn.DateFormat(table[date_field], "%Y")

	elif period == "quarterly":
		# CONCAT(DATE_FORMAT(date, '%Y'), '-Q', QUARTER(date))
		return fn.Concat(
			fn.DateFormat(table[date_field], "%Y"),
			frappe.qb.terms.ValueWrapper("-Q"),
			fn.Quarter(table[date_field]),
		)

	else:  # monthly
		return fn.DateFormat(table[date_field], "%Y-%m")


def _pivot_to_hierarchical(flat_rows, group_by, period_columns):
	"""Transform flat grouped query results into a hierarchical tree.

	Input: flat rows with dim_0, dim_1, ..., period_label, total
	Output: list of rows with description, level, is_group, values

	values = [grand_total, period_1_total, period_2_total, ...]

	For single dimension, no grouping hierarchy — just sorted rows.
	For multiple dimensions, dim_0 is the group header, dim_1+ are children.
	"""
	if not flat_rows:
		return []

	num_dims = len(group_by)

	if num_dims == 1:
		return _pivot_single_dimension(flat_rows, period_columns)
	else:
		return _pivot_multi_dimension(flat_rows, group_by, period_columns)


def _pivot_single_dimension(flat_rows, period_columns):
	"""Pivot single-dimension results into period columns."""
	# Accumulate totals per dimension value and period
	dim_data = OrderedDict()  # dim_value -> {period -> total}

	for row in flat_rows:
		dim_val = row.get("dim_0") or "Unknown"
		p = row.get("period_label", "")
		total = flt(row.get("total", 0), 2)

		if dim_val not in dim_data:
			dim_data[dim_val] = {}
		dim_data[dim_val][p] = dim_data[dim_val].get(p, 0) + total

	# Build output rows
	result = []
	for dim_val, period_totals in dim_data.items():
		grand_total = flt(sum(period_totals.values()), 2)
		values = [grand_total] + [flt(period_totals.get(p, 0), 2) for p in period_columns]
		result.append(
			{
				"description": str(dim_val),
				"level": 0,
				"is_group": False,
				"values": values,
			}
		)

	# Sort by grand total descending
	result.sort(key=lambda r: r["values"][0], reverse=True)

	return result


def _pivot_multi_dimension(flat_rows, group_by, period_columns):
	"""Pivot multi-dimension results into hierarchical rows with subtotals."""
	num_dims = len(group_by)

	# Build a nested dict: dim_0 -> dim_1 -> ... -> {period -> total}
	tree = OrderedDict()

	for row in flat_rows:
		dims = [row.get(f"dim_{i}") or "Unknown" for i in range(num_dims)]
		p = row.get("period_label", "")
		total = flt(row.get("total", 0), 2)

		# Navigate/create tree path
		node = tree
		for _i, dim_val in enumerate(dims[:-1]):
			if dim_val not in node:
				node[dim_val] = OrderedDict()
			node = node[dim_val]

		# Leaf level
		leaf_key = dims[-1]
		if leaf_key not in node:
			node[leaf_key] = {}
		node[leaf_key][p] = node[leaf_key].get(p, 0) + total

	# Flatten tree into hierarchical rows
	result = []
	_flatten_tree(tree, period_columns, result, level=0, num_dims=num_dims)

	return result


def _flatten_tree(node, period_columns, result, level, num_dims):
	"""Recursively flatten the tree into hierarchical rows.

	At leaf level (level == num_dims - 1), node values are {period -> total} dicts.
	At group levels, node values are OrderedDicts containing children.
	"""
	is_leaf_level = level == num_dims - 2  # children are leaves

	for key, children in node.items():
		if is_leaf_level:
			# children is an OrderedDict of leaf_key -> {period -> total}
			# First add children, accumulate subtotals
			group_period_totals = {}
			child_rows = []

			for child_key, period_totals in children.items():
				grand_total = flt(sum(period_totals.values()), 2)
				values = [grand_total] + [flt(period_totals.get(p, 0), 2) for p in period_columns]
				child_rows.append(
					{
						"description": str(child_key),
						"level": level + 1,
						"is_group": False,
						"values": values,
					}
				)
				# Accumulate into group subtotals
				for p, v in period_totals.items():
					group_period_totals[p] = group_period_totals.get(p, 0) + v

			# Sort children by total descending
			child_rows.sort(key=lambda r: r["values"][0], reverse=True)

			# Add group header row with subtotals
			group_total = flt(sum(group_period_totals.values()), 2)
			group_values = [group_total] + [flt(group_period_totals.get(p, 0), 2) for p in period_columns]
			result.append(
				{
					"description": str(key),
					"level": level,
					"is_group": True,
					"values": group_values,
				}
			)

			# Add children
			result.extend(child_rows)
		else:
			# Intermediate group level — recurse and collect subtotals
			sub_result = []
			_flatten_tree(children, period_columns, sub_result, level + 1, num_dims)

			# Compute subtotals from children
			group_values = [0.0] * (1 + len(period_columns))
			for child_row in sub_result:
				if child_row["level"] == level + 1:  # direct children only
					for i, v in enumerate(child_row["values"]):
						group_values[i] += v

			group_values = [flt(v, 2) for v in group_values]

			result.append(
				{
					"description": str(key),
					"level": level,
					"is_group": True,
					"values": group_values,
				}
			)
			result.extend(sub_result)
