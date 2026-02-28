"""Change Approval Analyzer — analyze change approval velocity, bottlenecks, and wait times."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ApprovalOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    AUTO_APPROVED = "auto_approved"
    ESCALATED = "escalated"


class ApprovalBottleneck(StrEnum):
    REVIEWER_UNAVAILABLE = "reviewer_unavailable"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    RISK_ASSESSMENT = "risk_assessment"
    COMPLIANCE_CHECK = "compliance_check"
    TESTING_INCOMPLETE = "testing_incomplete"


class ApprovalSpeed(StrEnum):
    INSTANT = "instant"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    BLOCKED = "blocked"


# --- Models ---


class ApprovalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    outcome: ApprovalOutcome = ApprovalOutcome.APPROVED
    speed: ApprovalSpeed = ApprovalSpeed.NORMAL
    wait_hours: float = 0.0
    reviewer_id: str = ""
    environment: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ApprovalBottleneckDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    bottleneck: ApprovalBottleneck = ApprovalBottleneck.REVIEWER_UNAVAILABLE
    delay_hours: float = 0.0
    resolution: str = ""
    resolved: bool = False
    created_at: float = Field(default_factory=time.time)


class ApprovalAnalyzerReport(BaseModel):
    total_approvals: int = 0
    total_bottlenecks: int = 0
    avg_wait_hours: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    slow_approval_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeApprovalAnalyzer:
    """Analyze change approval velocity, bottlenecks, and wait times."""

    def __init__(
        self,
        max_records: int = 200000,
        max_approval_hours: float = 24.0,
    ) -> None:
        self._max_records = max_records
        self._max_approval_hours = max_approval_hours
        self._records: list[ApprovalRecord] = []
        self._bottlenecks: list[ApprovalBottleneckDetail] = []
        logger.info(
            "approval_analyzer.initialized",
            max_records=max_records,
            max_approval_hours=max_approval_hours,
        )

    # -- record / get / list ---------------------------------------------

    def record_approval(
        self,
        change_id: str,
        outcome: ApprovalOutcome = ApprovalOutcome.APPROVED,
        speed: ApprovalSpeed = ApprovalSpeed.NORMAL,
        wait_hours: float = 0.0,
        reviewer_id: str = "",
        environment: str = "",
        details: str = "",
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            change_id=change_id,
            outcome=outcome,
            speed=speed,
            wait_hours=wait_hours,
            reviewer_id=reviewer_id,
            environment=environment,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "approval_analyzer.approval_recorded",
            record_id=record.id,
            change_id=change_id,
            outcome=outcome.value,
            wait_hours=wait_hours,
        )
        return record

    def get_approval(self, record_id: str) -> ApprovalRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_approvals(
        self,
        change_id: str | None = None,
        outcome: ApprovalOutcome | None = None,
        limit: int = 50,
    ) -> list[ApprovalRecord]:
        results = list(self._records)
        if change_id is not None:
            results = [r for r in results if r.change_id == change_id]
        if outcome is not None:
            results = [r for r in results if r.outcome == outcome]
        return results[-limit:]

    def add_bottleneck(
        self,
        change_id: str,
        bottleneck: ApprovalBottleneck = ApprovalBottleneck.REVIEWER_UNAVAILABLE,
        delay_hours: float = 0.0,
        resolution: str = "",
        resolved: bool = False,
    ) -> ApprovalBottleneckDetail:
        detail = ApprovalBottleneckDetail(
            change_id=change_id,
            bottleneck=bottleneck,
            delay_hours=delay_hours,
            resolution=resolution,
            resolved=resolved,
        )
        self._bottlenecks.append(detail)
        if len(self._bottlenecks) > self._max_records:
            self._bottlenecks = self._bottlenecks[-self._max_records :]
        logger.info(
            "approval_analyzer.bottleneck_added",
            change_id=change_id,
            bottleneck=bottleneck.value,
            delay_hours=delay_hours,
        )
        return detail

    # -- domain operations -----------------------------------------------

    def analyze_approval_velocity(self, environment: str) -> dict[str, Any]:
        """Analyze approval velocity for a specific environment."""
        records = [r for r in self._records if r.environment == environment]
        if not records:
            return {"environment": environment, "status": "no_data"}
        avg_wait = round(sum(r.wait_hours for r in records) / len(records), 2)
        slow_count = sum(1 for r in records if r.wait_hours > self._max_approval_hours)
        approved_count = sum(1 for r in records if r.outcome == ApprovalOutcome.APPROVED)
        approval_rate = round(approved_count / len(records) * 100, 2)
        return {
            "environment": environment,
            "total_approvals": len(records),
            "avg_wait_hours": avg_wait,
            "slow_approval_count": slow_count,
            "approval_rate_pct": approval_rate,
            "within_threshold": avg_wait <= self._max_approval_hours,
        }

    def identify_slow_approvals(self) -> list[dict[str, Any]]:
        """Find approvals that exceeded the maximum approval time threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.wait_hours > self._max_approval_hours:
                results.append(
                    {
                        "change_id": r.change_id,
                        "wait_hours": r.wait_hours,
                        "outcome": r.outcome.value,
                        "environment": r.environment,
                        "reviewer_id": r.reviewer_id,
                        "exceeded_by_hours": round(r.wait_hours - self._max_approval_hours, 2),
                    }
                )
        results.sort(key=lambda x: x["wait_hours"], reverse=True)
        return results

    def rank_by_wait_time(self) -> list[dict[str, Any]]:
        """Rank approval records by wait time descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "change_id": r.change_id,
                    "wait_hours": r.wait_hours,
                    "speed": r.speed.value,
                    "outcome": r.outcome.value,
                    "environment": r.environment,
                }
            )
        results.sort(key=lambda x: x["wait_hours"], reverse=True)
        return results

    def detect_approval_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect the most frequent bottleneck types and their total delay impact."""
        bottleneck_counts: dict[str, int] = {}
        bottleneck_delay: dict[str, float] = {}
        unresolved_counts: dict[str, int] = {}
        for b in self._bottlenecks:
            key = b.bottleneck.value
            bottleneck_counts[key] = bottleneck_counts.get(key, 0) + 1
            bottleneck_delay[key] = bottleneck_delay.get(key, 0.0) + b.delay_hours
            if not b.resolved:
                unresolved_counts[key] = unresolved_counts.get(key, 0) + 1
        results: list[dict[str, Any]] = []
        for bottleneck, count in bottleneck_counts.items():
            results.append(
                {
                    "bottleneck": bottleneck,
                    "occurrence_count": count,
                    "total_delay_hours": round(bottleneck_delay.get(bottleneck, 0.0), 2),
                    "unresolved_count": unresolved_counts.get(bottleneck, 0),
                }
            )
        results.sort(key=lambda x: x["total_delay_hours"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ApprovalAnalyzerReport:
        by_outcome: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        for r in self._records:
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
            by_speed[r.speed.value] = by_speed.get(r.speed.value, 0) + 1
        avg_wait = (
            round(sum(r.wait_hours for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        slow_approvals = self.identify_slow_approvals()
        bottlenecks = self.detect_approval_bottlenecks()
        recs: list[str] = []
        if avg_wait > self._max_approval_hours:
            recs.append(f"Average wait {avg_wait}h exceeds {self._max_approval_hours}h threshold")
        if slow_approvals:
            recs.append(f"{len(slow_approvals)} approval(s) exceeded the time threshold")
        if bottlenecks:
            top = bottlenecks[0]["bottleneck"]
            recs.append(f"Top bottleneck: {top} — address to improve approval velocity")
        if not recs:
            recs.append("Approval velocity is within acceptable thresholds")
        return ApprovalAnalyzerReport(
            total_approvals=len(self._records),
            total_bottlenecks=len(self._bottlenecks),
            avg_wait_hours=avg_wait,
            by_outcome=by_outcome,
            by_speed=by_speed,
            slow_approval_count=len(slow_approvals),
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._bottlenecks.clear()
        logger.info("approval_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            key = r.outcome.value
            outcome_dist[key] = outcome_dist.get(key, 0) + 1
        return {
            "total_approvals": len(self._records),
            "total_bottlenecks": len(self._bottlenecks),
            "max_approval_hours": self._max_approval_hours,
            "outcome_distribution": outcome_dist,
            "unique_changes": len({r.change_id for r in self._records}),
        }
