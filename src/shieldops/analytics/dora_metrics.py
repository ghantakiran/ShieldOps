"""DORA metrics engine.

Tracks all four DORA metrics: deployment frequency, lead time for changes,
change failure rate, and mean time to recovery (MTTR).
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class DORALevel(enum.StrEnum):
    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DORAMetricType(enum.StrEnum):
    DEPLOYMENT_FREQUENCY = "deployment_frequency"
    LEAD_TIME = "lead_time"
    CHANGE_FAILURE_RATE = "change_failure_rate"
    MTTR = "mttr"


# -- Models --------------------------------------------------------------------


class DeploymentRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    environment: str = "production"
    commit_sha: str = ""
    lead_time_seconds: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FailureRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    deployment_id: str = ""
    description: str = ""
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecoveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    failure_id: str = ""
    recovery_time_seconds: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DORASnapshot(BaseModel):
    service: str
    period_start: float
    period_end: float
    deployment_frequency: float = 0.0
    lead_time_seconds: float = 0.0
    change_failure_rate: float = 0.0
    mttr_seconds: float = 0.0
    deployment_frequency_level: DORALevel = DORALevel.LOW
    lead_time_level: DORALevel = DORALevel.LOW
    change_failure_rate_level: DORALevel = DORALevel.LOW
    mttr_level: DORALevel = DORALevel.LOW
    overall_level: DORALevel = DORALevel.LOW
    total_deployments: int = 0
    total_failures: int = 0
    total_recoveries: int = 0
    computed_at: float = Field(default_factory=time.time)


# -- Engine --------------------------------------------------------------------


class DORAMetricsEngine:
    """Track and compute DORA metrics.

    Parameters
    ----------
    default_period_days:
        Default lookback period for metric computation.
    max_records:
        Maximum total records to store.
    """

    def __init__(
        self,
        default_period_days: int = 30,
        max_records: int = 50000,
    ) -> None:
        self._deployments: list[DeploymentRecord] = []
        self._failures: list[FailureRecord] = []
        self._recoveries: list[RecoveryRecord] = []
        self._default_period = default_period_days * 86400
        self._max_records = max_records

    def record_deployment(
        self,
        service: str,
        environment: str = "production",
        commit_sha: str = "",
        lead_time_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> DeploymentRecord:
        if len(self._deployments) >= self._max_records:
            self._deployments = self._deployments[-self._max_records // 2 :]
        record = DeploymentRecord(
            service=service,
            environment=environment,
            commit_sha=commit_sha,
            lead_time_seconds=lead_time_seconds,
            metadata=metadata or {},
        )
        self._deployments.append(record)
        logger.info("dora_deployment_recorded", service=service, deploy_id=record.id)
        return record

    def record_failure(
        self,
        service: str,
        deployment_id: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> FailureRecord:
        if len(self._failures) >= self._max_records:
            self._failures = self._failures[-self._max_records // 2 :]
        record = FailureRecord(
            service=service,
            deployment_id=deployment_id,
            description=description,
            metadata=metadata or {},
        )
        self._failures.append(record)
        logger.info("dora_failure_recorded", service=service, failure_id=record.id)
        return record

    def record_recovery(
        self,
        service: str,
        failure_id: str = "",
        recovery_time_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> RecoveryRecord:
        if len(self._recoveries) >= self._max_records:
            self._recoveries = self._recoveries[-self._max_records // 2 :]
        record = RecoveryRecord(
            service=service,
            failure_id=failure_id,
            recovery_time_seconds=recovery_time_seconds,
            metadata=metadata or {},
        )
        self._recoveries.append(record)
        logger.info("dora_recovery_recorded", service=service, recovery_id=record.id)
        return record

    def _classify_deployment_frequency(self, deploys_per_day: float) -> DORALevel:
        if deploys_per_day >= 1.0:
            return DORALevel.ELITE
        if deploys_per_day >= 1.0 / 7:
            return DORALevel.HIGH
        if deploys_per_day >= 1.0 / 30:
            return DORALevel.MEDIUM
        return DORALevel.LOW

    def _classify_lead_time(self, seconds: float) -> DORALevel:
        if seconds <= 86400:
            return DORALevel.ELITE
        if seconds <= 604800:
            return DORALevel.HIGH
        if seconds <= 2592000:
            return DORALevel.MEDIUM
        return DORALevel.LOW

    def _classify_change_failure_rate(self, rate: float) -> DORALevel:
        if rate <= 0.05:
            return DORALevel.ELITE
        if rate <= 0.10:
            return DORALevel.HIGH
        if rate <= 0.15:
            return DORALevel.MEDIUM
        return DORALevel.LOW

    def _classify_mttr(self, seconds: float) -> DORALevel:
        if seconds <= 3600:
            return DORALevel.ELITE
        if seconds <= 86400:
            return DORALevel.HIGH
        if seconds <= 604800:
            return DORALevel.MEDIUM
        return DORALevel.LOW

    def classify_level(self, metric_type: DORAMetricType, value: float) -> DORALevel:
        if metric_type == DORAMetricType.DEPLOYMENT_FREQUENCY:
            return self._classify_deployment_frequency(value)
        if metric_type == DORAMetricType.LEAD_TIME:
            return self._classify_lead_time(value)
        if metric_type == DORAMetricType.CHANGE_FAILURE_RATE:
            return self._classify_change_failure_rate(value)
        if metric_type == DORAMetricType.MTTR:
            return self._classify_mttr(value)
        return DORALevel.LOW

    def compute_snapshot(
        self,
        service: str,
        period_days: int | None = None,
    ) -> DORASnapshot:
        period = (period_days or (self._default_period // 86400)) * 86400
        now = time.time()
        start = now - period

        deploys = [d for d in self._deployments if d.service == service and d.timestamp >= start]
        failures = [f for f in self._failures if f.service == service and f.timestamp >= start]
        recoveries = [r for r in self._recoveries if r.service == service and r.timestamp >= start]

        days = period / 86400
        deploy_freq = len(deploys) / days if days > 0 else 0.0
        avg_lead_time = sum(d.lead_time_seconds for d in deploys) / len(deploys) if deploys else 0.0
        cfr = len(failures) / len(deploys) if deploys else 0.0
        avg_mttr = (
            sum(r.recovery_time_seconds for r in recoveries) / len(recoveries)
            if recoveries
            else 0.0
        )

        df_level = self._classify_deployment_frequency(deploy_freq)
        lt_level = self._classify_lead_time(avg_lead_time)
        cfr_level = self._classify_change_failure_rate(cfr)
        mttr_level = self._classify_mttr(avg_mttr)

        level_values = {
            DORALevel.ELITE: 4,
            DORALevel.HIGH: 3,
            DORALevel.MEDIUM: 2,
            DORALevel.LOW: 1,
        }
        avg_level_val = (
            level_values[df_level]
            + level_values[lt_level]
            + level_values[cfr_level]
            + level_values[mttr_level]
        ) / 4
        if avg_level_val >= 3.5:
            overall = DORALevel.ELITE
        elif avg_level_val >= 2.5:
            overall = DORALevel.HIGH
        elif avg_level_val >= 1.5:
            overall = DORALevel.MEDIUM
        else:
            overall = DORALevel.LOW

        return DORASnapshot(
            service=service,
            period_start=start,
            period_end=now,
            deployment_frequency=deploy_freq,
            lead_time_seconds=avg_lead_time,
            change_failure_rate=cfr,
            mttr_seconds=avg_mttr,
            deployment_frequency_level=df_level,
            lead_time_level=lt_level,
            change_failure_rate_level=cfr_level,
            mttr_level=mttr_level,
            overall_level=overall,
            total_deployments=len(deploys),
            total_failures=len(failures),
            total_recoveries=len(recoveries),
        )

    def get_trends(
        self,
        service: str,
        periods: int = 4,
        period_days: int | None = None,
    ) -> list[DORASnapshot]:
        pd = period_days or (self._default_period // 86400)
        snapshots: list[DORASnapshot] = []
        now = time.time()
        for i in range(periods):
            end = now - i * pd * 86400
            start = end - pd * 86400
            deploys = [
                d for d in self._deployments if d.service == service and start <= d.timestamp < end
            ]
            failures = [
                f for f in self._failures if f.service == service and start <= f.timestamp < end
            ]
            recoveries = [
                r for r in self._recoveries if r.service == service and start <= r.timestamp < end
            ]
            days = pd
            deploy_freq = len(deploys) / days if days > 0 else 0.0
            avg_lead = sum(d.lead_time_seconds for d in deploys) / len(deploys) if deploys else 0.0
            cfr = len(failures) / len(deploys) if deploys else 0.0
            avg_mttr = (
                sum(r.recovery_time_seconds for r in recoveries) / len(recoveries)
                if recoveries
                else 0.0
            )
            snap = DORASnapshot(
                service=service,
                period_start=start,
                period_end=end,
                deployment_frequency=deploy_freq,
                lead_time_seconds=avg_lead,
                change_failure_rate=cfr,
                mttr_seconds=avg_mttr,
                deployment_frequency_level=self._classify_deployment_frequency(deploy_freq),
                lead_time_level=self._classify_lead_time(avg_lead),
                change_failure_rate_level=self._classify_change_failure_rate(cfr),
                mttr_level=self._classify_mttr(avg_mttr),
                total_deployments=len(deploys),
                total_failures=len(failures),
                total_recoveries=len(recoveries),
            )
            snapshots.append(snap)
        return list(reversed(snapshots))

    def get_stats(self) -> dict[str, Any]:
        services = set()
        for d in self._deployments:
            services.add(d.service)
        for f in self._failures:
            services.add(f.service)
        return {
            "total_deployments": len(self._deployments),
            "total_failures": len(self._failures),
            "total_recoveries": len(self._recoveries),
            "tracked_services": len(services),
        }
