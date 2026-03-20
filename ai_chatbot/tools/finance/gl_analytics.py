# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
GL Entry-Based Finance Tools

Provides authoritative accounting data by querying the General Ledger directly.
Includes GL summary, trial balance, and account statement tools.
"""

import frappe
from frappe.query_builder import functions as fn
from frappe.utils import flt

from ai_chatbot.core.config import get_fiscal_year_dates
from ai_chatbot.core.session_context import get_company_filter
from ai_chatbot.data.charts import build_bar_chart, build_horizontal_bar, build_line_chart
from ai_chatbot.data.currency import build_currency_response
from ai_chatbot.tools.registry import register_tool


def _primary(company):
	"""Get primary company name (first in list or string as-is)."""
	return company[0] if isinstance(company, list) else company


# Maps group_by parameter values to their query fields
GROUP_BY_FIELDS = {
	"root_type": {"source": "account", "field": "root_type", "label": "Root Type"},
	"account_type": {"source": "account", "field": "account_type", "label": "Account Type"},
	"party_type": {"source": "gl_entry", "field": "party_type", "label": "Party Type"},
	"voucher_type": {"source": "gl_entry", "field": "voucher_type", "label": "Voucher Type"},
	"account_name": {"source": "gl_entry", "field": "account", "label": "Account"},
}

# Root types and their normal balance direction
# Asset/Expense: normal balance is debit (positive = debit - credit)
# Liability/Equity/Income: normal balance is credit (positive = credit - debit)
DEBIT_ROOT_TYPES = {"Asset", "Expense"}
CREDIT_ROOT_TYPES = {"Liability", "Equity", "Income"}


@register_tool(
	name="get_gl_summary",
	category="finance",
	description=(
		"Get General Ledger summary with flexible grouping by root type, account type, "
		"party type, voucher type, or account name. Uses GL entries for authoritative "
		"accounting data. Useful for cash & bank position, receivables, payables, and "
		"income/expense breakdowns."
	),
	parameters={
		"group_by": {
			"type": "string",
			"description": (
				"How to group the GL data. Options: 'root_type' (Asset/Liability/Equity/Income/Expense), "
				"'account_type' (Bank/Cash/Receivable/Payable/etc.), 'party_type' (Customer/Supplier/Employee), "
				"'voucher_type' (Sales Invoice/Purchase Invoice/etc.), 'account_name' (individual accounts). "
				"Default: 'root_type'"
			),
		},
		"root_type": {
			"type": "string",
			"description": "Filter by root type: 'Asset', 'Liability', 'Equity', 'Income', 'Expense'",
		},
		"account_type": {
			"type": "string",
			"description": "Filter by account type: 'Bank', 'Cash', 'Receivable', 'Payable', etc.",
		},
		"party_type": {
			"type": "string",
			"description": "Filter by party type: 'Customer', 'Supplier', 'Employee'",
		},
		"party": {
			"type": "string",
			"description": "Filter by specific party name",
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
	doctypes=["GL Entry", "Account"],
)
def get_gl_summary(
	group_by="root_type",
	root_type=None,
	account_type=None,
	party_type=None,
	party=None,
	from_date=None,
	to_date=None,
	company=None,
):
	"""Get GL summary grouped by the specified dimension."""
	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	if group_by not in GROUP_BY_FIELDS:
		frappe.throw(f"Unsupported group_by: {group_by}. Options: {', '.join(GROUP_BY_FIELDS.keys())}")

	gle = frappe.qb.DocType("GL Entry")
	acc = frappe.qb.DocType("Account")

	group_config = GROUP_BY_FIELDS[group_by]
	if group_config["source"] == "account":
		group_col = acc[group_config["field"]]
	else:
		group_col = gle[group_config["field"]]

	query = (
		frappe.qb.from_(gle)
		.join(acc)
		.on(gle.account == acc.name)
		.select(
			group_col.as_("group_label"),
			fn.Sum(gle.debit).as_("total_debit"),
			fn.Sum(gle.credit).as_("total_credit"),
			(fn.Sum(gle.debit) - fn.Sum(gle.credit)).as_("balance"),
			fn.Count("*").as_("entry_count"),
		)
		.where(gle.is_cancelled == 0)
		.where(gle.posting_date >= from_date)
		.where(gle.posting_date <= to_date)
		.groupby(group_col)
		.orderby(fn.Sum(gle.debit) - fn.Sum(gle.credit), order=frappe.qb.desc)
	)

	if isinstance(company, list):
		query = query.where(gle.company.isin(company))
	else:
		query = query.where(gle.company == company)

	# Apply optional filters
	if root_type:
		query = query.where(acc.root_type == root_type)
	if account_type:
		query = query.where(acc.account_type == account_type)
	if party_type:
		query = query.where(gle.party_type == party_type)
	if party:
		query = query.where(gle.party == party)

	rows = query.run(as_dict=True)

	summary = []
	for row in rows:
		label = row.group_label or "Unknown"
		summary.append(
			{
				"label": label,
				"total_debit": flt(row.total_debit, 2),
				"total_credit": flt(row.total_credit, 2),
				"balance": flt(row.balance, 2),
				"entry_count": row.entry_count or 0,
			}
		)

	# Chart — use horizontal bar for account_name (long labels), bar chart otherwise
	categories = [s["label"] for s in summary[:15]]
	values = [abs(s["balance"]) for s in summary[:15]]

	if group_by == "account_name":
		chart = build_horizontal_bar(
			title=f"GL Summary by {group_config['label']}",
			categories=list(reversed(categories)),
			series_data=list(reversed(values)),
			x_axis_name="Balance",
			series_name="Balance",
		)
	else:
		chart = build_bar_chart(
			title=f"GL Summary by {group_config['label']}",
			categories=categories,
			series_data=values,
			y_axis_name="Balance",
			series_name="Balance",
		)

	totals = {
		"total_debit": flt(sum(s["total_debit"] for s in summary), 2),
		"total_credit": flt(sum(s["total_credit"] for s in summary), 2),
		"net_balance": flt(sum(s["balance"] for s in summary), 2),
	}

	result = {
		"group_by": group_by,
		"summary": summary,
		"totals": totals,
		"period": {"from": from_date, "to": to_date},
		"echart_option": chart,
	}
	return build_currency_response(result, _primary(company))


@register_tool(
	name="get_trial_balance",
	category="finance",
	description=(
		"Get a trial balance showing opening balance, period debit/credit, and closing "
		"balance for all accounts. The fundamental accounting report. Results are grouped "
		"by root type (Asset, Liability, Equity, Income, Expense) with subtotals."
	),
	parameters={
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end.",
		},
		"root_type": {
			"type": "string",
			"description": "Filter by root type: 'Asset', 'Liability', 'Equity', 'Income', 'Expense'",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["GL Entry", "Account"],
)
def get_trial_balance(from_date=None, to_date=None, root_type=None, company=None):
	"""Get trial balance from GL entries."""
	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	gle = frappe.qb.DocType("GL Entry")
	acc = frappe.qb.DocType("Account")

	# --- Opening balance: GL entries before from_date ---
	opening_query = (
		frappe.qb.from_(gle)
		.join(acc)
		.on(gle.account == acc.name)
		.select(
			gle.account,
			acc.root_type,
			fn.Sum(gle.debit).as_("opening_debit"),
			fn.Sum(gle.credit).as_("opening_credit"),
		)
		.where(gle.is_cancelled == 0)
		.where(gle.posting_date < from_date)
		.where(acc.is_group == 0)
		.groupby(gle.account, acc.root_type)
	)
	if isinstance(company, list):
		opening_query = opening_query.where(gle.company.isin(company))
	else:
		opening_query = opening_query.where(gle.company == company)
	if root_type:
		opening_query = opening_query.where(acc.root_type == root_type)

	opening_rows = opening_query.run(as_dict=True)
	opening_map = {
		r.account: {
			"root_type": r.root_type,
			"opening_debit": flt(r.opening_debit, 2),
			"opening_credit": flt(r.opening_credit, 2),
		}
		for r in opening_rows
	}

	# --- Period movement: GL entries within the date range ---
	period_query = (
		frappe.qb.from_(gle)
		.join(acc)
		.on(gle.account == acc.name)
		.select(
			gle.account,
			acc.root_type,
			fn.Sum(gle.debit).as_("debit"),
			fn.Sum(gle.credit).as_("credit"),
		)
		.where(gle.is_cancelled == 0)
		.where(gle.posting_date >= from_date)
		.where(gle.posting_date <= to_date)
		.where(acc.is_group == 0)
		.groupby(gle.account, acc.root_type)
	)
	if isinstance(company, list):
		period_query = period_query.where(gle.company.isin(company))
	else:
		period_query = period_query.where(gle.company == company)
	if root_type:
		period_query = period_query.where(acc.root_type == root_type)

	period_rows = period_query.run(as_dict=True)
	period_map = {
		r.account: {
			"root_type": r.root_type,
			"debit": flt(r.debit, 2),
			"credit": flt(r.credit, 2),
		}
		for r in period_rows
	}

	# Combine all accounts
	all_accounts = sorted(set(list(opening_map.keys()) + list(period_map.keys())))

	accounts = []
	root_type_subtotals = {}

	for account in all_accounts:
		opening = opening_map.get(account, {})
		period = period_map.get(account, {})
		rt = opening.get("root_type") or period.get("root_type") or "Unknown"

		op_debit = flt(opening.get("opening_debit", 0), 2)
		op_credit = flt(opening.get("opening_credit", 0), 2)
		p_debit = flt(period.get("debit", 0), 2)
		p_credit = flt(period.get("credit", 0), 2)
		cl_debit = flt(op_debit + p_debit, 2)
		cl_credit = flt(op_credit + p_credit, 2)

		# Skip accounts with no activity
		if not (op_debit or op_credit or p_debit or p_credit):
			continue

		accounts.append(
			{
				"account": account,
				"root_type": rt,
				"opening_debit": op_debit,
				"opening_credit": op_credit,
				"debit": p_debit,
				"credit": p_credit,
				"closing_debit": cl_debit,
				"closing_credit": cl_credit,
			}
		)

		# Accumulate root_type subtotals
		if rt not in root_type_subtotals:
			root_type_subtotals[rt] = {
				"opening_debit": 0,
				"opening_credit": 0,
				"debit": 0,
				"credit": 0,
				"closing_debit": 0,
				"closing_credit": 0,
			}
		sub = root_type_subtotals[rt]
		sub["opening_debit"] += op_debit
		sub["opening_credit"] += op_credit
		sub["debit"] += p_debit
		sub["credit"] += p_credit
		sub["closing_debit"] += cl_debit
		sub["closing_credit"] += cl_credit

	# Round subtotals
	for rt_key in root_type_subtotals:
		for field in root_type_subtotals[rt_key]:
			root_type_subtotals[rt_key][field] = flt(root_type_subtotals[rt_key][field], 2)

	# Grand totals
	grand_total = {
		"opening_debit": flt(sum(s["opening_debit"] for s in root_type_subtotals.values()), 2),
		"opening_credit": flt(sum(s["opening_credit"] for s in root_type_subtotals.values()), 2),
		"debit": flt(sum(s["debit"] for s in root_type_subtotals.values()), 2),
		"credit": flt(sum(s["credit"] for s in root_type_subtotals.values()), 2),
		"closing_debit": flt(sum(s["closing_debit"] for s in root_type_subtotals.values()), 2),
		"closing_credit": flt(sum(s["closing_credit"] for s in root_type_subtotals.values()), 2),
	}

	result = {
		"accounts": accounts,
		"root_type_subtotals": root_type_subtotals,
		"grand_total": grand_total,
		"account_count": len(accounts),
		"period": {"from": from_date, "to": to_date},
	}
	return build_currency_response(result, _primary(company))


@register_tool(
	name="get_account_statement",
	category="finance",
	description=(
		"Get a detailed account statement showing all GL transactions for a specific "
		"account. Shows date, voucher type, voucher number, party, debit, credit, and "
		"running balance. Similar to a bank statement view."
	),
	parameters={
		"account": {
			"type": "string",
			"description": "Account name (required). e.g. 'Cash - TC', 'Debtors - TC'",
		},
		"from_date": {
			"type": "string",
			"description": "Start date (YYYY-MM-DD). Optional — omit to use current fiscal year start.",
		},
		"to_date": {
			"type": "string",
			"description": "End date (YYYY-MM-DD). Optional — omit to use current fiscal year end.",
		},
		"party_type": {
			"type": "string",
			"description": "Filter by party type: 'Customer', 'Supplier'",
		},
		"party": {
			"type": "string",
			"description": "Filter by specific party name",
		},
		"company": {
			"type": "string",
			"description": "Company name. Optional — omit to use user's default company.",
		},
	},
	doctypes=["GL Entry", "Account"],
)
def get_account_statement(
	account=None,
	from_date=None,
	to_date=None,
	party_type=None,
	party=None,
	company=None,
):
	"""Get detailed account statement with running balance."""
	if not account:
		frappe.throw("Account name is required for account statement")

	company = get_company_filter(company)

	if not from_date or not to_date:
		fy_from, fy_to = get_fiscal_year_dates(_primary(company))
		from_date = from_date or fy_from
		to_date = to_date or fy_to

	gle = frappe.qb.DocType("GL Entry")

	# --- Opening balance: before from_date ---
	opening_query = (
		frappe.qb.from_(gle)
		.select(
			fn.Sum(gle.debit).as_("total_debit"),
			fn.Sum(gle.credit).as_("total_credit"),
		)
		.where(gle.account == account)
		.where(gle.is_cancelled == 0)
		.where(gle.posting_date < from_date)
	)
	if isinstance(company, list):
		opening_query = opening_query.where(gle.company.isin(company))
	else:
		opening_query = opening_query.where(gle.company == company)
	if party_type:
		opening_query = opening_query.where(gle.party_type == party_type)
	if party:
		opening_query = opening_query.where(gle.party == party)

	opening_result = opening_query.run(as_dict=True)
	opening_debit = flt(opening_result[0].total_debit) if opening_result else 0
	opening_credit = flt(opening_result[0].total_credit) if opening_result else 0
	opening_balance = flt(opening_debit - opening_credit, 2)

	# --- Period transactions ---
	txn_query = (
		frappe.qb.from_(gle)
		.select(
			gle.posting_date,
			gle.voucher_type,
			gle.voucher_no,
			gle.party_type,
			gle.party,
			gle.debit,
			gle.credit,
			gle.remarks,
		)
		.where(gle.account == account)
		.where(gle.is_cancelled == 0)
		.where(gle.posting_date >= from_date)
		.where(gle.posting_date <= to_date)
		.orderby(gle.posting_date)
		.orderby(gle.creation)
	)
	if isinstance(company, list):
		txn_query = txn_query.where(gle.company.isin(company))
	else:
		txn_query = txn_query.where(gle.company == company)
	if party_type:
		txn_query = txn_query.where(gle.party_type == party_type)
	if party:
		txn_query = txn_query.where(gle.party == party)

	txn_rows = txn_query.run(as_dict=True)

	# Build transactions with running balance
	running_balance = opening_balance
	transactions = []
	balance_series = []  # for the line chart

	for txn in txn_rows:
		debit = flt(txn.debit, 2)
		credit = flt(txn.credit, 2)
		running_balance = flt(running_balance + debit - credit, 2)

		transactions.append(
			{
				"posting_date": str(txn.posting_date),
				"voucher_type": txn.voucher_type or "",
				"voucher_no": txn.voucher_no or "",
				"party": txn.party or "",
				"debit": debit,
				"credit": credit,
				"balance": running_balance,
			}
		)
		balance_series.append(running_balance)

	closing_balance = running_balance
	total_debit = flt(sum(t["debit"] for t in transactions), 2)
	total_credit = flt(sum(t["credit"] for t in transactions), 2)

	# Line chart of running balance
	chart = None
	if transactions:
		dates = [t["posting_date"] for t in transactions]
		chart = build_line_chart(
			title=f"Balance Trend — {account}",
			categories=dates,
			series_data=balance_series,
			y_axis_name="Balance",
			series_name="Running Balance",
		)

	result = {
		"account": account,
		"opening_balance": opening_balance,
		"transactions": transactions,
		"total_debit": total_debit,
		"total_credit": total_credit,
		"closing_balance": closing_balance,
		"transaction_count": len(transactions),
		"period": {"from": from_date, "to": to_date},
	}
	if chart:
		result["echart_option"] = chart

	return build_currency_response(result, _primary(company))
