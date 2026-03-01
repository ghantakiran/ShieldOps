"""Change Velocity Tracker — track change velocity per team/service, detect acceleration."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VelocityTrend(StrEnum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECELERATING = "decelerating"
    STALLED = "stalled"
    VOLATILE = "volatile"


class ChangeScope(StrEnum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    HOTFIX = "hotfix"
    CONFIG = "config"


class VelocityRisk(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class VelocityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    period_id: str = ""
    velocity_trend: VelocityTrend = VelocityTrend.STABLE
    change_scope: ChangeScope = ChangeScope.PATCH
    velocity_risk: VelocityRisk = VelocityRisk.NONE
    changes_per_day: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VelocityMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    period_id: str = ""
    velocity_trend: VelocityTrend = VelocityTrend.STABLE
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeVelocityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    high_velocity_count: int = 0
    avg_changes_per_day: float = 0.0
    by_trend: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_fast_movers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeVelocityTracker:
    """Track change velocity per team/service, detect acceleration/deceleration."""

    def __init__(
        self,
        max_records: int = 200000,
        max_changes_per_day: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._max_changes_per_day = max_changes_per_day
        self._records: list[VelocityRecord] = []
        self._metrics: list[VelocityMetric] = []
        logger.info(
            "change_velocity.initialized",
            max_records=max_records,
            max_changes_per_day=max_changes_per_day,
        )

    # -- record / get / list ------------------------------------------------

    def record_velocity(
        self,
        period_id: str,
        velocity_trend: VelocityTrend = VelocityTrend.STABLE,
        change_scope: ChangeScope = ChangeScope.PATCH,
        velocity_risk: VelocityRisk = VelocityRisk.NONE,
        changes_per_day: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> VelocityRecord:
        record = VelocityRecord(
            period_id=period_id,
            velocity_trend=velocity_trend,
            change_scope=change_scope,
            velocity_risk=velocity_risk,
            changes_per_day=changes_per_day,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_velocity.velocity_recorded",
            record_id=record.id,
            period_id=period_id,
            velocity_trend=velocity_trend.value,
            velocity_risk=velocity_risk.value,
        )
        return record

    def get_velocity(self, record_id: str) -> VelocityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_velocities(
        self,
        trend: VelocityTrend | None = None,
        scope: ChangeScope | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VelocityRecord]:
        results = list(self._records)
        if trend is not None:
            results = [r for r in results if r.velocity_trend == trend]
        if scope is not None:
            results = [r for r in results if r.change_scope == scope]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        period_id: str,
        velocity_trend: VelocityTrend = VelocityTrend.STABLE,
        metric_value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> VelocityMetric:
        metric = VelocityMetric(
            period_id=period_id,
            velocity_trend=velocity_trend,
            metric_value=metric_value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "change_velocity.metric_added",
            period_id=period_id,
            velocity_trend=velocity_trend.value,
            metric_value=metric_value,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_velocity_distribution(self) -> dict[str, Any]:
        """Group by velocity_trend; return count and avg changes_per_day."""
        trend_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.velocity_trend.value
            trend_data.setdefault(key, []).append(r.changes_per_day)
        result: dict[str, Any] = {}
        for trend, cpds in trend_data.items():
            result[trend] = {
                "count": len(cpds),
                "avg_changes_per_day": round(sum(cpds) / len(cpds), 2),
            }
        return result

    def identify_high_velocity_services(self) -> list[dict[str, Any]]:
        """Return records where changes_per_day exceeds max_changes_per_day."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.changes_per_day > self._max_changes_per_day:
                results.append(
                    {
                        "record_id": r.id,
                        "period_id": r.period_id,
                        "velocity_trend": r.velocity_trend.value,
                        "changes_per_day": r.changes_per_day,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_velocity(self) -> list[dict[str, Any]]:
        """Group by service, avg changes_per_day, sort descending."""
        svc_cpds: dict[str, list[float]] = {}
        for r in self._records:
            svc_cpds.setdefault(r.service, []).append(r.changes_per_day)
        results: list[dict[str, Any]] = []
        for svc, cpds in svc_cpds.items():
            results.append(
                {
                    "service": svc,
                    "avg_changes_per_day": round(sum(cpds) / len(cpds), 2),
                }
            )
        results.sort(key=lambda x: x["avg_changes_per_day"], reverse=True)
        return results

    def detect_velocity_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_value; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_value for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "accelerating"
        else:
            trend = "decelerating"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ChangeVelocityReport:
        by_trend: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_trend[r.velocity_trend.value] = by_trend.get(r.velocity_trend.value, 0) + 1
            by_scope[r.change_scope.value] = by_scope.get(r.change_scope.value, 0) + 1
            by_risk[r.velocity_risk.value] = by_risk.get(r.velocity_risk.value, 0) + 1
        high_velocity_count = sum(
            1 for r in self._records if r.changes_per_day > self._max_changes_per_day
        )
        cpds = [r.changes_per_day for r in self._records]
        avg_changes_per_day = round(sum(cpds) / len(cpds), 2) if cpds else 0.0
        rankings = self.rank_by_velocity()
        top_fast_movers = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if high_velocity_count > 0:
            recs.append(
                f"{high_velocity_count} service(s) exceed max velocity"
                f" ({self._max_changes_per_day} changes/day)"
            )
        stalled = sum(1 for r in self._records if r.velocity_trend == VelocityTrend.STALLED)
        if stalled > 0:
            recs.append(f"{stalled} stalled service(s) — investigate blockers")
        if not recs:
            recs.append("Change velocity levels are healthy")
        return ChangeVelocityReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            high_velocity_count=high_velocity_count,
            avg_changes_per_day=avg_changes_per_day,
            by_trend=by_trend,
            by_scope=by_scope,
            by_risk=by_risk,
            top_fast_movers=top_fast_movers,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("change_velocity.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        trend_dist: dict[str, int] = {}
        for r in self._records:
            key = r.velocity_trend.value
            trend_dist[key] = trend_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_changes_per_day": self._max_changes_per_day,
            "trend_distribution": trend_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
