# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
HRMS Tools Module
Human Resource Management tools for AI Chatbot

Provides employee analytics, attendance, leave balance, payroll, and turnover tools.
Requires the HRMS app to be installed — tools return a helpful error if it is not.
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt, get_first_day, get_last_day, nowdate

from ai_chatbot.core.config import get_fiscal_year_dates, is_hrms_installed
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_bar_chart, build_multi_series_chart, build_pie_chart
from ai_chatbot.data.currency import build_company_context, build_currency_response
from ai_chatbot.tools.registry import register_tool


def _primary(company):
	"""Get primary company name (first in list or string as-is)."""
	return company[0] if isinstance(company, list) else company


_HRMS_NOT_INSTALLED = {
	"error": (
		"HRMS app is not installed. Please install the HRMS app "
		"(bench get-app hrms && bench install-app hrms) to use HR tools."
	),
}


# ---------------------------------------------------------------------------
# 1. Employee Count
# ---------------------------------------------------------------------------
@register_tool(
	name="get_employee_count",
	category="hrms",
	description="Get employee headcount with optional breakdown by department, status, or designation",
	parameters={
		"department": {"type": "string", "description": "Filter by department name"},
		"status": {
			"type": "string",
			"description": "Employee status: Active, Inactive, Suspended, or Left (default: Active)",
		},
		"designation": {"type": "string", "description": "Filter by designation/job title"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Employee"],
)
def get_employee_count(department=None, status="Active", designation=None, company=None):
	"""Get employee headcount with department breakdown and pie chart."""
	if not is_hrms_installed():
		return _HRMS_NOT_INSTALLED

	company = get_company_filter(company)

	company_filter = {"company": ["in", company]} if isinstance(company, list) else {"company": company}
	filters = {**company_filter}
	if status:
		filters["status"] = status
	if department:
		filters["department"] = department
	if designation:
		filters["designation"] = designation

	total = frappe.db.count("Employee", filters)

	# Department breakdown
	emp = frappe.qb.DocType("Employee")
	dept_query = (
		frappe.qb.from_(emp)
		.select(emp.department, fn.Count("*").as_("count"))
		.groupby(emp.department)
		.orderby(fn.Count("*"), order=frappe.qb.desc)
	)
	if isinstance(company, list):
		dept_query = dept_query.where(emp.company.isin(company))
	else:
		dept_query = dept_query.where(emp.company == company)
	if status:
		dept_query = dept_query.where(emp.status == status)
	if designation:
		dept_query = dept_query.where(emp.designation == designation)

	dept_rows = dept_query.run(as_dict=True)

	departments = [{"department": r.department or "Unassigned", "count": r["count"]} for r in dept_rows]

	pie_data = [{"name": d["department"], "value": d["count"]} for d in departments]

	result = {
		"total_employees": total,
		"status_filter": status or "All",
		"departments": departments,
	}

	if pie_data:
		result["echart_option"] = build_pie_chart(
			title=f"Employees by Department ({status or 'All'})",
			data=pie_data,
		)

	return build_company_context(result, _primary(company))


# ---------------------------------------------------------------------------
# 2. Attendance Summary
# ---------------------------------------------------------------------------
@register_tool(
	name="get_attendance_summary",
	category="hrms",
	description=(
		"Get attendance summary showing present, absent, on leave, half day, and work from home counts"
	),
	parameters={
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current month start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current month end.",
		},
		"department": {"type": "string", "description": "Filter by department name"},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Attendance"],
)
def get_attendance_summary(from_date=None, to_date=None, department=None, company=None):
	"""Get attendance summary grouped by status with bar chart."""
	if not is_hrms_installed():
		return _HRMS_NOT_INSTALLED

	company = get_company_filter(company)

	# Default to current month
	if not from_date:
		from_date = str(get_first_day(nowdate()))
	if not to_date:
		to_date = str(get_last_day(nowdate()))

	att = frappe.qb.DocType("Attendance")

	query = (
		frappe.qb.from_(att)
		.select(att.status, fn.Count("*").as_("count"))
		.where(att.docstatus == 1)
		.where(att.attendance_date >= from_date)
		.where(att.attendance_date <= to_date)
		.groupby(att.status)
		.orderby(fn.Count("*"), order=frappe.qb.desc)
	)

	if isinstance(company, list):
		query = query.where(att.company.isin(company))
	else:
		query = query.where(att.company == company)

	if department:
		query = query.where(att.department == department)

	rows = query.run(as_dict=True)

	status_counts = {r.status: r["count"] for r in rows}
	total = sum(status_counts.values())

	present = status_counts.get("Present", 0) + status_counts.get("Work From Home", 0)
	absent = status_counts.get("Absent", 0)
	attendance_rate = round(present / (present + absent) * 100, 1) if (present + absent) > 0 else 0

	categories = list(status_counts.keys())
	values = list(status_counts.values())

	result = {
		"total_records": total,
		"status_breakdown": status_counts,
		"attendance_rate": attendance_rate,
		"period": {"from": from_date, "to": to_date},
	}

	if categories:
		result["echart_option"] = build_bar_chart(
			title="Attendance Summary",
			categories=categories,
			series_data=values,
			y_axis_name="Count",
			series_name="Attendance",
		)

	return build_company_context(result, _primary(company))


# ---------------------------------------------------------------------------
# 3. Leave Balance
# ---------------------------------------------------------------------------
@register_tool(
	name="get_leave_balance",
	category="hrms",
	description=(
		"Get leave balance for an employee or all employees, "
		"showing allocated, used, and remaining leaves by type"
	),
	parameters={
		"employee": {
			"type": "string",
			"description": "Employee ID or name to filter by (optional — omit for company-wide summary)",
		},
		"leave_type": {
			"type": "string",
			"description": "Leave type to filter by (e.g. 'Casual Leave', 'Sick Leave')",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Leave Allocation", "Leave Application"],
)
def get_leave_balance(employee=None, leave_type=None, company=None):
	"""Get leave balance: allocated minus consumed, per leave type."""
	if not is_hrms_installed():
		return _HRMS_NOT_INSTALLED

	company = get_company_filter(company)
	today = nowdate()

	# Resolve employee name to ID if needed
	if employee and not frappe.db.exists("Employee", employee):
		resolve_filters = {"employee_name": ["like", f"%{employee}%"]}
		if isinstance(company, list):
			resolve_filters["company"] = ["in", company]
		else:
			resolve_filters["company"] = company
		resolved = frappe.db.get_value("Employee", resolve_filters, "name")
		if resolved:
			employee = resolved

	# --- Allocated leaves (current, submitted, not expired) ---
	la = frappe.qb.DocType("Leave Allocation")
	alloc_query = (
		frappe.qb.from_(la)
		.select(
			la.employee,
			la.employee_name,
			la.leave_type,
			fn.Sum(la.total_leaves_allocated).as_("allocated"),
		)
		.where(la.docstatus == 1)
		.where(la.from_date <= today)
		.where(la.to_date >= today)
		.groupby(la.employee, la.leave_type)
	)

	if isinstance(company, list):
		alloc_query = alloc_query.where(la.company.isin(company))
	else:
		alloc_query = alloc_query.where(la.company == company)

	if employee:
		alloc_query = alloc_query.where(la.employee == employee)
	if leave_type:
		alloc_query = alloc_query.where(la.leave_type == leave_type)

	allocations = alloc_query.run(as_dict=True)

	# --- Consumed leaves (approved leave applications in current fiscal year) ---
	fy_from, fy_to = get_fiscal_year_dates(_primary(company))

	lapp = frappe.qb.DocType("Leave Application")
	consumed_query = (
		frappe.qb.from_(lapp)
		.select(
			lapp.employee,
			lapp.leave_type,
			fn.Sum(lapp.total_leave_days).as_("consumed"),
		)
		.where(lapp.status == "Approved")
		.where(lapp.docstatus == 1)
		.where(lapp.from_date >= fy_from)
		.where(lapp.to_date <= fy_to)
		.groupby(lapp.employee, lapp.leave_type)
	)

	if isinstance(company, list):
		consumed_query = consumed_query.where(lapp.company.isin(company))
	else:
		consumed_query = consumed_query.where(lapp.company == company)

	if employee:
		consumed_query = consumed_query.where(lapp.employee == employee)
	if leave_type:
		consumed_query = consumed_query.where(lapp.leave_type == leave_type)

	consumed_rows = consumed_query.run(as_dict=True)

	# Build consumed lookup
	consumed_map = {}
	for c in consumed_rows:
		key = (c.employee, c.leave_type)
		consumed_map[key] = flt(c.consumed)

	# Build result
	balances = []
	for a in allocations:
		key = (a.employee, a.leave_type)
		consumed = consumed_map.get(key, 0)
		balance = flt(a.allocated) - consumed
		balances.append(
			{
				"employee": a.employee,
				"employee_name": a.employee_name,
				"leave_type": a.leave_type,
				"allocated": flt(a.allocated),
				"consumed": consumed,
				"balance": balance,
			}
		)

	return build_company_context(
		{
			"leave_balances": balances,
			"total_entries": len(balances),
		},
		_primary(company),
	)


# ---------------------------------------------------------------------------
# 4. Payroll Summary
# ---------------------------------------------------------------------------
@register_tool(
	name="get_payroll_summary",
	category="hrms",
	description="Get payroll summary with total gross pay, deductions, and net pay for a period",
	parameters={
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current month start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current month end.",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Salary Slip"],
)
def get_payroll_summary(from_date=None, to_date=None, company=None):
	"""Get payroll totals with bar chart of gross/deductions/net."""
	if not is_hrms_installed():
		return _HRMS_NOT_INSTALLED

	company = get_company_filter(company)

	# Default to current month
	if not from_date:
		from_date = str(get_first_day(nowdate()))
	if not to_date:
		to_date = str(get_last_day(nowdate()))

	ss = frappe.qb.DocType("Salary Slip")

	query = (
		frappe.qb.from_(ss)
		.select(
			fn.Count("*").as_("slip_count"),
			fn.Sum(ss.base_gross_pay).as_("total_gross"),
			fn.Sum(ss.base_total_deduction).as_("total_deductions"),
			fn.Sum(ss.base_net_pay).as_("total_net"),
		)
		.where(ss.docstatus == 1)
		.where(ss.posting_date >= from_date)
		.where(ss.posting_date <= to_date)
	)
	if isinstance(company, list):
		query = query.where(ss.company.isin(company))
	else:
		query = query.where(ss.company == company)
	rows = query.run(as_dict=True)

	row = rows[0] if rows else {}
	slip_count = row.get("slip_count", 0) or 0
	total_gross = flt(row.get("total_gross", 0), 2)
	total_deductions = flt(row.get("total_deductions", 0), 2)
	total_net = flt(row.get("total_net", 0), 2)

	result = {
		"salary_slips": slip_count,
		"total_gross_pay": total_gross,
		"total_deductions": total_deductions,
		"total_net_pay": total_net,
		"average_gross_per_employee": flt(total_gross / slip_count, 2) if slip_count else 0,
		"average_net_per_employee": flt(total_net / slip_count, 2) if slip_count else 0,
		"period": {"from": from_date, "to": to_date},
	}

	if slip_count:
		result["echart_option"] = build_bar_chart(
			title="Payroll Summary",
			categories=["Gross Pay", "Deductions", "Net Pay"],
			series_data=[total_gross, total_deductions, total_net],
			y_axis_name="Amount",
			series_name="Payroll",
		)

	return build_currency_response(result, _primary(company))


# ---------------------------------------------------------------------------
# 5. Department-wise Salary
# ---------------------------------------------------------------------------
@register_tool(
	name="get_department_wise_salary",
	category="hrms",
	description="Get salary distribution by department showing gross and net pay per department",
	parameters={
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current month start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current month end.",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["Salary Slip"],
)
def get_department_wise_salary(from_date=None, to_date=None, company=None):
	"""Get salary breakdown by department with pie chart."""
	if not is_hrms_installed():
		return _HRMS_NOT_INSTALLED

	company = get_company_filter(company)

	# Default to current month
	if not from_date:
		from_date = str(get_first_day(nowdate()))
	if not to_date:
		to_date = str(get_last_day(nowdate()))

	ss = frappe.qb.DocType("Salary Slip")

	query = (
		frappe.qb.from_(ss)
		.select(
			ss.department,
			fn.Count("*").as_("slip_count"),
			fn.Sum(ss.base_gross_pay).as_("total_gross"),
			fn.Sum(ss.base_net_pay).as_("total_net"),
		)
		.where(ss.docstatus == 1)
		.where(ss.posting_date >= from_date)
		.where(ss.posting_date <= to_date)
		.groupby(ss.department)
		.orderby(fn.Sum(ss.base_net_pay), order=frappe.qb.desc)
	)
	if isinstance(company, list):
		query = query.where(ss.company.isin(company))
	else:
		query = query.where(ss.company == company)
	rows = query.run(as_dict=True)

	departments = [
		{
			"department": r.department or "Unassigned",
			"employee_count": r.slip_count,
			"total_gross_pay": flt(r.total_gross, 2),
			"total_net_pay": flt(r.total_net, 2),
		}
		for r in rows
	]

	pie_data = [{"name": d["department"], "value": d["total_net_pay"]} for d in departments]

	result = {
		"departments": departments,
		"period": {"from": from_date, "to": to_date},
	}

	if pie_data:
		result["echart_option"] = build_pie_chart(
			title="Salary Distribution by Department (Net Pay)",
			data=pie_data,
		)

	return build_currency_response(result, _primary(company))


# ---------------------------------------------------------------------------
# 6. Employee Turnover
# ---------------------------------------------------------------------------
@register_tool(
	name="get_employee_turnover",
	category="hrms",
	description="Get employee turnover showing new hires vs exits with turnover rate",
	parameters={
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
	doctypes=["Employee"],
)
def get_employee_turnover(from_date=None, to_date=None, company=None):
	"""Get employee turnover: new hires vs exits with multi-series bar chart."""
	if not is_hrms_installed():
		return _HRMS_NOT_INSTALLED

	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	emp = frappe.qb.DocType("Employee")

	# New hires — employees who joined in the period
	hire_query = (
		frappe.qb.from_(emp)
		.select(fn.Count("*").as_("count"))
		.where(emp.date_of_joining >= from_date)
		.where(emp.date_of_joining <= to_date)
	)
	if isinstance(company, list):
		hire_query = hire_query.where(emp.company.isin(company))
	else:
		hire_query = hire_query.where(emp.company == company)
	new_hires = hire_query.run(as_dict=True)
	joined = new_hires[0]["count"] if new_hires else 0

	# Exits — employees who left in the period
	exit_query = (
		frappe.qb.from_(emp)
		.select(fn.Count("*").as_("count"))
		.where(emp.status == "Left")
		.where(emp.relieving_date >= from_date)
		.where(emp.relieving_date <= to_date)
	)
	if isinstance(company, list):
		exit_query = exit_query.where(emp.company.isin(company))
	else:
		exit_query = exit_query.where(emp.company == company)
	exits = exit_query.run(as_dict=True)
	left = exits[0]["count"] if exits else 0

	# Total active employees (for rate calculation)
	active_filter = {"status": "Active"}
	if isinstance(company, list):
		active_filter["company"] = ["in", company]
	else:
		active_filter["company"] = company
	active = frappe.db.count("Employee", active_filter)

	turnover_rate = round(left / (active + left) * 100, 1) if (active + left) > 0 else 0

	return build_company_context(
		{
			"new_hires": joined,
			"exits": left,
			"active_employees": active,
			"turnover_rate": turnover_rate,
			"period": {"from": from_date, "to": to_date},
			"echart_option": build_multi_series_chart(
				title="Employee Turnover",
				categories=["Period"],
				series_list=[
					{"name": "New Hires", "data": [joined]},
					{"name": "Exits", "data": [left]},
				],
				y_axis_name="Employees",
				chart_type="bar",
			),
		},
		_primary(company),
	)
