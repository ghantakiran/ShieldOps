"""Deployment Stability Tracker — track deployment stability, measurements, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StabilityPhase(StrEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    BASELINE = "baseline"


class StabilityStatus(StrEnum):
    STABLE = "stable"
    MINOR_ISSUES = "minor_issues"
    DEGRADED = "degraded"
    UNSTABLE = "unstable"
    ROLLBACK_NEEDED = "rollback_needed"


class StabilityMetric(StrEnum):
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    REQUEST_RATE = "request_rate"


# --- Models ---


class StabilityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    stability_phase: StabilityPhase = StabilityPhase.IMMEDIATE
    stability_status: StabilityStatus = StabilityStatus.STABLE
    stability_metric: StabilityMetric = StabilityMetric.ERROR_RATE
    stability_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class StabilityMeasurement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    stability_metric: StabilityMetric = StabilityMetric.ERROR_RATE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentStabilityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_measurements: int = 0
    unstable_deployments: int = 0
    avg_stability_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    top_unstable: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentStabilityTracker:
    """Track deployment stability, identify patterns, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_stability_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_stability_score = min_stability_score
        self._records: list[StabilityRecord] = []
        self._measurements: list[StabilityMeasurement] = []
        logger.info(
            "deploy_stability.initialized",
            max_records=max_records,
            min_stability_score=min_stability_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_stability(
        self,
        deployment_id: str,
        stability_phase: StabilityPhase = StabilityPhase.IMMEDIATE,
        stability_status: StabilityStatus = StabilityStatus.STABLE,
        stability_metric: StabilityMetric = StabilityMetric.ERROR_RATE,
        stability_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> StabilityRecord:
        record = StabilityRecord(
            deployment_id=deployment_id,
            stability_phase=stability_phase,
            stability_status=stability_status,
            stability_metric=stability_metric,
            stability_score=stability_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_stability.stability_recorded",
            record_id=record.id,
            deployment_id=deployment_id,
            stability_phase=stability_phase.value,
            stability_status=stability_status.value,
        )
        return record

    def get_stability(self, record_id: str) -> StabilityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_stabilities(
        self,
        phase: StabilityPhase | None = None,
        status: StabilityStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[StabilityRecord]:
        results = list(self._records)
        if phase is not None:
            results = [r for r in results if r.stability_phase == phase]
        if status is not None:
            results = [r for r in results if r.stability_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_measurement(
        self,
        deployment_id: str,
        stability_metric: StabilityMetric = StabilityMetric.ERROR_RATE,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> StabilityMeasurement:
        measurement = StabilityMeasurement(
            deployment_id=deployment_id,
            stability_metric=stability_metric,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._measurements.append(measurement)
        if len(self._measurements) > self._max_records:
            self._measurements = self._measurements[-self._max_records :]
        logger.info(
            "deploy_stability.measurement_added",
            deployment_id=deployment_id,
            stability_metric=stability_metric.value,
            value=value,
        )
        return measurement

    # -- domain operations --------------------------------------------------

    def analyze_stability_patterns(self) -> dict[str, Any]:
        """Group by phase; return count and avg stability score per phase."""
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.stability_phase.value
            phase_data.setdefault(key, []).append(r.stability_score)
        result: dict[str, Any] = {}
        for phase, scores in phase_data.items():
            result[phase] = {
                "count": len(scores),
                "avg_stability_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_unstable_deployments(self) -> list[dict[str, Any]]:
        """Return records where status == UNSTABLE or ROLLBACK_NEEDED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.stability_status in (
                StabilityStatus.UNSTABLE,
                StabilityStatus.ROLLBACK_NEEDED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "deployment_id": r.deployment_id,
                        "stability_phase": r.stability_phase.value,
                        "stability_status": r.stability_status.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_stability_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.stability_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(scores),
                    "avg_stability_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_stability_score"], reverse=True)
        return results

    def detect_stability_trends(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._measurements) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [m.value for m in self._measurements]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
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

    def generate_report(self) -> DeploymentStabilityReport:
        by_phase: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        for r in self._records:
            by_phase[r.stability_phase.value] = by_phase.get(r.stability_phase.value, 0) + 1
            by_status[r.stability_status.value] = by_status.get(r.stability_status.value, 0) + 1
            by_metric[r.stability_metric.value] = by_metric.get(r.stability_metric.value, 0) + 1
        unstable_count = sum(
            1
            for r in self._records
            if r.stability_status in (StabilityStatus.UNSTABLE, StabilityStatus.ROLLBACK_NEEDED)
        )
        scores = [r.stability_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_stability_score()
        top_unstable = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        below_threshold = sum(
            1 for r in self._records if r.stability_score < self._min_stability_score
        )
        below_rate = round(below_threshold / len(self._records) * 100, 2) if self._records else 0.0
        if below_rate > 20.0:
            recs.append(
                f"Low stability rate {below_rate}% exceeds threshold ({self._min_stability_score})"
            )
        if unstable_count > 0:
            recs.append(f"{unstable_count} unstable deployment(s) detected — review stability")
        if not recs:
            recs.append("Deployment stability is acceptable")
        return DeploymentStabilityReport(
            total_records=len(self._records),
            total_measurements=len(self._measurements),
            unstable_deployments=unstable_count,
            avg_stability_score=avg_score,
            by_phase=by_phase,
            by_status=by_status,
            by_metric=by_metric,
            top_unstable=top_unstable,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._measurements.clear()
        logger.info("deploy_stability.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.stability_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_measurements": len(self._measurements),
            "min_stability_score": self._min_stability_score,
            "phase_distribution": phase_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_deployments": len({r.deployment_id for r in self._records}),
        }
