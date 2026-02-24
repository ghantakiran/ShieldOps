"""Log Anomaly Detector — statistical anomaly detection on log patterns."""

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
    VOLUME_SPIKE = "volume_spike"
    NEW_PATTERN = "new_pattern"
    ERROR_RATE_SURGE = "error_rate_surge"
    PATTERN_DISAPPEARANCE = "pattern_disappearance"
    FREQUENCY_SHIFT = "frequency_shift"


class AnomalySeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DetectionMethod(StrEnum):
    STATISTICAL = "statistical"
    PATTERN_MATCHING = "pattern_matching"
    FREQUENCY_ANALYSIS = "frequency_analysis"
    BASELINE_COMPARISON = "baseline_comparison"


# --- Models ---


class LogPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern: str = ""
    service: str = ""
    level: str = "info"
    sample_message: str = ""
    count: int = 0
    first_seen: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)


class LogAnomaly(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_type: AnomalyType = AnomalyType.VOLUME_SPIKE
    severity: AnomalySeverity = AnomalySeverity.INFO
    service: str = ""
    pattern: str = ""
    description: str = ""
    detection_method: DetectionMethod = DetectionMethod.STATISTICAL
    score: float = 0.0
    acknowledged: bool = False
    detected_at: float = Field(default_factory=time.time)


class AnomalySummary(BaseModel):
    total_anomalies: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    unacknowledged: int = 0


# --- Engine ---


class LogAnomalyDetector:
    """Statistical anomaly detection on log patterns, volume spikes, new pattern detection."""

    def __init__(
        self,
        max_patterns: int = 100000,
        sensitivity: float = 0.7,
    ) -> None:
        self._max_patterns = max_patterns
        self._sensitivity = sensitivity
        self._patterns: list[LogPattern] = []
        self._anomalies: list[LogAnomaly] = []
        self._baseline_rates: dict[str, float] = {}
        self._log_batches: list[dict[str, Any]] = []
        logger.info(
            "log_anomaly.initialized",
            max_patterns=max_patterns,
            sensitivity=sensitivity,
        )

    def register_pattern(
        self,
        pattern: str,
        service: str = "",
        level: str = "info",
        sample_message: str = "",
    ) -> LogPattern:
        lp = LogPattern(
            pattern=pattern,
            service=service,
            level=level,
            sample_message=sample_message,
        )
        self._patterns.append(lp)
        if len(self._patterns) > self._max_patterns:
            self._patterns = self._patterns[-self._max_patterns :]
        logger.info("log_anomaly.pattern_registered", pattern_id=lp.id, pattern=pattern)
        return lp

    def submit_log_batch(
        self,
        service: str,
        logs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        batch = {
            "service": service,
            "count": len(logs),
            "logs": logs,
            "submitted_at": time.time(),
        }
        self._log_batches.append(batch)
        # Update pattern counts
        for log in logs:
            msg = log.get("message", "")
            matched = False
            for p in self._patterns:
                if p.pattern in msg and (not p.service or p.service == service):
                    p.count += 1
                    p.last_seen = time.time()
                    matched = True
                    break
            if not matched and msg:
                # Register as new pattern
                lvl = log.get("level", "info")
                self.register_pattern(
                    pattern=msg[:100],
                    service=service,
                    level=lvl,
                )
        logger.info("log_anomaly.batch_submitted", service=service, count=len(logs))
        return {"service": service, "processed": len(logs)}

    def detect_anomalies(self, service: str | None = None) -> list[LogAnomaly]:
        detected: list[LogAnomaly] = []
        patterns = self._patterns
        if service:
            patterns = [p for p in patterns if p.service == service]

        # Check for volume spikes
        for p in patterns:
            baseline = self._baseline_rates.get(p.pattern, 0.0)
            if baseline > 0 and p.count > baseline * (2.0 - self._sensitivity):
                severity = (
                    AnomalySeverity.HIGH if p.count > baseline * 3 else AnomalySeverity.MEDIUM
                )
                anomaly = LogAnomaly(
                    anomaly_type=AnomalyType.VOLUME_SPIKE,
                    severity=severity,
                    service=p.service,
                    pattern=p.pattern,
                    description=f"Volume spike: {p.count} vs baseline {baseline}",
                    detection_method=DetectionMethod.BASELINE_COMPARISON,
                    score=min(1.0, p.count / baseline / 3) if baseline > 0 else 0.0,
                )
                detected.append(anomaly)
                self._anomalies.append(anomaly)

        # Check for error patterns
        error_patterns = [p for p in patterns if p.level in ("error", "critical")]
        if error_patterns:
            total_errors = sum(p.count for p in error_patterns)
            total_all = sum(p.count for p in patterns) or 1
            error_rate = total_errors / total_all
            if error_rate > self._sensitivity * 0.5:
                severity = AnomalySeverity.CRITICAL if error_rate > 0.5 else AnomalySeverity.HIGH
                anomaly = LogAnomaly(
                    anomaly_type=AnomalyType.ERROR_RATE_SURGE,
                    severity=severity,
                    service=service or "all",
                    pattern="error_rate",
                    description=f"Error rate surge: {error_rate:.1%}",
                    detection_method=DetectionMethod.STATISTICAL,
                    score=min(1.0, error_rate),
                )
                detected.append(anomaly)
                self._anomalies.append(anomaly)

        return detected

    def get_anomaly(self, anomaly_id: str) -> LogAnomaly | None:
        for a in self._anomalies:
            if a.id == anomaly_id:
                return a
        return None

    def list_anomalies(
        self,
        service: str | None = None,
        severity: AnomalySeverity | None = None,
        limit: int = 100,
    ) -> list[LogAnomaly]:
        results = list(self._anomalies)
        if service is not None:
            results = [a for a in results if a.service == service]
        if severity is not None:
            results = [a for a in results if a.severity == severity]
        return results[-limit:]

    def set_baseline(self, pattern: str, rate: float) -> dict[str, Any]:
        self._baseline_rates[pattern] = rate
        logger.info("log_anomaly.baseline_set", pattern=pattern, rate=rate)
        return {"pattern": pattern, "baseline_rate": rate}

    def get_pattern_stats(self, pattern_id: str) -> dict[str, Any] | None:
        for p in self._patterns:
            if p.id == pattern_id:
                return {
                    "id": p.id,
                    "pattern": p.pattern,
                    "service": p.service,
                    "count": p.count,
                    "level": p.level,
                }
        return None

    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        for a in self._anomalies:
            if a.id == anomaly_id:
                a.acknowledged = True
                return True
        return False

    def get_trending_patterns(self, limit: int = 10) -> list[dict[str, Any]]:
        sorted_patterns = sorted(self._patterns, key=lambda p: p.count, reverse=True)
        return [
            {
                "pattern": p.pattern,
                "service": p.service,
                "count": p.count,
                "level": p.level,
            }
            for p in sorted_patterns[:limit]
        ]

    def get_stats(self) -> dict[str, Any]:
        sev_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        unack = 0
        for a in self._anomalies:
            sev_counts[a.severity] = sev_counts.get(a.severity, 0) + 1
            type_counts[a.anomaly_type] = type_counts.get(a.anomaly_type, 0) + 1
            if not a.acknowledged:
                unack += 1
        return {
            "total_patterns": len(self._patterns),
            "total_anomalies": len(self._anomalies),
            "unacknowledged": unack,
            "severity_distribution": sev_counts,
            "type_distribution": type_counts,
            "baselines_configured": len(self._baseline_rates),
        }
