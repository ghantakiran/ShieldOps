"""LLM prompt templates and response schemas for the Auto Remediation Agent."""

from pydantic import BaseModel, Field


class AssessmentOutput(BaseModel):
    """Structured output for assessment output."""

    issue_type: str = Field(description="Type of issue detected")
    severity: str = Field(description="Issue severity: critical/high/medium/low")
    root_cause: str = Field(description="Root cause analysis")


class PlanOutput(BaseModel):
    """Structured output for plan output."""

    strategy: str = Field(description="Remediation strategy")
    risk_score: float = Field(description="Remediation risk 0-100")
    reasoning: str = Field(description="Planning reasoning")


class FixOutput(BaseModel):
    """Structured output for fix output."""

    fixes_count: int = Field(description="Number of fixes executed")
    success_rate: float = Field(description="Fix success rate 0-100")
    reasoning: str = Field(description="Fix execution reasoning")


SYSTEM_ASSESS = """\
You are an expert SRE issue assessor.

Given the remediation configuration:
1. Identify the root cause of the issue
2. Assess the blast radius and affected services
3. Classify the issue type and severity

Focus on: service health, infrastructure state, configuration drift."""


SYSTEM_PLAN = """\
You are an expert remediation planner.

Given the issue assessment:
1. Design the optimal remediation strategy
2. Plan step-by-step fix actions
3. Estimate risk and duration for each step

Balance speed of resolution with safety and rollback capability."""


SYSTEM_FIX = """\
You are an expert automated remediation executor.

Given the remediation plan:
1. Execute fix actions in the correct order
2. Validate each step before proceeding
3. Prepare rollback for any failed action

Minimize blast radius and ensure all changes are auditable."""
