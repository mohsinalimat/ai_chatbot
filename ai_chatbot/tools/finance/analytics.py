# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Multi-Dimensional Analytics Tool

Provides a generic multi-dimensional summary tool that groups transactional data
by any combination of dimensions (territory, customer_group, item_group, etc.)
across time periods (monthly, quarterly, yearly).
"""

from frappe.utils import flt

from ai_chatbot.core.config import get_default_company, get_fiscal_year_dates
from ai_chatbot.data.charts import build_stacked_bar_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.data.grouping import (
	DIMENSION_FIELDS,
	MAX_DIMENSIONS,
	METRIC_CONFIG,
	get_all_dimensions,
	get_grouped_metric,
)
from ai_chatbot.tools.registry import register_tool


@register_tool(
	name="get_multidimensional_summary",
	category="finance",
	description=(
		"Generate a multi-dimensional summary grouped by any combination of supported "
		"dimensions and time periods. "
		"Built-in dimensions: company, territory, customer_group, customer, item_group, "
		"cost_center, department. "
		"Additionally, any Accounting Dimensions created in ERPNext are automatically "
		"available. Use snake_case fieldnames with underscores (e.g. 'business_vertical' "
		"not 'business vertical', 'business_segment' not 'business segment'). "
		"The tool auto-resolves spaces to underscores, so both formats work. "
		"Time periods: monthly, quarterly, yearly. "
		"Metrics: revenue, expenses, profit, orders. "
		"If unsure whether a dimension exists, try it — the tool will return a clear error "
		"if the dimension is not available."
	),
	parameters={
		"metric": {
			"type": "string",
			"description": (
				"What to measure: 'revenue' (Sales Invoice totals), 'expenses' (Purchase Invoice totals), "
				"'profit' (revenue minus expenses), 'orders' (Sales Order totals). Default: 'revenue'"
			),
		},
		"group_by": {
			"type": "array",
			"items": {"type": "string"},
			"description": (
				"Dimensions to group by, in order of hierarchy. Max 3 dimensions. "
				"Built-in: 'company', 'territory', 'customer_group', 'customer', 'item_group', "
				"'cost_center', 'department'. "
				"Also supports any Accounting Dimension fieldnames created in ERPNext "
				"(e.g. 'business_vertical', 'business_segment', 'project'). "
				"Use snake_case with underscores. Spaces are auto-resolved to underscores. "
				"Example: ['territory', 'customer_group'] or ['business_vertical', 'business_segment']"
			),
		},
		"period": {
			"type": "string",
			"description": "Time grouping: 'monthly', 'quarterly', 'yearly'. Default: 'quarterly'",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end.",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Sales Invoice", "Purchase Invoice", "Sales Order"],
)
def get_multidimensional_summary(
	metric="revenue",
	group_by=None,
	period="quarterly",
	from_date=None,
	to_date=None,
	company=None,
):
	"""Generate a multi-dimensional summary with hierarchical table and stacked bar chart."""
	company = get_default_company(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(company)
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	# Default group_by
	if not group_by:
		group_by = ["territory"]

	# Ensure group_by is a list
	if isinstance(group_by, str):
		group_by = [group_by]

	# Validate period
	valid_periods = ["monthly", "quarterly", "yearly"]
	if period not in valid_periods:
		period = "quarterly"

	# Get the hierarchical table data from the grouping engine
	table_data = get_grouped_metric(
		metric=metric,
		group_by=group_by,
		period=period,
		from_date=from_date,
		to_date=to_date,
		company=company,
	)

	# Build stacked bar chart from the top-level rows
	chart = _build_chart(table_data, metric, group_by, period)

	result = {
		"metric": metric,
		"group_by": group_by,
		"period": period,
		"hierarchical_table": table_data,
		"period_info": {"from": from_date, "to": to_date},
	}
	if chart:
		result["echart_option"] = chart

	return build_currency_response(result, company)


def _build_chart(table_data, metric, group_by, period):
	"""Build a stacked bar chart from the hierarchical table data.

	X-axis: period columns
	Each stack: a top-level dimension value (level 0 rows)
	"""
	headers = table_data.get("headers", [])
	rows = table_data.get("rows", [])

	if not headers or not rows:
		return None

	# Period columns are headers[2:] (skip description and Total columns)
	period_columns = headers[2:] if len(headers) > 2 else []
	if not period_columns:
		return None

	# Get top-level rows for the chart series
	top_rows = [r for r in rows if r.get("level", 0) == 0]
	if not top_rows:
		top_rows = rows

	# Limit to top 10 for readability
	top_rows = top_rows[:10]

	series_list = []
	for row in top_rows:
		values = row.get("values", [])
		# values[0] is total, values[1:] are period values
		period_values = values[1:] if len(values) > 1 else []
		# Pad to match period_columns length
		while len(period_values) < len(period_columns):
			period_values.append(0)

		series_list.append(
			{
				"name": row.get("description", "Unknown"),
				"data": [flt(v, 2) for v in period_values[: len(period_columns)]],
			}
		)

	all_dims = get_all_dimensions()
	dim_label = all_dims.get(group_by[0], {}).get("label", group_by[0])
	title = f"{metric.title()} by {dim_label} ({period.title()})"

	return build_stacked_bar_chart(
		title=title,
		categories=period_columns,
		series_list=series_list,
		y_axis_name="Amount",
	)
