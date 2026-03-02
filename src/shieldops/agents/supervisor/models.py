"""State models for the Supervisor Agent LangGraph workflow."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(StrEnum):
    """Types of tasks the supervisor can delegate."""

    INVESTIGATE = "investigate"
    REMEDIATE = "remediate"
    SECURITY_SCAN = "security_scan"
    COST_ANALYSIS = "cost_analysis"
    LEARN = "learn"
    SOC_ANALYSIS = "soc_analysis"
    THREAT_HUNT = "threat_hunt"
    FORENSICS = "forensics"
    DECEPTION = "deception"


class TaskStatus(StrEnum):
    """Status of a delegated task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class EventClassification(BaseModel):
    """Result of classifying an incoming event."""

    event_type: str  # alert, incident, cve_alert, schedule, feedback, etc.
    task_type: TaskType
    priority: str = "medium"  # critical, high, medium, low
    confidence: float = 1.0
    reasoning: str = ""


class DelegatedTask(BaseModel):
    """A task delegated to a specialist agent."""

    task_id: str
    task_type: TaskType
    agent_name: str  # investigation, remediation, security, cost, learning
    status: TaskStatus = TaskStatus.PENDING
    input_data: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int = 0


class EscalationRecord(BaseModel):
    """Record of an escalation to a human operator."""

    escalation_id: str
    reason: str  # low_confidence, agent_failure, policy_denied, timeout, critical_risk
    task_id: str | None = None
    task_type: TaskType | None = None
    channel: str = "slack"  # slack, pagerduty, email
    notified_at: datetime | None = None
    acknowledged: bool = False


class ChainedWorkflow(BaseModel):
    """Record of a chained workflow (e.g. investigation → remediation)."""

    source_task_id: str
    source_task_type: TaskType
    chained_task_id: str
    chained_task_type: TaskType
    trigger_reason: str = ""  # e.g. "high confidence investigation with recommended action"


class SupervisorStep(BaseModel):
    """Audit trail entry for the supervisor workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str = ""


class SupervisorState(BaseModel):
    """Full state for a supervisor orchestration run through the LangGraph workflow."""

    session_id: str = ""
    event: dict[str, Any] = Field(default_factory=dict)

    # Classification
    classification: EventClassification | None = None

    # Delegation
    delegated_tasks: list[DelegatedTask] = Field(default_factory=list)
    active_task: DelegatedTask | None = None

    # Chaining
    chained_workflows: list[ChainedWorkflow] = Field(default_factory=list)
    should_chain: bool = False
    chain_task_type: TaskType | None = None

    # Escalation
    escalations: list[EscalationRecord] = Field(default_factory=list)
    needs_escalation: bool = False

    # Learning trigger
    should_trigger_learning: bool = False

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[SupervisorStep] = Field(default_factory=list)
    current_step: str = "pending"
    error: str | None = None
