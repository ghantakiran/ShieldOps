"""Alert Storm Correlator — detect real-time alert cascades and find root trigger."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StormSeverity(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"
    CATASTROPHIC = "catastrophic"


class CorrelationMethod(StrEnum):
    TEMPORAL = "temporal"
    TOPOLOGICAL = "topological"
    CAUSAL = "causal"
    SYMPTOM_BASED = "symptom_based"
    HYBRID = "hybrid"


class StormPhase(StrEnum):
    BUILDING = "building"
    PEAK = "peak"
    SUBSIDING = "subsiding"
    RESOLVED = "resolved"
    RECURRING = "recurring"


# --- Models ---


class StormAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    service: str = ""
    severity: str = ""
    timestamp: float = Field(default_factory=time.time)
    is_root_cause: bool = False


class AlertStorm(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    storm_name: str = ""
    severity: StormSeverity = StormSeverity.MINOR
    phase: StormPhase = StormPhase.BUILDING
    method: CorrelationMethod = CorrelationMethod.TEMPORAL
    alerts: list[StormAlert] = Field(default_factory=list)
    root_cause_alert_id: str = ""
    affected_services: list[str] = Field(default_factory=list)
    started_at: float = Field(default_factory=time.time)
    resolved_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class StormReport(BaseModel):
    total_storms: int = 0
    active_storms: int = 0
    avg_alerts_per_storm: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    frequent_root_causes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertStormCorrelator:
    """Detect real-time alert cascades and find root trigger."""

    def __init__(
        self,
        max_records: int = 200000,
        storm_window_seconds: float = 300.0,
    ) -> None:
        self._max_records = max_records
        self._storm_window_seconds = storm_window_seconds
        self._records: list[AlertStorm] = []
        logger.info(
            "alert_storm_correlator.initialized",
            max_records=max_records,
            storm_window_seconds=storm_window_seconds,
        )

    # -- CRUD --

    def record_storm(
        self,
        storm_name: str,
        severity: StormSeverity = StormSeverity.MINOR,
        method: CorrelationMethod = CorrelationMethod.TEMPORAL,
    ) -> AlertStorm:
        storm = AlertStorm(
            storm_name=storm_name,
            severity=severity,
            method=method,
        )
        self._records.append(storm)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_storm_correlator.recorded",
            storm_id=storm.id,
            storm_name=storm_name,
            severity=severity.value,
        )
        return storm

    def get_storm(self, storm_id: str) -> AlertStorm | None:
        for s in self._records:
            if s.id == storm_id:
                return s
        return None

    def list_storms(
        self,
        severity: StormSeverity | None = None,
        phase: StormPhase | None = None,
        limit: int = 50,
    ) -> list[AlertStorm]:
        results = list(self._records)
        if severity is not None:
            results = [s for s in results if s.severity == severity]
        if phase is not None:
            results = [s for s in results if s.phase == phase]
        return results[-limit:]

    # -- Domain operations --

    def detect_storm(
        self,
        alerts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if len(alerts) < 5:
            return {"storm_detected": False, "reason": "fewer_than_5_alerts"}
        timestamps = [a.get("timestamp", 0.0) for a in alerts]
        if not timestamps:
            return {"storm_detected": False, "reason": "no_timestamps"}
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        window = max_ts - min_ts
        if window > self._storm_window_seconds:
            return {
                "storm_detected": False,
                "reason": "alerts_outside_window",
                "window_seconds": window,
            }
        # Storm detected — create it
        storm_alerts: list[StormAlert] = []
        services: set[str] = set()
        for a in alerts:
            alert = StormAlert(
                alert_name=a.get("alert_name", ""),
                service=a.get("service", ""),
                severity=a.get("severity", "warning"),
                timestamp=a.get("timestamp", time.time()),
            )
            storm_alerts.append(alert)
            if alert.service:
                services.add(alert.service)
        severity = self._classify_storm_severity(len(storm_alerts))
        storm = AlertStorm(
            storm_name=f"auto_detected_{int(time.time())}",
            severity=severity,
            method=CorrelationMethod.TEMPORAL,
            alerts=storm_alerts,
            affected_services=sorted(services),
            started_at=min_ts,
        )
        # Mark earliest alert as root cause
        storm_alerts.sort(key=lambda a: a.timestamp)
        storm_alerts[0].is_root_cause = True
        storm.root_cause_alert_id = storm_alerts[0].id
        self._records.append(storm)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_storm_correlator.storm_detected",
            storm_id=storm.id,
            alert_count=len(storm_alerts),
            severity=severity.value,
        )
        return {
            "storm_detected": True,
            "storm_id": storm.id,
            "alert_count": len(storm_alerts),
            "severity": severity.value,
            "affected_services": sorted(services),
            "root_cause_alert_id": storm.root_cause_alert_id,
        }

    def add_alert_to_storm(
        self,
        storm_id: str,
        alert_name: str,
        service: str,
        severity: str = "warning",
    ) -> dict[str, Any]:
        storm = self.get_storm(storm_id)
        if storm is None:
            return {"error": "storm_not_found"}
        alert = StormAlert(
            alert_name=alert_name,
            service=service,
            severity=severity,
        )
        storm.alerts.append(alert)
        if service and service not in storm.affected_services:
            storm.affected_services.append(service)
        # Re-evaluate storm severity based on new alert count
        storm.severity = self._classify_storm_severity(len(storm.alerts))
        logger.info(
            "alert_storm_correlator.alert_added",
            storm_id=storm_id,
            alert_id=alert.id,
            total_alerts=len(storm.alerts),
        )
        return {
            "storm_id": storm_id,
            "alert_id": alert.id,
            "total_alerts": len(storm.alerts),
            "severity": storm.severity.value,
        }

    def identify_root_cause(
        self,
        storm_id: str,
    ) -> dict[str, Any]:
        storm = self.get_storm(storm_id)
        if storm is None:
            return {"error": "storm_not_found"}
        if not storm.alerts:
            return {"storm_id": storm_id, "root_cause": None}
        # Root cause is the earliest alert
        earliest = min(storm.alerts, key=lambda a: a.timestamp)
        # Reset previous root cause flags
        for a in storm.alerts:
            a.is_root_cause = False
        earliest.is_root_cause = True
        storm.root_cause_alert_id = earliest.id
        logger.info(
            "alert_storm_correlator.root_cause_identified",
            storm_id=storm_id,
            root_cause_alert_id=earliest.id,
            alert_name=earliest.alert_name,
        )
        return {
            "storm_id": storm_id,
            "root_cause_alert_id": earliest.id,
            "alert_name": earliest.alert_name,
            "service": earliest.service,
            "timestamp": earliest.timestamp,
        }

    def calculate_storm_frequency(self) -> dict[str, Any]:
        if not self._records:
            return {"storms_per_day": 0.0, "storms_per_week": 0.0, "total": 0}
        timestamps = [s.started_at for s in self._records]
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        span_hours = (max_ts - min_ts) / 3600.0 if max_ts > min_ts else 24.0
        span_days = max(span_hours / 24.0, 1.0)
        total = len(self._records)
        per_day = round(total / span_days, 2)
        per_week = round(per_day * 7.0, 2)
        return {
            "storms_per_day": per_day,
            "storms_per_week": per_week,
            "total": total,
            "span_days": round(span_days, 2),
        }

    def update_storm_phase(
        self,
        storm_id: str,
        phase: StormPhase,
    ) -> dict[str, Any]:
        storm = self.get_storm(storm_id)
        if storm is None:
            return {"error": "storm_not_found"}
        old_phase = storm.phase.value
        storm.phase = phase
        if phase == StormPhase.RESOLVED:
            storm.resolved_at = time.time()
        logger.info(
            "alert_storm_correlator.phase_updated",
            storm_id=storm_id,
            old_phase=old_phase,
            new_phase=phase.value,
        )
        return {
            "storm_id": storm_id,
            "old_phase": old_phase,
            "new_phase": phase.value,
        }

    # -- Report --

    def generate_storm_report(self) -> StormReport:
        by_severity: dict[str, int] = {}
        by_phase: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for s in self._records:
            by_severity[s.severity.value] = by_severity.get(s.severity.value, 0) + 1
            by_phase[s.phase.value] = by_phase.get(s.phase.value, 0) + 1
            by_method[s.method.value] = by_method.get(s.method.value, 0) + 1
        total = len(self._records)
        active = sum(
            1
            for s in self._records
            if s.phase in (StormPhase.BUILDING, StormPhase.PEAK, StormPhase.RECURRING)
        )
        avg_alerts = round(sum(len(s.alerts) for s in self._records) / total, 2) if total else 0.0
        # Find frequent root causes by alert_name
        root_names: dict[str, int] = {}
        for s in self._records:
            for a in s.alerts:
                if a.is_root_cause and a.alert_name:
                    root_names[a.alert_name] = root_names.get(a.alert_name, 0) + 1
        frequent = sorted(root_names.items(), key=lambda x: x[1], reverse=True)
        frequent_names = [name for name, _ in frequent[:10]]
        recs: list[str] = []
        if active > 0:
            recs.append(f"{active} active storm(s) require attention")
        catastrophic = by_severity.get(StormSeverity.CATASTROPHIC.value, 0)
        if catastrophic > 0:
            recs.append(
                f"{catastrophic} catastrophic storm(s) detected — review cascading failures"
            )
        if frequent_names:
            recs.append(f"Top recurring root cause: {frequent_names[0]}")
        if not recs:
            recs.append("No active alert storms detected")
        return StormReport(
            total_storms=total,
            active_storms=active,
            avg_alerts_per_storm=avg_alerts,
            by_severity=by_severity,
            by_phase=by_phase,
            by_method=by_method,
            frequent_root_causes=frequent_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for s in self._records:
            key = s.severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        total_alerts = sum(len(s.alerts) for s in self._records)
        return {
            "total_storms": len(self._records),
            "total_alerts": total_alerts,
            "storm_window_seconds": self._storm_window_seconds,
            "severity_distribution": severity_dist,
        }

    # -- Internal helpers --

    def _classify_storm_severity(
        self,
        alert_count: int,
    ) -> StormSeverity:
        if alert_count >= 50:
            return StormSeverity.CATASTROPHIC
        if alert_count >= 20:
            return StormSeverity.SEVERE
        if alert_count >= 10:
            return StormSeverity.MAJOR
        if alert_count >= 5:
            return StormSeverity.MODERATE
        return StormSeverity.MINOR
