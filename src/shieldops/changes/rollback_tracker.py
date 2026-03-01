"""Deployment Rollback Tracker — track rollbacks, patterns, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RollbackReason(StrEnum):
    BUG = "bug"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    CONFIGURATION = "configuration"


class RollbackImpact(StrEnum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class RollbackStatus(StrEnum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# --- Models ---


class RollbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    rollback_reason: RollbackReason = RollbackReason.BUG
    rollback_impact: RollbackImpact = RollbackImpact.NONE
    rollback_status: RollbackStatus = RollbackStatus.INITIATED
    duration_minutes: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RollbackPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    rollback_reason: RollbackReason = RollbackReason.BUG
    frequency_threshold: int = 0
    auto_block: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RollbackTrackerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_patterns: int = 0
    failed_rollbacks: int = 0
    avg_duration_minutes: float = 0.0
    by_reason: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    frequent_rollers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentRollbackTracker:
    """Track deployment rollbacks, identify patterns, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_rollback_rate_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_rollback_rate_pct = max_rollback_rate_pct
        self._records: list[RollbackRecord] = []
        self._patterns: list[RollbackPattern] = []
        logger.info(
            "rollback_tracker.initialized",
            max_records=max_records,
            max_rollback_rate_pct=max_rollback_rate_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_rollback(
        self,
        deployment_id: str,
        rollback_reason: RollbackReason = RollbackReason.BUG,
        rollback_impact: RollbackImpact = RollbackImpact.NONE,
        rollback_status: RollbackStatus = RollbackStatus.INITIATED,
        duration_minutes: float = 0.0,
        team: str = "",
    ) -> RollbackRecord:
        record = RollbackRecord(
            deployment_id=deployment_id,
            rollback_reason=rollback_reason,
            rollback_impact=rollback_impact,
            rollback_status=rollback_status,
            duration_minutes=duration_minutes,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "rollback_tracker.rollback_recorded",
            record_id=record.id,
            deployment_id=deployment_id,
            rollback_reason=rollback_reason.value,
            rollback_impact=rollback_impact.value,
        )
        return record

    def get_rollback(self, record_id: str) -> RollbackRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rollbacks(
        self,
        reason: RollbackReason | None = None,
        impact: RollbackImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RollbackRecord]:
        results = list(self._records)
        if reason is not None:
            results = [r for r in results if r.rollback_reason == reason]
        if impact is not None:
            results = [r for r in results if r.rollback_impact == impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_pattern(
        self,
        service_pattern: str,
        rollback_reason: RollbackReason = RollbackReason.BUG,
        frequency_threshold: int = 0,
        auto_block: bool = False,
        description: str = "",
    ) -> RollbackPattern:
        pattern = RollbackPattern(
            service_pattern=service_pattern,
            rollback_reason=rollback_reason,
            frequency_threshold=frequency_threshold,
            auto_block=auto_block,
            description=description,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "rollback_tracker.pattern_added",
            service_pattern=service_pattern,
            rollback_reason=rollback_reason.value,
            frequency_threshold=frequency_threshold,
        )
        return pattern

    # -- domain operations --------------------------------------------------

    def analyze_rollback_patterns(self) -> dict[str, Any]:
        """Group by reason; return count and avg duration per reason."""
        reason_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.rollback_reason.value
            reason_data.setdefault(key, []).append(r.duration_minutes)
        result: dict[str, Any] = {}
        for reason, durations in reason_data.items():
            result[reason] = {
                "count": len(durations),
                "avg_duration": round(sum(durations) / len(durations), 2),
            }
        return result

    def identify_frequent_rollers(self) -> list[dict[str, Any]]:
        """Return records where status == FAILED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.rollback_status == RollbackStatus.FAILED:
                results.append(
                    {
                        "record_id": r.id,
                        "deployment_id": r.deployment_id,
                        "rollback_reason": r.rollback_reason.value,
                        "rollback_impact": r.rollback_impact.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_duration(self) -> list[dict[str, Any]]:
        """Group by team, total records, sort descending by avg duration."""
        team_data: dict[str, list[float]] = {}
        for r in self._records:
            team_data.setdefault(r.team, []).append(r.duration_minutes)
        results: list[dict[str, Any]] = []
        for team, durations in team_data.items():
            results.append(
                {
                    "team": team,
                    "rollback_count": len(durations),
                    "avg_duration": round(sum(durations) / len(durations), 2),
                }
            )
        results.sort(key=lambda x: x["avg_duration"], reverse=True)
        return results

    def detect_rollback_trends(self) -> dict[str, Any]:
        """Split-half on frequency_threshold; delta threshold 5.0."""
        if len(self._patterns) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [p.frequency_threshold for p in self._patterns]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> RollbackTrackerReport:
        by_reason: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_reason[r.rollback_reason.value] = by_reason.get(r.rollback_reason.value, 0) + 1
            by_impact[r.rollback_impact.value] = by_impact.get(r.rollback_impact.value, 0) + 1
            by_status[r.rollback_status.value] = by_status.get(r.rollback_status.value, 0) + 1
        failed_count = sum(1 for r in self._records if r.rollback_status == RollbackStatus.FAILED)
        durations = [r.duration_minutes for r in self._records]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        rankings = self.rank_by_duration()
        frequent = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        failed_rate = round(failed_count / len(self._records) * 100, 2) if self._records else 0.0
        if failed_rate > self._max_rollback_rate_pct:
            recs.append(
                f"Failed rollback rate {failed_rate}% exceeds "
                f"threshold ({self._max_rollback_rate_pct}%)"
            )
        if failed_count > 0:
            recs.append(f"{failed_count} failed rollback(s) detected — review deployment pipeline")
        if not recs:
            recs.append("Rollback rates are acceptable")
        return RollbackTrackerReport(
            total_records=len(self._records),
            total_patterns=len(self._patterns),
            failed_rollbacks=failed_count,
            avg_duration_minutes=avg_duration,
            by_reason=by_reason,
            by_impact=by_impact,
            by_status=by_status,
            frequent_rollers=frequent,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("rollback_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        reason_dist: dict[str, int] = {}
        for r in self._records:
            key = r.rollback_reason.value
            reason_dist[key] = reason_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "max_rollback_rate_pct": self._max_rollback_rate_pct,
            "reason_distribution": reason_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_deployments": len({r.deployment_id for r in self._records}),
        }
