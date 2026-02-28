"""Capacity Anomaly Detector — detect anomalous capacity patterns across resources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyType(StrEnum):
    SPIKE = "spike"
    DROP = "drop"
    TREND_SHIFT = "trend_shift"
    SEASONAL_DEVIATION = "seasonal_deviation"
    FLATLINE = "flatline"


class AnomalySeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class ResourceType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    CONNECTIONS = "connections"


# --- Models ---


class AnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    severity: AnomalySeverity = AnomalySeverity.MODERATE
    resource: ResourceType = ResourceType.CPU
    confidence_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AnomalyPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_name: str = ""
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    severity: AnomalySeverity = AnomalySeverity.MODERATE
    threshold_value: float = 0.0
    cooldown_minutes: int = 30
    created_at: float = Field(default_factory=time.time)


class CapacityAnomalyReport(BaseModel):
    total_anomalies: int = 0
    total_patterns: int = 0
    high_confidence_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityAnomalyDetector:
    """Detect anomalous capacity patterns across resources."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[AnomalyRecord] = []
        self._patterns: list[AnomalyPattern] = []
        logger.info(
            "capacity_anomaly.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_anomaly(
        self,
        service_name: str,
        anomaly_type: AnomalyType = AnomalyType.SPIKE,
        severity: AnomalySeverity = AnomalySeverity.MODERATE,
        resource: ResourceType = ResourceType.CPU,
        confidence_pct: float = 0.0,
        details: str = "",
    ) -> AnomalyRecord:
        record = AnomalyRecord(
            service_name=service_name,
            anomaly_type=anomaly_type,
            severity=severity,
            resource=resource,
            confidence_pct=confidence_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_anomaly.anomaly_recorded",
            record_id=record.id,
            service_name=service_name,
            anomaly_type=anomaly_type.value,
            severity=severity.value,
        )
        return record

    def get_anomaly(self, record_id: str) -> AnomalyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_anomalies(
        self,
        service_name: str | None = None,
        anomaly_type: AnomalyType | None = None,
        limit: int = 50,
    ) -> list[AnomalyRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if anomaly_type is not None:
            results = [r for r in results if r.anomaly_type == anomaly_type]
        return results[-limit:]

    def add_pattern(
        self,
        pattern_name: str,
        anomaly_type: AnomalyType = AnomalyType.SPIKE,
        severity: AnomalySeverity = AnomalySeverity.MODERATE,
        threshold_value: float = 0.0,
        cooldown_minutes: int = 30,
    ) -> AnomalyPattern:
        pattern = AnomalyPattern(
            pattern_name=pattern_name,
            anomaly_type=anomaly_type,
            severity=severity,
            threshold_value=threshold_value,
            cooldown_minutes=cooldown_minutes,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "capacity_anomaly.pattern_added",
            pattern_name=pattern_name,
            anomaly_type=anomaly_type.value,
            severity=severity.value,
        )
        return pattern

    # -- domain operations -----------------------------------------------

    def analyze_anomaly_patterns(self, service_name: str) -> dict[str, Any]:
        """Analyze anomaly patterns for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_confidence = round(sum(r.confidence_pct for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "avg_confidence": avg_confidence,
            "record_count": len(records),
            "meets_threshold": avg_confidence >= self._min_confidence_pct,
        }

    def identify_critical_anomalies(self) -> list[dict[str, Any]]:
        """Find services with >1 CRITICAL/HIGH anomaly."""
        crit_counts: dict[str, int] = {}
        for r in self._records:
            if r.severity in (AnomalySeverity.CRITICAL, AnomalySeverity.HIGH):
                crit_counts[r.service_name] = crit_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in crit_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "critical_count": count,
                    }
                )
        results.sort(key=lambda x: x["critical_count"], reverse=True)
        return results

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Rank services by average confidence_pct descending."""
        svc_confidence: dict[str, list[float]] = {}
        for r in self._records:
            svc_confidence.setdefault(r.service_name, []).append(r.confidence_pct)
        results: list[dict[str, Any]] = []
        for svc, confidences in svc_confidence.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_confidence_pct": round(sum(confidences) / len(confidences), 2),
                }
            )
        results.sort(key=lambda x: x["avg_confidence_pct"], reverse=True)
        return results

    def detect_recurring_anomalies(self) -> list[dict[str, Any]]:
        """Detect services with >3 records for recurrence analysis."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "record_count": count,
                        "recurrence_detected": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CapacityAnomalyReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.anomaly_type.value] = by_type.get(r.anomaly_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        high_conf_count = sum(
            1 for r in self._records if r.confidence_pct >= self._min_confidence_pct
        )
        high_conf_rate = (
            round(high_conf_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        critical_count = sum(1 for r in self._records if r.severity == AnomalySeverity.CRITICAL)
        critical_svcs = len(self.identify_critical_anomalies())
        recs: list[str] = []
        if self._records and high_conf_rate < self._min_confidence_pct:
            recs.append(
                f"High-confidence rate {high_conf_rate}% is below"
                f" {self._min_confidence_pct}% threshold"
            )
        if critical_svcs > 0:
            recs.append(f"{critical_svcs} service(s) with critical anomalies")
        if critical_count > 0:
            recs.append(f"{critical_count} critical anomaly record(s) detected")
        if not recs:
            recs.append("Capacity anomaly detection meets targets")
        return CapacityAnomalyReport(
            total_anomalies=len(self._records),
            total_patterns=len(self._patterns),
            high_confidence_rate_pct=high_conf_rate,
            by_type=by_type,
            by_severity=by_severity,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("capacity_anomaly.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.anomaly_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_anomalies": len(self._records),
            "total_patterns": len(self._patterns),
            "min_confidence_pct": self._min_confidence_pct,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
