"""
Aggregation Queries for AI Chatbot Tools

Provides SUM, COUNT, GROUP BY, and time-series queries using frappe.qb
(Frappe Query Builder) for safe, parameterized queries. No raw SQL.
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import add_months, get_first_day, get_last_day, getdate, nowdate

from ai_chatbot.core.config import get_default_company
from ai_chatbot.core.constants import BASE_AMOUNT_FIELDS


def get_sum(doctype, field, filters=None, company=None):
	"""Get SUM of a field with company filter.

	Args:
		doctype: Frappe doctype name.
		field: Field name to sum.
		filters: Dict of additional filters.
		company: Company name.

	Returns:
		float — the sum value.
	"""
	company = get_default_company(company)
	table = frappe.qb.DocType(doctype)
	query = frappe.qb.from_(table).select(fn.Sum(table[field]).as_("total"))

	if _has_field(doctype, "company"):
		query = query.where(table.company == company)

	query = _apply_filters(query, table, doctype, filters)
	result = query.run(as_dict=True)
	return result[0].total or 0 if result else 0


def get_grouped_sum(
	doctype, sum_field, group_field, filters=None, company=None, order_by_sum=True, limit=None
):
	"""Get SUM grouped by a field.

	Args:
		doctype: Frappe doctype name.
		sum_field: Field to SUM.
		group_field: Field to GROUP BY.
		filters: Dict of additional filters.
		company: Company name.
		order_by_sum: If True, order by sum descending.
		limit: Max number of groups.

	Returns:
		List of dicts with group_field and total.
	"""
	company = get_default_company(company)
	table = frappe.qb.DocType(doctype)
	total = fn.Sum(table[sum_field]).as_("total")
	count = fn.Count("*").as_("count")

	query = frappe.qb.from_(table).select(table[group_field], total, count).groupby(table[group_field])

	if _has_field(doctype, "company"):
		query = query.where(table.company == company)

	query = _apply_filters(query, table, doctype, filters)

	if order_by_sum:
		query = query.orderby(total, order=frappe.qb.desc)

	if limit:
		query = query.limit(limit)

	return query.run(as_dict=True)


def get_time_series(doctype, value_field, date_field, filters=None, company=None, months=12):
	"""Get monthly time-series aggregation.

	Args:
		doctype: Frappe doctype name.
		value_field: Field to SUM per month.
		date_field: Date field for bucketing.
		filters: Dict of additional filters.
		company: Company name.
		months: Number of months to look back from today.

	Returns:
		List of dicts with month (YYYY-MM), total, and count.
	"""
	company = get_default_company(company)
	table = frappe.qb.DocType(doctype)

	start_date = get_first_day(add_months(nowdate(), -months + 1))
	end_date = get_last_day(nowdate())

	# Use Frappe's date formatting for month grouping
	month_expr = fn.DateFormat(table[date_field], "%Y-%m")

	query = (
		frappe.qb.from_(table)
		.select(
			month_expr.as_("month"),
			fn.Sum(table[value_field]).as_("total"),
			fn.Count("*").as_("count"),
		)
		.where(table[date_field] >= start_date)
		.where(table[date_field] <= end_date)
		.groupby(month_expr)
		.orderby(month_expr)
	)

	if _has_field(doctype, "company"):
		query = query.where(table.company == company)

	query = _apply_filters(query, table, doctype, filters)

	return query.run(as_dict=True)


def get_base_amount_field(doctype):
	"""Get the base currency amount field for a doctype.

	Args:
		doctype: Frappe doctype name.

	Returns:
		Field name string (e.g. "base_grand_total").
	"""
	return BASE_AMOUNT_FIELDS.get(doctype, "base_grand_total")


def _has_field(doctype, fieldname):
	"""Check if doctype has a field (cached)."""
	meta = frappe.get_meta(doctype)
	return meta.has_field(fieldname)


def _apply_filters(query, table, doctype, filters):
	"""Apply a dict of filters to a frappe.qb query.

	Supports simple equality and list operators:
		{"status": "Open"}              → WHERE status = 'Open'
		{"posting_date": [">=", date]}  → WHERE posting_date >= date
		{"docstatus": 1}                → WHERE docstatus = 1
	"""
	if not filters:
		return query

	for field, value in filters.items():
		if not _has_field(doctype, field):
			continue

		col = table[field]

		if isinstance(value, (list, tuple)) and len(value) == 2:
			operator, operand = value
			op_str = operator.lower() if isinstance(operator, str) else operator

			# Handle "between" specially: operand is [start, end]
			if op_str == "between" and isinstance(operand, (list, tuple)) and len(operand) == 2:
				query = query.where(col.between(operand[0], operand[1]))
			else:
				op_map = {
					">=": col.gte,
					"<=": col.lte,
					">": col.gt,
					"<": col.lt,
					"=": col.eq,
					"!=": col.ne,
					"like": col.like,
					"in": col.isin,
					"not in": col.notin,
				}
				op_func = op_map.get(op_str)
				if op_func:
					query = query.where(op_func(operand))
		else:
			query = query.where(col == value)

	return query
