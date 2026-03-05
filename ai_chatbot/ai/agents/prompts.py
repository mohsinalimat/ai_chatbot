# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Agent Prompt Templates

System prompts for the classifier, planner, analyst, and synthesis agents.
"""

from __future__ import annotations

import json


def get_classifier_prompt() -> str:
	"""System prompt for query complexity classification.

	The classifier decides whether to use multi-agent orchestration (complex)
	or the standard single-pass tool-calling flow (simple).
	"""
	return (
		"You are a query complexity classifier for an ERPNext business intelligence chatbot.\n\n"
		"Classify the user's query as either **simple** or **complex**.\n\n"
		"## Simple queries (single tool call or direct answer)\n"
		"- Single data retrieval: 'Show me sales this month', 'What is receivable aging?'\n"
		"- Record creation/update: 'Create a new lead for John'\n"
		"- Single metric lookup: 'What is our current inventory of laptops?'\n"
		"- Greetings or general questions about capabilities\n\n"
		"## Complex queries (require multiple tools, analysis, or comparison)\n"
		"- Multi-dimensional analysis: 'Compare sales across all regions this quarter'\n"
		"- Composite reports: 'Give me a complete financial health report for Q3'\n"
		"- Root cause analysis: 'What is causing the decline in profitability?'\n"
		"- Cross-functional queries: 'Analyze top customers buying patterns and suggest upselling'\n"
		"- Trend + recommendation: 'How are our receivables trending and what should we do?'\n"
		"- Queries needing data from 3+ different areas (sales + costs + margins, etc.)\n\n"
		"Respond with ONLY a JSON object, no other text:\n"
		'```json\n{"complexity": "simple" or "complex", "reason": "brief explanation"}\n```'
	)


def get_planner_prompt(tool_names: list[str]) -> str:
	"""System prompt for the planner agent that decomposes queries into steps.

	Args:
		tool_names: List of available tool names for the planner to reference.
	"""
	tools_list = ", ".join(tool_names[:40])  # Cap to avoid prompt bloat

	return (
		"You are a query planner for an ERPNext business intelligence chatbot.\n\n"
		"Your job is to decompose a complex user query into 2-6 concrete, executable steps.\n"
		"Each step should gather specific data or perform a specific analysis.\n\n"
		f"## Available tools\n{tools_list}\n\n"
		"## Plan format\n"
		"Respond with ONLY a JSON object, no other text:\n"
		"```json\n"
		"{\n"
		'  "steps": [\n'
		"    {\n"
		'      "step_id": "step_1",\n'
		'      "description": "Human-readable description of what this step does",\n'
		'      "tool_hint": "suggested_tool_name or null",\n'
		'      "depends_on": []\n'
		"    },\n"
		"    {\n"
		'      "step_id": "step_2",\n'
		'      "description": "Description",\n'
		'      "tool_hint": "another_tool_name",\n'
		'      "depends_on": ["step_1"]\n'
		"    }\n"
		"  ]\n"
		"}\n"
		"```\n\n"
		"## Rules\n"
		"- Each step should map to one or two tool calls at most.\n"
		"- Use `depends_on` when a step needs data from a previous step.\n"
		"- Steps without dependencies can run in any order.\n"
		"- Do NOT include a final 'summarize' or 'synthesize' step — that happens automatically.\n"
		"- Keep descriptions concise but specific (e.g., 'Fetch sales revenue by region for Q3' "
		"not 'Get some sales data').\n"
		"- The `tool_hint` is optional guidance — the executor may choose a different tool.\n"
		"- Maximum 6 steps. If the query needs more, combine related operations."
	)


def get_analyst_prompt(
	step_description: str,
	prior_results: dict[str, dict] | None = None,
	system_prompt: str = "",
) -> str:
	"""Build the analyst agent's system prompt for executing a single step.

	Args:
		step_description: What this step should accomplish.
		prior_results: Results from prior steps (keyed by step_id).
		system_prompt: The base system prompt (from build_system_prompt).
	"""
	parts = []

	if system_prompt:
		parts.append(system_prompt)

	parts.append(
		"\n## Current Task\n"
		"You are executing one step of a multi-step analysis plan.\n"
		"Focus ONLY on the specific task described below. Do not try to answer "
		"the user's full question — just complete this step and return the data.\n\n"
		f"**Step:** {step_description}"
	)

	if prior_results:
		parts.append("\n## Data from prior steps\n")
		for step_id, data in prior_results.items():
			desc = data.get("description", step_id)
			summary = data.get("summary", "")
			result = data.get("result", {})
			# Include summary and a compact version of the result
			parts.append(f"### {desc}\n")
			if summary:
				parts.append(f"Summary: {summary}\n")
			if result:
				compact = _compact_result(result)
				parts.append(f"Data: {compact}\n")

	parts.append(
		"\n## Instructions\n"
		"- Use the appropriate tool(s) to gather the required data.\n"
		"- After getting tool results, provide a brief summary of the findings.\n"
		"- Keep your response concise — focus on the key data points.\n"
		"- Do NOT produce charts or visualizations — just report the numbers and findings."
	)

	return "\n".join(parts)


def get_synthesis_prompt(steps_with_results: list[dict]) -> str:
	"""Build the synthesis prompt that combines all step results into a final response.

	Args:
		steps_with_results: List of dicts with description, summary, result for each step.
	"""
	parts = [
		"You are synthesizing the results of a multi-step analysis into a comprehensive response.\n\n"
		"## Analysis Results\n"
		"The following data was gathered from multiple analysis steps:\n"
	]

	for i, step_data in enumerate(steps_with_results, 1):
		desc = step_data.get("description", f"Step {i}")
		status = step_data.get("status", "unknown")
		summary = step_data.get("summary", "")
		result = step_data.get("result", {})

		parts.append(f"\n### Step {i}: {desc}")
		parts.append(f"Status: {status}")

		if status == "completed":
			if summary:
				parts.append(f"Summary: {summary}")
			if result:
				compact = _compact_result(result)
				parts.append(f"Data: {compact}")
		elif status == "failed":
			error = step_data.get("error", "Unknown error")
			parts.append(f"Error: {error}")
		elif status == "skipped":
			parts.append("Skipped due to dependency failure.")

	parts.append(
		"\n## Instructions\n"
		"- Synthesize all the above data into a comprehensive, well-structured response.\n"
		"- Use **markdown** formatting: tables for comparative data, bold for key figures, "
		"bullet points for insights.\n"
		"- Include the currency symbol/code when presenting monetary values.\n"
		"- If some steps failed, work with the data you have and note any limitations.\n"
		"- Provide actionable insights and recommendations where relevant.\n"
		"- Keep the response focused and avoid repeating raw numbers without context.\n"
		"- Mention the date range and company context when relevant."
	)

	return "\n".join(parts)


def _compact_result(result: dict, max_chars: int = 2000) -> str:
	"""Produce a compact JSON string of a tool result, capped to max_chars.

	Strips large rendering data (echart_option, hierarchical_table, bi_cards)
	and truncates the overall output.
	"""
	clean = {k: v for k, v in result.items() if k not in ("echart_option", "hierarchical_table", "bi_cards")}

	# Truncate large data arrays
	if isinstance(clean.get("data"), list) and len(clean["data"]) > 10:
		clean["data"] = clean["data"][:10]
		clean["_truncated"] = True

	text = json.dumps(clean, default=str)
	if len(text) > max_chars:
		text = text[:max_chars] + "... (truncated)"
	return text
