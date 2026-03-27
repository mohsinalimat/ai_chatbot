# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
System Prompt Builder for AI Chatbot

Dynamically builds the system message including user context, company info,
fiscal year dates, enabled tool categories, and behavioral guidelines.

The prompt is structured using XML-like tags (<role>, <session>, <rules>, etc.)
that LLMs parse more efficiently than wall-of-text instructions.

Two entry points:
- build_system_prompt() — returns a single string (used by all providers)
- build_system_prompt_blocks() — returns a list of tagged content blocks
  with cacheability hints (used by Claude for prompt caching)
"""

import frappe
from frappe.utils import nowdate

from ai_chatbot.core.config import (
	get_company_currency,
	get_default_company,
	get_fiscal_year_dates,
)
from ai_chatbot.core.constants import TOOL_CATEGORIES


def build_system_prompt_blocks(conversation_id: str | None = None, company: str | None = None) -> list[dict]:
	"""Build the system prompt as a list of tagged content blocks.

	Each block is a dict with:
	  - tag: str (e.g., "role", "session", "rules", "tools")
	  - content: str (the block content)
	  - cacheable: bool (True for static blocks, False for per-request volatile ones)

	Used by Claude provider for prompt caching (cache_control markers).
	OpenAI/Gemini providers use build_system_prompt() which joins these blocks.

	Args:
		conversation_id: Optional conversation ID to read session context.
		company: Optional company override (used by automation executor).

	Returns:
		list[dict]: Ordered list of prompt blocks.
	"""
	blocks = []
	settings = frappe.get_single("Chatbot Settings")

	# ── Role block (cacheable — persona rarely changes) ──
	persona = (getattr(settings, "ai_persona", "") or "").strip()
	if not persona:
		persona = "an intelligent ERPNext business assistant"

	blocks.append(
		{
			"tag": "role",
			"content": (
				f"You are {persona}. "
				"You help users analyze business data, manage records, and get insights "
				"from their ERPNext system."
			),
			"cacheable": True,
		}
	)

	# ── Session block (NOT cacheable — changes per user/conversation) ──
	session_parts = []
	try:
		user = frappe.session.user
		full_name = frappe.db.get_value("User", user, "full_name") or user
		company = company or get_default_company()
		currency = get_company_currency(company)
		fy_from, fy_to = get_fiscal_year_dates(company)

		session_parts.append(
			f"## Current Context\n"
			f"- **User**: {full_name}\n"
			f"- **Company**: {company}\n"
			f"- **Currency**: {currency}\n"
			f"- **Fiscal Year**: {fy_from} to {fy_to}\n"
			f"- **Today**: {nowdate()}"
		)
	except Exception:
		session_parts.append(f"## Current Context\n- **Today**: {nowdate()}")

	# Multi-Company / Session Context
	if company:
		try:
			from ai_chatbot.core.consolidation import get_child_companies, is_parent_company

			if is_parent_company(company):
				children = get_child_companies(company)
				if children:
					child_list = ", ".join(children[:10])
					suffix = f" (and {len(children) - 10} more)" if len(children) > 10 else ""
					parent_currency = get_company_currency(company)

					# Read current session state
					session_state = ""
					if conversation_id:
						from ai_chatbot.core.session_context import get_session_context

						ctx = get_session_context(conversation_id)
						inc_subs = ctx.get("include_subsidiaries", False)
						tgt_curr = ctx.get("target_currency")
						session_state = (
							f"\n- **Current session state:**\n"
							f"  - `include_subsidiaries`: **{'ON' if inc_subs else 'OFF'}**\n"
							f"  - `target_currency`: **{tgt_curr or 'not set (using company default)'}**"
						)

					session_parts.append(
						f"\n## Multi-Company Context\n"
						f'- "{company}" has subsidiaries: {child_list}{suffix}\n'
						f"- Currency: {parent_currency}"
						f"{session_state}\n"
						f"- When `include_subsidiaries` is ON, all tools automatically aggregate "
						f"data across parent + child companies. Use `company_label` from tool "
						f"responses when reporting.\n"
						f"- **Auto-detect intent**: If the user's query contains words like "
						f"'consolidated', 'group-wide', 'all companies', 'overall', 'entire group', "
						f"or 'across companies', automatically call `set_include_subsidiaries(true)` "
						f"before running the data tool. Do NOT auto-include for generic queries like "
						f"'total sales' or 'show revenue' — those should use the current setting.\n"
						f"- If the user explicitly asks to include or exclude subsidiaries, use "
						f"`set_include_subsidiaries(include)` accordingly.\n"
						f"- To group/compare data **by company**, use `get_multidimensional_summary` "
						f"with `group_by=['company']` — 'company' is a supported dimension.\n"
						f"- Use `set_target_currency(currency)` when the user specifies a display "
						f"currency (e.g. 'show in USD', @Currency). Pass empty string to reset.\n"
						f"- Session settings persist for the entire conversation."
					)
		except Exception:
			pass

	blocks.append(
		{
			"tag": "session",
			"content": "\n".join(session_parts),
			"cacheable": False,
		}
	)

	# ── Rules block (cacheable — guidelines are static) ──
	rules_parts = []

	# Date Range Guidelines
	rules_parts.append(
		"## Date Range Guidelines\n"
		"- Do NOT ask the user for dates when they haven't specified any — just call the tool "
		"without `from_date`/`to_date` and the server will default to the current fiscal year.\n"
		"- Always include the date range used in your response so the user knows the scope.\n"
		"- For comparisons (e.g. 'this month vs last month'), calculate the appropriate ranges."
	)

	# Company Context Guidelines
	rules_parts.append(
		"## Company Context Guidelines\n"
		"- Do NOT ask the user for a company name — omit the `company` parameter and the "
		"server will use their default company automatically.\n"
		"- When the user explicitly names a company (e.g. 'show sales of Tara Technologies'), "
		"always pass it as the `company` parameter. The server will fuzzy-match partial names "
		"to the correct company in the database.\n"
		"- Always mention the company name in your response. Tool responses include a "
		"`company_label` field — use it as-is (it includes subsidiary notation when applicable)."
	)

	# Currency Guidelines
	rules_parts.append(
		"## Currency Guidelines\n"
		"- Always include the currency symbol or code when presenting monetary values.\n"
		"- Use the company's default currency for aggregated amounts.\n"
		"- When presenting data from tools, the `currency` field indicates the currency used.\n"
		"- When data is grouped by company and no target currency is set via @Currency, "
		"show each company's data in its own default currency.\n"
		"- When a target currency is set (via session), all amounts are shown in that currency."
	)

	# Financial Analysis Behaviour
	if getattr(settings, "enable_finance_tools", False):
		rules_parts.append(
			"## Financial Analysis Behaviour\n"
			"When answering financial questions, act as a seasoned Financial Analyst / CFO:\n"
			"- Provide context for numbers (YoY change, % of revenue, industry benchmarks)\n"
			"- Highlight key risks and opportunities in the data\n"
			"- Suggest actionable next steps when presenting financial metrics\n"
			"- Use professional financial terminology (EBITDA, DSO, working capital cycle)\n"
			"- Compare current metrics against previous periods when data is available\n"
			"- Flag anomalies or concerning trends proactively"
		)

	# Dimension Filtering (dynamically discovered)
	dim_names = ["cost_center", "department", "project"]
	try:
		from ai_chatbot.core.dimensions import get_available_dimensions

		extra_dims = get_available_dimensions()
		for d in extra_dims:
			fn = d.get("fieldname")
			if fn and fn not in dim_names:
				dim_names.append(fn)
	except Exception:
		pass

	dim_list = ", ".join(f"`{d}`" for d in dim_names)
	rules_parts.append(
		"## Dimension Filtering\n"
		f"- Finance tools support optional filtering by: {dim_list}.\n"
		"- Only pass these filters when the user explicitly mentions a dimension value.\n"
		"- Do NOT ask the user for dimension filters — they are optional."
	)

	# Write Operations
	write_enabled = getattr(settings, "enable_write_operations", False)
	if write_enabled:
		rules_parts.append(
			"## Write Operations\n"
			"You can propose creating, updating, submitting, and cancelling ERPNext documents.\n\n"
			"**IMPORTANT rules:**\n"
			"1. **ALWAYS use `propose_*` tools** for ALL write operations — use `propose_create_document`, "
			"`propose_update_document`, `propose_submit_document`, or `propose_cancel_document`. "
			"**NEVER** use the old typed tools (`create_lead`, `create_opportunity`, `create_todo`, "
			"`update_lead_status`, `update_opportunity_status`, `update_todo`) — those exist only "
			"as legacy fallbacks. Always prefer the `propose_*` tools so the user sees a confirmation card.\n"
			"2. These tools validate the data and return a **confirmation card** for the user to review. "
			"The document is NOT created/modified until the user clicks 'Confirm' on the card.\n"
			"3. If the tool returns validation errors, inform the user and help fix them.\n"
			"4. If the tool returns warnings, mention them but the user can still confirm.\n"
			"5. For create operations, pass all fields the user mentioned. Do NOT worry about auto-populated "
			"fields like naming_series, currency, exchange_rate, price_list — ERPNext fills those automatically.\n"
			"6. After the user confirms or cancels, they will see the result in the confirmation card.\n"
			"7. When proposing child table data (e.g. items in a Sales Order), structure them as "
			"arrays of objects in the `values` parameter. For items, use `item_code` with the item's "
			"name or code — the system will auto-resolve item names to item codes.\n"
			"8. When the user asks to create **multiple independent documents** (e.g. 'create items "
			"Laptop and Smartphone'), call `propose_create_document` **once per document**. The frontend "
			"will render all confirmation cards together so the user can review them at once."
		)

	# Response Language (per-conversation or global fallback)
	lang = None
	if conversation_id:
		from ai_chatbot.core.session_context import get_session_context

		lang_ctx = get_session_context(conversation_id)
		lang = (lang_ctx.get("response_language") or "").strip() or None

	if not lang:
		lang = (getattr(settings, "response_language", "") or "").strip() or None

	if lang and lang != "English":
		rules_parts.append(f"## Language\nAlways respond in {lang}.")

	# Response Format
	rules_parts.append(
		"## Response Format\n"
		"- Use **markdown** for formatting (tables, bold, lists, code blocks).\n"
		"- Use tables for comparative or tabular data.\n"
		"- Keep responses concise and focused on the user's question.\n"
		"- When presenting numbers, use appropriate formatting (commas for thousands, "
		"2 decimal places for currency).\n"
		"- **NEVER** include image tags (`![](...)` or `<img ...>`) in your response. "
		"Charts and visualizations are rendered automatically by the frontend from tool data. "
		"Do not attempt to embed, link, or reference any chart images."
	)

	# Custom System Prompt
	custom_prompt = (getattr(settings, "custom_system_prompt", "") or "").strip()
	if custom_prompt:
		rules_parts.append(f"## Custom Instructions\n{custom_prompt}")

	# Custom Instructions
	custom_instructions = (getattr(settings, "custom_instructions", "") or "").strip()
	if custom_instructions:
		rules_parts.append(f"## Additional Instructions\n{custom_instructions}")

	blocks.append(
		{
			"tag": "rules",
			"content": "\n\n".join(rules_parts),
			"cacheable": True,
		}
	)

	# ── Tools block (cacheable — tool categories change only on settings save) ──
	from ai_chatbot.tools.registry import _EXTRA_CATEGORIES

	all_categories = {**TOOL_CATEGORIES, **_EXTRA_CATEGORIES}
	enabled = []
	for category, field in all_categories.items():
		if field is None or getattr(settings, field, False):
			enabled.append(category)

	if enabled:
		blocks.append(
			{
				"tag": "tools",
				"content": (
					"## Available Tool Categories\n"
					f"You have access to tools in these categories: {', '.join(enabled)}.\n"
					"Use the appropriate tools to fetch real data from ERPNext when answering "
					"business questions. Do not make up data — always use tools."
				),
				"cacheable": True,
			}
		)

	# ── IDP block (cacheable, conditional) ──
	if getattr(settings, "enable_idp_tools", False):
		idp_output_language = (getattr(settings, "idp_output_language", "") or "").strip()

		if idp_output_language:
			output_lang_instruction = (
				f"   **a. Output Language: {idp_output_language} (configured in settings)**\n"
				f"   Use {idp_output_language} as the output language. Only ask if the user "
				"explicitly requests a different language.\n\n"
			)
		else:
			output_lang_instruction = (
				"   **a. Output Language (default: English):**\n"
				"   In which language should the extracted data be output? The document can be "
				"in any language — extracted values will be translated to the chosen language. "
				"Only skip asking if the user explicitly states a language (e.g., 'in English', "
				"'Language: French', 'extract in Spanish'). Providing item details like "
				"'stock items' or 'Item Group' does NOT count as specifying the language.\n\n"
			)

		blocks.append(
			{
				"tag": "idp",
				"content": (
					"## Document Processing (IDP)\n"
					"You can extract structured data from uploaded documents (invoices, POs, quotations, "
					"receipts) and create ERPNext records from them.\n"
					"**Workflow:**\n"
					"1. **Collect preferences (MANDATORY before extraction):**\n"
					"   When the user uploads a document and asks to extract or process it, you MUST "
					"collect ALL of the following preferences before calling `extract_document_data`. "
					"Scan the user's message — if a preference is already stated, memorize it. "
					"For ALL preferences NOT explicitly stated, you MUST ask the user.\n\n"
					+ output_lang_instruction
					+ "   **b. Is Stock Item? (yes/no):**\n"
					"   Are these physical inventory items? Only skip if user says e.g. 'stock items', "
					"'non-stock', 'these are services'.\n\n"
					"   **c. Is Fixed Asset? (yes/no):**\n"
					"   Are these fixed assets? Only skip if user says e.g. 'fixed assets', "
					"'not fixed assets'. Also skip (assume no) if user already said 'stock items' "
					"— stock items and fixed assets are mutually exclusive in ERPNext.\n\n"
					"   **d. Item Group:**\n"
					"   Which ERPNext Item Group? Only skip if user says e.g. 'Item Group: Consumable', "
					"'Products group'.\n\n"
					"   Ask all missing preferences in a single message. If user says 'skip' or "
					f"'use defaults', use {idp_output_language or 'English'} for language and ERPNext defaults for item settings.\n"
					"2. Call `extract_document_data` with the file_url, target_doctype, and "
					f"`output_language` (from step 1, default '{idp_output_language or 'English'}').\n"
					"3. Present the extracted data to the user in a clear table format for review.\n"
					"4. Highlight any validation warnings or unresolved fields.\n"
					"5. **Only after the user confirms** the data is correct, proceed to step 6.\n"
					"6. Call `create_from_extracted_data`. If it returns a `missing_masters` error, "
					"follow step 7.\n"
					"7. **When masters are missing:** Present the missing records to the user and ask "
					"if they want to create them. Use the item defaults memorized from step 1. If "
					"the user did not provide them in step 1, ask now. Then call "
					"`create_from_extracted_data` again with `create_missing_masters='true'` "
					"and `item_defaults_json` containing the user's answers.\n"
					"8. To compare an uploaded document against an existing record, use "
					"`compare_document_with_record`.\n\n"
					"**CRITICAL:** Do NOT call `create_from_extracted_data` more than ONCE with the "
					"same parameters if it fails. If it returns a missing_masters error, you MUST "
					"stop and ask the user. Only retry AFTER the user answers "
					"and you have `create_missing_masters='true'` + `item_defaults_json`.\n\n"
					"Supported document formats: PDF, images (JPEG, PNG), Excel (XLSX), CSV, Word (DOCX).\n"
					"Documents can be in any language — the extraction handles multi-language content.\n\n"
					"**Default Assumptions (inform the user when applied):**\n"
					"- If the user does not specify a company, the user's default company is used.\n"
					"- If item_code and item_name are missing, the first 100 characters of the item "
					"description are used as both item_code and item_name.\n"
					"- If item quantity is missing, qty defaults to 1.\n"
					"- If posting/bill date is missing, today's date is used.\n"
					"When presenting extracted data, mention any defaults that were applied.\n"
				),
				"cacheable": True,
			}
		)

	# ── Predictive block (cacheable, conditional) ──
	if getattr(settings, "enable_predictive_tools", False):
		blocks.append(
			{
				"tag": "predictive",
				"content": (
					"## Predictive Analytics\n"
					"You have access to forecasting and anomaly detection tools. Guidelines:\n"
					"- **Forecasting tools** (`forecast_demand`, `forecast_revenue`, `forecast_cash_flow`, "
					"`forecast_by_territory`) use statistical methods (moving averages, exponential "
					"smoothing, trend analysis) on historical data to project future values.\n"
					"- **Forecasts require at least 3 months of historical data.** If data is insufficient, "
					"inform the user how much history is available and suggest waiting.\n"
					"- Always present the forecasting method used, confidence intervals, and any "
					"detected trends or seasonality in your response.\n"
					"- **Confidence intervals:** 80% and 95% bands are provided. Explain to the user "
					"that wider bands mean more uncertainty.\n"
					"- **Anomaly detection** (`detect_anomalies`) identifies unusual transactions using "
					"statistical methods (z-score, IQR). Present flagged anomalies with context "
					"(amount, date, party) and explain why they were flagged.\n"
					"- Forecasts are statistical projections, not guarantees. Always include a disclaimer "
					"that actual results may differ.\n"
					"- When the user asks about future revenue, demand, or cash flow, proactively use "
					"the forecast tools rather than extrapolating manually."
				),
				"cacheable": True,
			}
		)

	return blocks


def build_system_prompt(conversation_id: str | None = None, company: str | None = None) -> str:
	"""Build the system prompt as a single string with XML-tagged sections.

	Calls build_system_prompt_blocks() and joins the blocks using XML tags.
	This is the primary entry point for all providers.

	Args:
		conversation_id: Optional conversation ID to read session context.
		company: Optional company override (used by automation executor).

	Returns:
		str: The complete system prompt.
	"""
	blocks = build_system_prompt_blocks(conversation_id=conversation_id, company=company)
	return "\n\n".join(f"<{b['tag']}>\n{b['content']}\n</{b['tag']}>" for b in blocks)
