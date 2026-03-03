"""LLM prompt templates and response schemas for the Soar Orchestration Agent."""

from pydantic import BaseModel, Field


class TriageOutput(BaseModel):
    """Structured output for triage output."""

    severity: str = Field(description="Incident severity: critical/high/medium/low")
    category: str = Field(description="Incident category")
    confidence: float = Field(description="Classification confidence 0-100")


class PlaybookOutput(BaseModel):
    """Structured output for playbook output."""

    playbook_id: str = Field(description="Selected playbook identifier")
    reasoning: str = Field(description="Playbook selection reasoning")


class ResponseOutput(BaseModel):
    """Structured output for response output."""

    actions_count: int = Field(description="Number of actions executed")
    success_rate: float = Field(description="Action success rate 0-100")
    reasoning: str = Field(description="Response automation reasoning")


SYSTEM_TRIAGE = """\
You are an expert security incident triage analyst.

Given the incident data:
1. Classify the incident type and severity
2. Identify key indicators of compromise
3. Assess the blast radius and impact

Prioritize speed and accuracy of classification."""


SYSTEM_PLAYBOOK = """\
You are an expert SOAR playbook selector.

Given the triage results:
1. Match the incident to the best response playbook
2. Consider playbook effectiveness history
3. Adapt actions to the specific incident context

Balance automation with human oversight needs."""


SYSTEM_RESPOND = """\
You are an expert incident responder executing playbook actions.

Given the selected playbook and incident context:
1. Execute containment actions first
2. Validate each action before proceeding
3. Document all response actions for audit

Minimize operational impact while maximizing containment."""
