"""Cost anomaly detector.

Z-score based anomaly detection on cloud cost data, with daily summaries
and alert tracking.
"""

from __future__ import annotations

import enum
import math
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class AnomalySeverity(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(enum.StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


# ── Models ───────────────────────────────────────────────────────────


class CostDataPoint(BaseModel):
    service: str
    amount: float
    currency: str = "USD"
    date: str = ""
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CostAnomaly(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    amount: float
    expected_amount: float = 0.0
    z_score: float = 0.0
    severity: AnomalySeverity = AnomalySeverity.LOW
    status: AnomalyStatus = AnomalyStatus.OPEN
    detected_at: float = Field(default_factory=time.time)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnomalyAlert(BaseModel):
    anomaly_id: str
    service: str
    severity: AnomalySeverity
    message: str
    created_at: float = Field(default_factory=time.time)


# ── Detector ─────────────────────────────────────────────────────────


class CostAnomalyDetector:
    """Detect cost anomalies using Z-score analysis.

    Parameters
    ----------
    z_threshold:
        Z-score threshold for flagging anomalies.
    lookback_days:
        Number of historical days for baseline computation.
    """

    def __init__(
        self,
        z_threshold: float = 2.5,
        lookback_days: int = 30,
    ) -> None:
        self._data: list[CostDataPoint] = []
        self._anomalies: dict[str, CostAnomaly] = {}
        self._z_threshold = z_threshold
        self._lookback_seconds = lookback_days * 86400

    def ingest(
        self,
        service: str,
        amount: float,
        currency: str = "USD",
        date: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CostDataPoint:
        point = CostDataPoint(
            service=service,
            amount=amount,
            currency=currency,
            date=date,
            metadata=metadata or {},
        )
        self._data.append(point)
        return point

    def detect_anomalies(
        self,
        service: str | None = None,
    ) -> list[CostAnomaly]:
        now = time.time()
        cutoff = now - self._lookback_seconds
        services = set()
        if service:
            services.add(service)
        else:
            services = {d.service for d in self._data}

        new_anomalies: list[CostAnomaly] = []
        for svc in services:
            points = [d for d in self._data if d.service == svc and d.timestamp >= cutoff]
            if len(points) < 3:
                continue
            amounts = [p.amount for p in points]
            mean = sum(amounts) / len(amounts)
            variance = sum((a - mean) ** 2 for a in amounts) / len(amounts)
            std = math.sqrt(variance) if variance > 0 else 0.0
            if std == 0:
                continue

            latest = points[-1]
            z = (latest.amount - mean) / std
            if abs(z) >= self._z_threshold:
                severity = self._classify_severity(abs(z))
                anomaly = CostAnomaly(
                    service=svc,
                    amount=latest.amount,
                    expected_amount=round(mean, 2),
                    z_score=round(z, 4),
                    severity=severity,
                    description=(
                        f"Cost for {svc} is {latest.amount:.2f} "
                        f"(expected ~{mean:.2f}, z-score={z:.2f})"
                    ),
                )
                self._anomalies[anomaly.id] = anomaly
                new_anomalies.append(anomaly)
                logger.info(
                    "cost_anomaly_detected",
                    service=svc,
                    z_score=z,
                    severity=severity,
                )
        return new_anomalies

    def _classify_severity(self, z: float) -> AnomalySeverity:
        if z >= 4.0:
            return AnomalySeverity.CRITICAL
        if z >= 3.5:
            return AnomalySeverity.HIGH
        if z >= 3.0:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def get_anomaly(self, anomaly_id: str) -> CostAnomaly | None:
        return self._anomalies.get(anomaly_id)

    def update_status(
        self,
        anomaly_id: str,
        status: AnomalyStatus,
    ) -> CostAnomaly | None:
        anomaly = self._anomalies.get(anomaly_id)
        if anomaly is None:
            return None
        anomaly.status = status
        logger.info("cost_anomaly_status_updated", anomaly_id=anomaly_id, status=status)
        return anomaly

    def list_anomalies(
        self,
        status: AnomalyStatus | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[CostAnomaly]:
        anomalies = sorted(
            self._anomalies.values(),
            key=lambda a: a.detected_at,
            reverse=True,
        )
        if status:
            anomalies = [a for a in anomalies if a.status == status]
        if service:
            anomalies = [a for a in anomalies if a.service == service]
        return anomalies[:limit]

    def get_daily_summary(self) -> dict[str, Any]:
        now = time.time()
        day_ago = now - 86400
        today_data = [d for d in self._data if d.timestamp >= day_ago]
        by_service: dict[str, float] = {}
        for d in today_data:
            by_service[d.service] = by_service.get(d.service, 0.0) + d.amount
        return {
            "period": "last_24h",
            "total_cost": round(sum(by_service.values()), 2),
            "by_service": {k: round(v, 2) for k, v in by_service.items()},
            "data_points": len(today_data),
        }

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for a in self._anomalies.values():
            by_status[a.status.value] = by_status.get(a.status.value, 0) + 1
            by_severity[a.severity.value] = by_severity.get(a.severity.value, 0) + 1
        return {
            "total_data_points": len(self._data),
            "total_anomalies": len(self._anomalies),
            "by_status": by_status,
            "by_severity": by_severity,
        }
