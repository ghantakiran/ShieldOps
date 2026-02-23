"""Alert Noise Analyzer — signal-to-noise ratio, actionability scoring, alert fatigue tracking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AlertOutcome(StrEnum):
    ACTIONED = "actioned"
    IGNORED = "ignored"
    AUTO_RESOLVED = "auto_resolved"
    ESCALATED = "escalated"
    DUPLICATE = "duplicate"


class NoiseLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSource(StrEnum):
    PROMETHEUS = "prometheus"
    DATADOG = "datadog"
    CLOUDWATCH = "cloudwatch"
    CUSTOM = "custom"
    SYNTHETIC = "synthetic"


# --- Models ---


class AlertRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str
    source: AlertSource = AlertSource.CUSTOM
    service: str = ""
    outcome: AlertOutcome | None = None
    responder: str = ""
    fired_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None
    tags: list[str] = Field(default_factory=list)


class NoiseReport(BaseModel):
    alert_name: str
    total_fires: int = 0
    actioned_count: int = 0
    ignored_count: int = 0
    auto_resolved_count: int = 0
    duplicate_count: int = 0
    noise_level: NoiseLevel = NoiseLevel.LOW
    signal_to_noise: float = 0.0


# --- Analyzer ---


class AlertNoiseAnalyzer:
    """Analyzes alert signal-to-noise ratio, actionability, and fatigue."""

    def __init__(
        self,
        max_records: int = 100000,
        noise_threshold: float = 0.3,
    ) -> None:
        self._max_records = max_records
        self._noise_threshold = noise_threshold
        self._records: dict[str, AlertRecord] = {}
        logger.info(
            "alert_noise.initialized",
            max_records=max_records,
            noise_threshold=noise_threshold,
        )

    def record_alert(
        self,
        alert_name: str,
        source: AlertSource = AlertSource.CUSTOM,
        service: str = "",
        responder: str = "",
        **kw: Any,
    ) -> AlertRecord:
        """Record a new alert firing."""
        record = AlertRecord(
            alert_name=alert_name,
            source=source,
            service=service,
            responder=responder,
            **kw,
        )
        self._records[record.id] = record
        if len(self._records) > self._max_records:
            oldest = next(iter(self._records))
            del self._records[oldest]
        logger.info(
            "alert_noise.alert_recorded",
            record_id=record.id,
            alert_name=alert_name,
            source=source,
        )
        return record

    def resolve_alert(
        self,
        alert_id: str,
        outcome: AlertOutcome,
    ) -> AlertRecord | None:
        """Resolve an alert with an outcome."""
        record = self._records.get(alert_id)
        if record is None:
            return None
        record.outcome = outcome
        record.resolved_at = time.time()
        logger.info(
            "alert_noise.alert_resolved",
            record_id=alert_id,
            outcome=outcome,
        )
        return record

    def analyze_noise(self) -> list[NoiseReport]:
        """Analyze noise levels across all alert types."""
        by_name: dict[str, list[AlertRecord]] = {}
        for rec in self._records.values():
            by_name.setdefault(rec.alert_name, []).append(rec)

        reports: list[NoiseReport] = []
        for name, records in by_name.items():
            total = len(records)
            actioned = sum(1 for r in records if r.outcome == AlertOutcome.ACTIONED)
            ignored = sum(1 for r in records if r.outcome == AlertOutcome.IGNORED)
            auto_resolved = sum(1 for r in records if r.outcome == AlertOutcome.AUTO_RESOLVED)
            duplicate = sum(1 for r in records if r.outcome == AlertOutcome.DUPLICATE)
            signal = actioned + sum(1 for r in records if r.outcome == AlertOutcome.ESCALATED)
            stn = round(signal / total, 4) if total else 0.0
            if stn < 0.1:
                noise_level = NoiseLevel.CRITICAL
            elif stn < self._noise_threshold:
                noise_level = NoiseLevel.HIGH
            elif stn < 0.6:
                noise_level = NoiseLevel.MODERATE
            else:
                noise_level = NoiseLevel.LOW
            reports.append(
                NoiseReport(
                    alert_name=name,
                    total_fires=total,
                    actioned_count=actioned,
                    ignored_count=ignored,
                    auto_resolved_count=auto_resolved,
                    duplicate_count=duplicate,
                    noise_level=noise_level,
                    signal_to_noise=stn,
                )
            )
        return reports

    def get_signal_to_noise(self) -> float:
        """Get overall signal-to-noise ratio."""
        total = len(self._records)
        if total == 0:
            return 0.0
        signal = sum(
            1
            for r in self._records.values()
            if r.outcome in (AlertOutcome.ACTIONED, AlertOutcome.ESCALATED)
        )
        return round(signal / total, 4)

    def get_top_noisy_alerts(self, limit: int = 10) -> list[NoiseReport]:
        """Get the noisiest alerts sorted by noise level."""
        reports = self.analyze_noise()
        reports.sort(key=lambda r: r.signal_to_noise)
        return reports[:limit]

    def list_alerts(
        self,
        alert_name: str | None = None,
        source: AlertSource | None = None,
        outcome: AlertOutcome | None = None,
    ) -> list[AlertRecord]:
        """List alert records with optional filters."""
        results = list(self._records.values())
        if alert_name is not None:
            results = [r for r in results if r.alert_name == alert_name]
        if source is not None:
            results = [r for r in results if r.source == source]
        if outcome is not None:
            results = [r for r in results if r.outcome == outcome]
        return results

    def get_fatigue_score(self, responder: str) -> dict[str, Any]:
        """Calculate alert fatigue score for a responder."""
        responder_alerts = [r for r in self._records.values() if r.responder == responder]
        total = len(responder_alerts)
        if total == 0:
            return {"responder": responder, "total_alerts": 0, "fatigue_score": 0.0}
        ignored = sum(1 for r in responder_alerts if r.outcome == AlertOutcome.IGNORED)
        fatigue = round(ignored / total, 4) if total else 0.0
        return {
            "responder": responder,
            "total_alerts": total,
            "ignored_count": ignored,
            "fatigue_score": fatigue,
        }

    def clear_records(self) -> int:
        """Clear all alert records. Returns count cleared."""
        count = len(self._records)
        self._records.clear()
        logger.info("alert_noise.records_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        source_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        for r in self._records.values():
            source_counts[r.source] = source_counts.get(r.source, 0) + 1
            if r.outcome is not None:
                outcome_counts[r.outcome] = outcome_counts.get(r.outcome, 0) + 1
        return {
            "total_records": len(self._records),
            "signal_to_noise": self.get_signal_to_noise(),
            "source_distribution": source_counts,
            "outcome_distribution": outcome_counts,
        }
