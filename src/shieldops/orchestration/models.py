"""Pydantic models for workflow orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    """Status of a workflow run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(StrEnum):
    """Supported agent types for orchestration."""

    INVESTIGATION = "investigation"
    REMEDIATION = "remediation"
    SECURITY = "security"
    LEARNING = "learning"
    SUPERVISOR = "supervisor"


class WorkflowStep(BaseModel):
    """A single step within a workflow run."""

    step_id: str = Field(default_factory=lambda: f"step-{uuid4().hex[:12]}")
    agent_type: AgentType
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class WorkflowRun(BaseModel):
    """A single execution of a named workflow."""

    run_id: str = Field(default_factory=lambda: f"wfrun-{uuid4().hex[:12]}")
    workflow_name: str
    trigger: str  # alert, manual, scheduled
    status: WorkflowStatus = WorkflowStatus.PENDING
    steps: list[WorkflowStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    initiated_by: str = "system"


class EscalationPolicy(BaseModel):
    """Escalation policy applied based on incident severity."""

    severity: str
    auto_remediate: bool = False
    notify_channels: list[str] = Field(default_factory=list)
    page_oncall: bool = False
    max_retries: int = 3
