"""LLM prompt templates and response schemas for the Automation Orchestrator Agent."""

from typing import Any

from pydantic import BaseModel, Field

# --- Response schemas for structured LLM output ---


class TriggerEvalResult(BaseModel):
    """Structured output from LLM trigger evaluation."""

    matches: bool = Field(description="Whether the event matches the trigger condition")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence that the event matches (0.0-1.0)"
    )
    matched_conditions: list[str] = Field(description="Specific conditions that matched the event")
    context_enrichment: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context extracted from the event for downstream actions",
    )


class ExecutionPlan(BaseModel):
    """Structured output for action chain execution planning."""

    should_execute: bool = Field(description="Whether the action chain should be executed")
    action_order: list[int] = Field(description="Ordered list of action step indices to execute")
    skip_actions: list[int] = Field(description="Action step indices to skip with reasoning")
    reasoning: str = Field(description="Explanation of the execution plan and any modifications")


class ExecutionSummary(BaseModel):
    """Structured output for automation execution summary."""

    summary: str = Field(description="Concise summary of what the automation did")
    outcome: str = Field(description="Overall outcome: success, partial_success, failure")
    impact: str = Field(description="Description of the impact of the automation execution")
    follow_up_actions: list[str] = Field(description="Recommended follow-up actions if any")


# --- Prompt templates ---

SYSTEM_EVALUATE_TRIGGER = """\
You are an expert SRE automation engine evaluating whether an incoming event \
matches an automation rule's trigger condition.

Given:
- The event data (type, source, payload)
- The rule's trigger condition (type, source, expression)

Your task is to:
1. Determine if the event matches the trigger condition
2. Assess your confidence in the match
3. List which specific conditions matched
4. Extract any context from the event that enriches downstream actions

Be precise: only mark as matching if the event genuinely satisfies the trigger expression. \
Consider partial matches and edge cases carefully."""

SYSTEM_PLAN_EXECUTION = """\
You are an expert SRE automation planner. Given an automation rule's action chain \
and the event context, plan the optimal execution.

Your task is to:
1. Determine the best order for executing the action steps
2. Identify any steps that should be skipped (e.g., redundant, inapplicable)
3. Consider dependencies between actions
4. Account for the event context and severity

Important:
- Respect the continue_on_failure flag for each step
- Consider timeout constraints
- If a gate or check action fails, downstream actions may need to be skipped
- Prioritize safety: notification and investigation actions before remediation"""

SYSTEM_SUMMARIZE_EXECUTION = """\
You are an expert SRE summarizing the results of an automated workflow execution.

Given the rule definition, event context, and results of each action step, \
produce a clear summary suitable for notification to an on-call engineer.

Include:
1. What triggered the automation
2. What actions were taken and their outcomes
3. The overall impact (what was fixed, mitigated, or escalated)
4. Any follow-up actions the engineer should consider

Be concise but complete. Engineers rely on these summaries for situational awareness."""
