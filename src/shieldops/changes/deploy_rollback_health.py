"""Deploy Rollback Health Tracker — track rollback health, success rates, time to recover."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RollbackHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    SLOW = "slow"
    FAILED = "failed"
    UNTESTED = "untested"


class RollbackTrigger(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    POLICY_VIOLATION = "policy_violation"
    HEALTH_CHECK = "health_check"
    TIMEOUT = "timeout"


class RecoverySpeed(StrEnum):
    INSTANT = "instant"
    FAST = "fast"
    MODERATE = "moderate"
    SLOW = "slow"
    MANUAL_INTERVENTION = "manual_intervention"


# --- Models ---


class RollbackHealthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    rollback_health_status: RollbackHealthStatus = RollbackHealthStatus.UNTESTED
    rollback_trigger: RollbackTrigger = RollbackTrigger.AUTOMATED
    recovery_speed: RecoverySpeed = RecoverySpeed.MODERATE
    recovery_time_seconds: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RollbackMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    rollback_health_status: RollbackHealthStatus = RollbackHealthStatus.UNTESTED
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployRollbackHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    unhealthy_rollbacks: int = 0
    avg_recovery_time: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    top_slow_recoveries: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeployRollbackHealthTracker:
    """Track rollback health, success rates, and time to recover."""

    def __init__(
        self,
        max_records: int = 200000,
        max_recovery_time_seconds: float = 300.0,
    ) -> None:
        self._max_records = max_records
        self._max_recovery_time_seconds = max_recovery_time_seconds
        self._records: list[RollbackHealthRecord] = []
        self._metrics: list[RollbackMetric] = []
        logger.info(
            "deploy_rollback_health.initialized",
            max_records=max_records,
            max_recovery_time_seconds=max_recovery_time_seconds,
        )

    # -- record / get / list ------------------------------------------------

    def record_rollback(
        self,
        deployment_id: str,
        rollback_health_status: RollbackHealthStatus = RollbackHealthStatus.UNTESTED,
        rollback_trigger: RollbackTrigger = RollbackTrigger.AUTOMATED,
        recovery_speed: RecoverySpeed = RecoverySpeed.MODERATE,
        recovery_time_seconds: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RollbackHealthRecord:
        record = RollbackHealthRecord(
            deployment_id=deployment_id,
            rollback_health_status=rollback_health_status,
            rollback_trigger=rollback_trigger,
            recovery_speed=recovery_speed,
            recovery_time_seconds=recovery_time_seconds,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_rollback_health.rollback_recorded",
            record_id=record.id,
            deployment_id=deployment_id,
            rollback_health_status=rollback_health_status.value,
            rollback_trigger=rollback_trigger.value,
        )
        return record

    def get_rollback(self, record_id: str) -> RollbackHealthRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rollbacks(
        self,
        status: RollbackHealthStatus | None = None,
        trigger: RollbackTrigger | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RollbackHealthRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.rollback_health_status == status]
        if trigger is not None:
            results = [r for r in results if r.rollback_trigger == trigger]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        deployment_id: str,
        rollback_health_status: RollbackHealthStatus = RollbackHealthStatus.UNTESTED,
        metric_value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RollbackMetric:
        metric = RollbackMetric(
            deployment_id=deployment_id,
            rollback_health_status=rollback_health_status,
            metric_value=metric_value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "deploy_rollback_health.metric_added",
            deployment_id=deployment_id,
            rollback_health_status=rollback_health_status.value,
            metric_value=metric_value,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_rollback_health(self) -> dict[str, Any]:
        """Group by rollback_health_status; return count and avg recovery time."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.rollback_health_status.value
            status_data.setdefault(key, []).append(r.recovery_time_seconds)
        result: dict[str, Any] = {}
        for status, times in status_data.items():
            result[status] = {
                "count": len(times),
                "avg_recovery_time": round(sum(times) / len(times), 2),
            }
        return result

    def identify_unhealthy_rollbacks(self) -> list[dict[str, Any]]:
        """Return records where status is FAILED or DEGRADED."""
        unhealthy = {RollbackHealthStatus.FAILED, RollbackHealthStatus.DEGRADED}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.rollback_health_status in unhealthy:
                results.append(
                    {
                        "record_id": r.id,
                        "deployment_id": r.deployment_id,
                        "rollback_health_status": r.rollback_health_status.value,
                        "rollback_trigger": r.rollback_trigger.value,
                        "recovery_time_seconds": r.recovery_time_seconds,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_recovery_time(self) -> list[dict[str, Any]]:
        """Group by service, avg recovery time, sort descending."""
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service, []).append(r.recovery_time_seconds)
        results: list[dict[str, Any]] = []
        for service, times in svc_times.items():
            results.append(
                {
                    "service": service,
                    "avg_recovery_time": round(sum(times) / len(times), 2),
                    "rollback_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_recovery_time"], reverse=True)
        return results

    def detect_health_trends(self) -> dict[str, Any]:
        """Split-half comparison on recovery_time_seconds; delta 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.recovery_time_seconds for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "degrading"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DeployRollbackHealthReport:
        by_status: dict[str, int] = {}
        by_trigger: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        for r in self._records:
            by_status[r.rollback_health_status.value] = (
                by_status.get(r.rollback_health_status.value, 0) + 1
            )
            by_trigger[r.rollback_trigger.value] = by_trigger.get(r.rollback_trigger.value, 0) + 1
            by_speed[r.recovery_speed.value] = by_speed.get(r.recovery_speed.value, 0) + 1
        unhealthy_statuses = {RollbackHealthStatus.FAILED, RollbackHealthStatus.DEGRADED}
        unhealthy_rollbacks = sum(
            1 for r in self._records if r.rollback_health_status in unhealthy_statuses
        )
        avg_recovery_time = (
            round(
                sum(r.recovery_time_seconds for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        rankings = self.rank_by_recovery_time()
        top_slow_recoveries = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if unhealthy_rollbacks > 0:
            recs.append(
                f"{unhealthy_rollbacks} unhealthy rollback(s) detected — review deployment health"
            )
        slow_count = sum(
            1 for r in self._records if r.recovery_time_seconds > self._max_recovery_time_seconds
        )
        if slow_count > 0:
            recs.append(
                f"{slow_count} rollback(s) exceeded recovery time threshold"
                f" ({self._max_recovery_time_seconds}s)"
            )
        if not recs:
            recs.append("Rollback health levels are healthy")
        return DeployRollbackHealthReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            unhealthy_rollbacks=unhealthy_rollbacks,
            avg_recovery_time=avg_recovery_time,
            by_status=by_status,
            by_trigger=by_trigger,
            by_speed=by_speed,
            top_slow_recoveries=top_slow_recoveries,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("deploy_rollback_health.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.rollback_health_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_recovery_time_seconds": self._max_recovery_time_seconds,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
