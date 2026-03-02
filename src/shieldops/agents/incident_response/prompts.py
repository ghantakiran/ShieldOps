"""LLM prompt templates and response schemas for the Incident Response Agent."""

from pydantic import BaseModel, Field


class AssessmentOutput(BaseModel):
    """Structured output for incident assessment."""

    severity: str = Field(description="Incident severity: critical/high/medium/low")
    assessment_score: float = Field(description="Assessment priority score 0-100")
    incident_type: str = Field(description="Type of incident detected")
    reasoning: str = Field(description="Assessment reasoning")


class ContainmentPlanOutput(BaseModel):
    """Structured output for containment planning."""

    actions: list[dict[str, str]] = Field(description="Containment actions with type, target, risk")
    auto_executable: bool = Field(description="Whether actions can be auto-executed")
    reasoning: str = Field(description="Containment reasoning")


class RecoveryPlanOutput(BaseModel):
    """Structured output for recovery planning."""

    tasks: list[dict[str, str]] = Field(description="Recovery tasks with type, service, priority")
    estimated_duration_min: int = Field(description="Estimated total recovery time in minutes")
    reasoning: str = Field(description="Recovery reasoning")


SYSTEM_ASSESS = """\
You are an expert incident responder performing initial incident assessment.

Given the incident data and context, determine:
1. Incident severity (critical, high, medium, low)
2. Assessment priority score (0-100, higher = more urgent)
3. Incident type classification

Consider: blast radius, data sensitivity, service criticality, active threat indicators."""


SYSTEM_CONTAINMENT = """\
You are an expert incident responder planning containment actions.

Given the incident assessment and affected assets:
1. Plan specific containment actions to isolate the threat
2. Assess risk level for each action
3. Determine which actions can be safely automated

Follow the principle of minimum blast radius while ensuring threat isolation."""


SYSTEM_RECOVERY = """\
You are an expert incident responder planning service recovery.

Given the incident status and affected services:
1. Plan recovery tasks in priority order
2. Estimate duration for each task
3. Identify dependencies between recovery steps

Prioritize critical services and ensure validation before declaring recovery complete."""
