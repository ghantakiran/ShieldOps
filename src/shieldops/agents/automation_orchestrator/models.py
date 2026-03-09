"""State models for the Automation Orchestrator Agent."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TriggerType(StrEnum):
    """Types of events that can trigger automation rules."""

    ALERT = "alert"
    K8S_EVENT = "k8s_event"
    VULNERABILITY_SCAN = "vulnerability_scan"
    COST_ALERT = "cost_alert"
    SLO_ALERT = "slo_alert"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    CUSTOM = "custom"


class ActionType(StrEnum):
    """Types of actions an automation rule can execute."""

    LAUNCH_AGENT = "launch_agent"
    NOTIFY = "notify"
    CREATE_TICKET = "create_ticket"
    REMEDIATE = "remediate"
    PATCH = "patch"
    SCALE = "scale"
    SCAN = "scan"
    BENCHMARK = "benchmark"
    ANALYZE = "analyze"
    GATE = "gate"
    CHECK = "check"
    TAG = "tag"
    INVESTIGATE = "investigate"


class TriggerCondition(BaseModel):
    """Defines when an automation rule should fire."""

    type: TriggerType
    source: str  # e.g., "PagerDuty", "Kubernetes", "GitHub Actions"
    condition_expression: str  # e.g., "severity = critical", "reason = OOMKilled, count > 3 in 10m"
    debounce_seconds: int = 0
    cooldown_seconds: int = 300


class ActionStep(BaseModel):
    """A single step in an automation rule's action chain."""

    type: ActionType
    target: str  # e.g., "Investigation Agent", "Slack #incidents", "Jira"
    parameters: dict[str, Any] = Field(default_factory=dict)
    detail: str = ""
    timeout_seconds: int = 300
    continue_on_failure: bool = False


class AutomationRule(BaseModel):
    """An automation rule that maps triggers to action chains."""

    id: str
    name: str
    description: str = ""
    trigger: TriggerCondition
    actions: list[ActionStep]
    policy_gate: str = ""  # OPA policy name
    enabled: bool = True
    category: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered: datetime | None = None
    executions_24h: int = 0
    total_executions: int = 0
    success_rate: float = 1.0
    max_concurrent: int = 1


class AutomationEvent(BaseModel):
    """An incoming event to be evaluated against automation rules."""

    id: str
    rule_id: str = ""
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = ""


class ActionResult(BaseModel):
    """Result of executing a single action step."""

    step_index: int
    action_type: ActionType
    target: str
    status: str = "success"  # success, failed, skipped, timeout
    output: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    error: str | None = None


class ReasoningStep(BaseModel):
    """A single step in the agent's reasoning chain."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int
    tool_used: str | None = None


class AutomationState(BaseModel):
    """Full state of an automation orchestrator workflow (LangGraph state)."""

    # Input
    event: AutomationEvent
    rule: AutomationRule

    # Processing
    policy_allowed: bool = False
    policy_reason: str = ""
    requires_approval: bool = False
    approval_status: str = "not_required"  # pending, approved, denied, not_required
    current_action_index: int = 0
    action_results: list[ActionResult] = Field(default_factory=list)

    # Output
    execution_id: str = ""
    overall_status: str = ""  # completed, partial, failed, denied, awaiting_approval
    summary: str = ""
    notifications_sent: list[str] = Field(default_factory=list)

    # Metadata
    execution_start: datetime | None = None
    execution_duration_ms: int = 0
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
