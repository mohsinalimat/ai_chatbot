# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt
"""
Agent Context — shared state for multi-agent orchestration.

Dataclasses that flow through the planner → analyst → synthesis pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentStep:
	"""A single step in an agent execution plan."""

	step_id: str
	description: str
	tool_hint: str | None = None
	depends_on: list[str] = field(default_factory=list)
	is_synthesis: bool = False

	# Execution state (mutated by the analyst)
	status: str = "pending"  # pending | running | completed | failed | skipped
	result: dict | None = None
	result_summary: str = ""
	error: str | None = None
	tool_calls: list[dict] = field(default_factory=list)
	tool_results: list[dict] = field(default_factory=list)
	tokens_used: int = 0


@dataclass
class AgentContext:
	"""Shared context passed through the orchestration pipeline."""

	query: str
	conversation_id: str
	stream_id: str | None = None
	user: str | None = None

	# Plan produced by the planner
	plan: list[AgentStep] = field(default_factory=list)

	# Aggregated across all steps
	all_tool_calls: list[dict] = field(default_factory=list)
	all_tool_results: list[dict] = field(default_factory=list)
	total_tokens: int = 0
	errors: list[str] = field(default_factory=list)

	def get_step(self, step_id: str) -> AgentStep | None:
		"""Look up a step by ID."""
		for step in self.plan:
			if step.step_id == step_id:
				return step
		return None

	def get_completed_results(self) -> dict[str, dict]:
		"""Get results from all completed steps, keyed by step_id."""
		return {
			step.step_id: {
				"description": step.description,
				"result": step.result,
				"summary": step.result_summary,
			}
			for step in self.plan
			if step.status == "completed" and step.result is not None
		}

	def get_dependency_results(self, step: AgentStep) -> dict[str, dict]:
		"""Get results from steps that this step depends on."""
		results = {}
		for dep_id in step.depends_on:
			dep_step = self.get_step(dep_id)
			if dep_step and dep_step.status == "completed" and dep_step.result is not None:
				results[dep_id] = {
					"description": dep_step.description,
					"result": dep_step.result,
					"summary": dep_step.result_summary,
				}
		return results

	def failed_count(self) -> int:
		"""Count how many steps have failed."""
		return sum(1 for step in self.plan if step.status == "failed")

	def total_data_steps(self) -> int:
		"""Count non-synthesis steps."""
		return sum(1 for step in self.plan if not step.is_synthesis)
