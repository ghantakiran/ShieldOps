"""Change Approval Flow Tracker — track change approval workflows, bottlenecks, and cycle times."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ApprovalStage(StrEnum):
    SUBMITTED = "submitted"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalPriority(StrEnum):
    EMERGENCY = "emergency"
    HIGH = "high"
    STANDARD = "standard"
    LOW = "low"
    ROUTINE = "routine"


class ApprovalChannel(StrEnum):
    AUTOMATED = "automated"
    PEER_REVIEW = "peer_review"
    MANAGER = "manager"
    CAB = "cab"
    EXECUTIVE = "executive"


# --- Models ---


class ApprovalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    approval_stage: ApprovalStage = ApprovalStage.SUBMITTED
    approval_priority: ApprovalPriority = ApprovalPriority.STANDARD
    approval_channel: ApprovalChannel = ApprovalChannel.AUTOMATED
    approval_time_hours: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ApprovalMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    approval_stage: ApprovalStage = ApprovalStage.SUBMITTED
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeApprovalFlowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    slow_approvals: int = 0
    avg_approval_time_hours: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_channel: dict[str, int] = Field(default_factory=dict)
    top_slow: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeApprovalFlowTracker:
    """Track change approval workflows, bottlenecks, and cycle times."""

    def __init__(
        self,
        max_records: int = 200000,
        max_approval_time_hours: float = 24.0,
    ) -> None:
        self._max_records = max_records
        self._max_approval_time_hours = max_approval_time_hours
        self._records: list[ApprovalRecord] = []
        self._metrics: list[ApprovalMetric] = []
        logger.info(
            "change_approval_flow.initialized",
            max_records=max_records,
            max_approval_time_hours=max_approval_time_hours,
        )

    # -- record / get / list ------------------------------------------------

    def record_approval(
        self,
        change_id: str,
        approval_stage: ApprovalStage = ApprovalStage.SUBMITTED,
        approval_priority: ApprovalPriority = ApprovalPriority.STANDARD,
        approval_channel: ApprovalChannel = ApprovalChannel.AUTOMATED,
        approval_time_hours: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            change_id=change_id,
            approval_stage=approval_stage,
            approval_priority=approval_priority,
            approval_channel=approval_channel,
            approval_time_hours=approval_time_hours,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_approval_flow.approval_recorded",
            record_id=record.id,
            change_id=change_id,
            approval_stage=approval_stage.value,
            approval_priority=approval_priority.value,
        )
        return record

    def get_approval(self, record_id: str) -> ApprovalRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_approvals(
        self,
        stage: ApprovalStage | None = None,
        priority: ApprovalPriority | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ApprovalRecord]:
        results = list(self._records)
        if stage is not None:
            results = [r for r in results if r.approval_stage == stage]
        if priority is not None:
            results = [r for r in results if r.approval_priority == priority]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        change_id: str,
        approval_stage: ApprovalStage = ApprovalStage.SUBMITTED,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ApprovalMetric:
        metric = ApprovalMetric(
            change_id=change_id,
            approval_stage=approval_stage,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "change_approval_flow.metric_added",
            change_id=change_id,
            approval_stage=approval_stage.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_approval_distribution(self) -> dict[str, Any]:
        """Group by approval_stage; return count and avg approval_time_hours."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.approval_stage.value
            stage_data.setdefault(key, []).append(r.approval_time_hours)
        result: dict[str, Any] = {}
        for stage, times in stage_data.items():
            result[stage] = {
                "count": len(times),
                "avg_approval_time_hours": round(sum(times) / len(times), 2),
            }
        return result

    def identify_slow_approvals(self) -> list[dict[str, Any]]:
        """Return records where approval_time_hours > max_approval_time_hours."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.approval_time_hours > self._max_approval_time_hours:
                results.append(
                    {
                        "record_id": r.id,
                        "change_id": r.change_id,
                        "approval_stage": r.approval_stage.value,
                        "approval_time_hours": r.approval_time_hours,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_approval_time(self) -> list[dict[str, Any]]:
        """Group by service, avg approval_time_hours, sort descending."""
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service, []).append(r.approval_time_hours)
        results: list[dict[str, Any]] = []
        for svc, times in svc_times.items():
            results.append(
                {
                    "service": svc,
                    "avg_approval_time_hours": round(sum(times) / len(times), 2),
                }
            )
        results.sort(key=lambda x: x["avg_approval_time_hours"], reverse=True)
        return results

    def detect_approval_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ChangeApprovalFlowReport:
        by_stage: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        for r in self._records:
            by_stage[r.approval_stage.value] = by_stage.get(r.approval_stage.value, 0) + 1
            by_priority[r.approval_priority.value] = (
                by_priority.get(r.approval_priority.value, 0) + 1
            )
            by_channel[r.approval_channel.value] = by_channel.get(r.approval_channel.value, 0) + 1
        slow_approvals = sum(
            1 for r in self._records if r.approval_time_hours > self._max_approval_time_hours
        )
        times = [r.approval_time_hours for r in self._records]
        avg_approval_time_hours = round(sum(times) / len(times), 2) if times else 0.0
        slow_list = self.identify_slow_approvals()
        top_slow = [o["change_id"] for o in slow_list[:5]]
        recs: list[str] = []
        if self._records and avg_approval_time_hours > self._max_approval_time_hours:
            recs.append(
                f"Avg approval time {avg_approval_time_hours}h exceeds threshold "
                f"({self._max_approval_time_hours}h)"
            )
        if slow_approvals > 0:
            recs.append(f"{slow_approvals} slow approval(s) — investigate bottlenecks")
        if not recs:
            recs.append("Change approval flow health is acceptable")
        return ChangeApprovalFlowReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            slow_approvals=slow_approvals,
            avg_approval_time_hours=avg_approval_time_hours,
            by_stage=by_stage,
            by_priority=by_priority,
            by_channel=by_channel,
            top_slow=top_slow,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("change_approval_flow.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.approval_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_approval_time_hours": self._max_approval_time_hours,
            "approval_stage_distribution": stage_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
