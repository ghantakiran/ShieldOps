"""Pydantic v2 models for the investigation-to-remediation pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shieldops.remediation.models import K8sActionType


class PipelineStatus(StrEnum):
    """Lifecycle status of a pipeline run."""

    PENDING = "pending"
    INVESTIGATING = "investigating"
    RECOMMENDING = "recommending"
    AWAITING_APPROVAL = "awaiting_approval"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class TimelineEntry(BaseModel):
    """A single timestamped event in the pipeline run timeline."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    status: PipelineStatus
    message: str = ""


class RemediationRecommendation(BaseModel):
    """Maps an investigation hypothesis to a concrete K8s remediation action.

    When ``auto_approve`` is True the pipeline will execute the action
    without waiting for human approval.
    """

    hypothesis_title: str
    confidence: float = Field(ge=0.0, le=1.0)
    action_type: K8sActionType
    target_resource: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    auto_approve: bool = False
    executed: bool = False
    execution_result: dict[str, Any] = Field(default_factory=dict)


class PipelineRun(BaseModel):
    """Tracks a full investigation-to-remediation pipeline execution."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    alert_name: str
    namespace: str
    service: str | None = None
    status: PipelineStatus = PipelineStatus.PENDING
    investigation_result: dict[str, Any] = Field(default_factory=dict)
    remediation_actions: list[RemediationRecommendation] = Field(
        default_factory=list,
    )
    timeline: list[TimelineEntry] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    completed_at: datetime | None = None

    def add_timeline_entry(
        self,
        status: PipelineStatus,
        message: str = "",
    ) -> None:
        """Append a new timeline entry and update the run status."""
        self.status = status
        self.timeline.append(
            TimelineEntry(status=status, message=message),
        )
