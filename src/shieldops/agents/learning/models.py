"""State models for the Learning Agent LangGraph workflow."""

from datetime import datetime

from pydantic import BaseModel, Field

from shieldops.models.base import Environment


class IncidentOutcome(BaseModel):
    """Record of a resolved incident and its outcome."""

    incident_id: str
    alert_type: str  # e.g. high_cpu, oom_kill, latency_spike, disk_full
    environment: Environment = Environment.PRODUCTION
    root_cause: str = ""
    resolution_action: str = ""  # what fixed it (restart_pod, scale_horizontal, etc.)
    investigation_duration_ms: int = 0
    remediation_duration_ms: int = 0
    was_automated: bool = False
    was_correct: bool = True  # did the automated action actually fix the issue?
    feedback: str = ""  # human feedback if any


class PatternInsight(BaseModel):
    """A pattern discovered from analyzing incident outcomes."""

    pattern_id: str
    alert_type: str
    description: str
    frequency: int = 1  # how many incidents match this pattern
    avg_resolution_time_ms: int = 0
    common_root_cause: str = ""
    common_resolution: str = ""
    confidence: float = 0.0
    environments: list[str] = Field(default_factory=list)


class PlaybookUpdate(BaseModel):
    """A suggested update to an operational playbook."""

    playbook_id: str
    alert_type: str
    update_type: str  # new_playbook, add_step, modify_step, deprecate
    title: str = ""
    description: str = ""
    steps: list[str] = Field(default_factory=list)
    priority: str = "medium"  # low, medium, high
    based_on_incidents: list[str] = Field(default_factory=list)


class ThresholdAdjustment(BaseModel):
    """A recommended adjustment to alerting thresholds."""

    adjustment_id: str
    metric_name: str
    current_threshold: float
    recommended_threshold: float
    direction: str  # increase, decrease
    reason: str = ""
    false_positive_reduction: float = 0.0  # estimated % reduction in false positives
    based_on_incidents: list[str] = Field(default_factory=list)


class LearningStep(BaseModel):
    """Audit trail entry for the learning workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str = ""


class LearningState(BaseModel):
    """Full state for a learning cycle through the LangGraph workflow."""

    learning_id: str = ""
    learning_type: str = "full"  # full, pattern_only, playbook_only, threshold_only
    target_period: str = "30d"

    # Input: incident outcomes to learn from
    incident_outcomes: list[IncidentOutcome] = Field(default_factory=list)
    total_incidents_analyzed: int = 0

    # Pattern analysis
    pattern_insights: list[PatternInsight] = Field(default_factory=list)
    recurring_pattern_count: int = 0

    # Playbook updates
    playbook_updates: list[PlaybookUpdate] = Field(default_factory=list)

    # Threshold adjustments
    threshold_adjustments: list[ThresholdAdjustment] = Field(default_factory=list)
    estimated_false_positive_reduction: float = 0.0

    # Effectiveness metrics
    automation_accuracy: float = 0.0  # % of automated actions that were correct
    avg_resolution_time_ms: int = 0
    improvement_score: float = 0.0  # overall improvement score 0-100

    # Workflow tracking
    learning_start: datetime | None = None
    learning_duration_ms: int = 0
    reasoning_chain: list[LearningStep] = Field(default_factory=list)
    current_step: str = "pending"
    error: str | None = None
