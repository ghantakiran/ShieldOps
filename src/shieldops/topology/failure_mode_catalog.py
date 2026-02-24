"""Failure Mode Catalog — catalog failure modes with detection and mitigation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FailureSeverity(StrEnum):
    COSMETIC = "cosmetic"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    CATASTROPHIC = "catastrophic"


class DetectionMethod(StrEnum):
    AUTOMATED_ALERT = "automated_alert"
    MANUAL_CHECK = "manual_check"
    SYNTHETIC_PROBE = "synthetic_probe"
    LOG_PATTERN = "log_pattern"
    METRIC_THRESHOLD = "metric_threshold"


class MitigationStrategy(StrEnum):
    RETRY = "retry"
    CIRCUIT_BREAK = "circuit_break"
    FAILOVER = "failover"
    GRACEFUL_DEGRADE = "graceful_degrade"
    MANUAL_INTERVENTION = "manual_intervention"


# --- Models ---


class FailureMode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    name: str = ""
    severity: FailureSeverity = FailureSeverity.MINOR
    detection_method: DetectionMethod = DetectionMethod.AUTOMATED_ALERT
    mitigation_strategy: MitigationStrategy = MitigationStrategy.RETRY
    description: str = ""
    is_mitigated: bool = False
    occurrences_count: int = 0
    last_occurrence_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class FailureOccurrence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failure_mode_id: str = ""
    occurred_at: float = Field(default_factory=time.time)
    detected_at: float = 0.0
    resolved_at: float = 0.0
    notes: str = ""


class FailureModeCatalogReport(BaseModel):
    total_modes: int = 0
    total_occurrences: int = 0
    unmitigated_count: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_detection: dict[str, int] = Field(default_factory=dict)
    avg_mtbf_hours: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class FailureModeCatalog:
    """Catalog known failure modes per service with detection rules and mitigation strategies."""

    def __init__(
        self,
        max_modes: int = 100000,
        mtbf_window_days: int = 365,
    ) -> None:
        self._max_modes = max_modes
        self._mtbf_window_days = mtbf_window_days
        self._modes: list[FailureMode] = []
        self._occurrences: list[FailureOccurrence] = []
        logger.info(
            "failure_mode_catalog.initialized",
            max_modes=max_modes,
            mtbf_window_days=mtbf_window_days,
        )

    def register_failure_mode(
        self,
        service_name: str,
        name: str,
        severity: FailureSeverity = FailureSeverity.MINOR,
        detection_method: DetectionMethod = DetectionMethod.AUTOMATED_ALERT,
        mitigation_strategy: MitigationStrategy = MitigationStrategy.RETRY,
        description: str = "",
        is_mitigated: bool = False,
    ) -> FailureMode:
        """Register a new failure mode in the catalog."""
        mode = FailureMode(
            service_name=service_name,
            name=name,
            severity=severity,
            detection_method=detection_method,
            mitigation_strategy=mitigation_strategy,
            description=description,
            is_mitigated=is_mitigated,
        )
        self._modes.append(mode)
        if len(self._modes) > self._max_modes:
            self._modes = self._modes[-self._max_modes :]
        logger.info(
            "failure_mode_catalog.mode_registered",
            mode_id=mode.id,
            service_name=service_name,
            name=name,
            severity=severity,
        )
        return mode

    def get_failure_mode(self, mode_id: str) -> FailureMode | None:
        """Retrieve a single failure mode by ID."""
        for m in self._modes:
            if m.id == mode_id:
                return m
        return None

    def list_failure_modes(
        self,
        severity: FailureSeverity | None = None,
        service_name: str | None = None,
        detection_method: DetectionMethod | None = None,
        limit: int = 100,
    ) -> list[FailureMode]:
        """List failure modes with optional filtering."""
        results = list(self._modes)
        if severity is not None:
            results = [m for m in results if m.severity == severity]
        if service_name is not None:
            results = [m for m in results if m.service_name == service_name]
        if detection_method is not None:
            results = [m for m in results if m.detection_method == detection_method]
        return results[-limit:]

    def record_occurrence(
        self,
        failure_mode_id: str,
        detected_at: float = 0.0,
        resolved_at: float = 0.0,
        notes: str = "",
    ) -> FailureOccurrence | None:
        """Record an occurrence of a failure mode. Returns None if mode not found."""
        mode = self.get_failure_mode(failure_mode_id)
        if mode is None:
            return None
        occurrence = FailureOccurrence(
            failure_mode_id=failure_mode_id,
            detected_at=detected_at,
            resolved_at=resolved_at,
            notes=notes,
        )
        self._occurrences.append(occurrence)
        mode.occurrences_count += 1
        mode.last_occurrence_at = occurrence.occurred_at
        logger.info(
            "failure_mode_catalog.occurrence_recorded",
            occurrence_id=occurrence.id,
            failure_mode_id=failure_mode_id,
            occurrences_count=mode.occurrences_count,
        )
        return occurrence

    def calculate_mtbf(self, failure_mode_id: str) -> dict[str, Any]:
        """Calculate mean time between failures for a failure mode."""
        mode_occurrences = [o for o in self._occurrences if o.failure_mode_id == failure_mode_id]
        occurrence_count = len(mode_occurrences)

        if occurrence_count < 2:
            return {
                "failure_mode_id": failure_mode_id,
                "occurrence_count": occurrence_count,
                "mtbf_hours": 0,
            }

        # Sort by occurred_at
        sorted_occ = sorted(mode_occurrences, key=lambda o: o.occurred_at)
        total_gap = 0.0
        for i in range(1, len(sorted_occ)):
            total_gap += sorted_occ[i].occurred_at - sorted_occ[i - 1].occurred_at

        mtbf_seconds = total_gap / (len(sorted_occ) - 1)
        mtbf_hours = round(mtbf_seconds / 3600, 2)

        logger.info(
            "failure_mode_catalog.mtbf_calculated",
            failure_mode_id=failure_mode_id,
            occurrence_count=occurrence_count,
            mtbf_hours=mtbf_hours,
        )
        return {
            "failure_mode_id": failure_mode_id,
            "occurrence_count": occurrence_count,
            "mtbf_hours": mtbf_hours,
        }

    def rank_by_frequency(self) -> list[FailureMode]:
        """Sort failure modes by occurrences_count descending."""
        return sorted(self._modes, key=lambda m: m.occurrences_count, reverse=True)

    def identify_unmitigated_modes(self) -> list[FailureMode]:
        """Return failure modes where is_mitigated is False."""
        return [m for m in self._modes if not m.is_mitigated]

    def analyze_detection_coverage(self) -> dict[str, Any]:
        """Analyze detection method coverage across failure modes."""
        methods: dict[str, int] = {}
        for m in self._modes:
            key = m.detection_method.value
            methods[key] = methods.get(key, 0) + 1

        total_modes = len(self._modes)
        automated_count = methods.get(DetectionMethod.AUTOMATED_ALERT.value, 0) + methods.get(
            DetectionMethod.METRIC_THRESHOLD.value, 0
        )
        automated_pct = round(automated_count / total_modes * 100, 2) if total_modes > 0 else 0.0

        logger.info(
            "failure_mode_catalog.detection_coverage_analyzed",
            total_modes=total_modes,
            automated_pct=automated_pct,
        )
        return {
            "methods": methods,
            "total_modes": total_modes,
            "automated_pct": automated_pct,
        }

    def generate_catalog_report(self) -> FailureModeCatalogReport:
        """Generate a comprehensive failure mode catalog report."""
        total_modes = len(self._modes)
        total_occurrences = len(self._occurrences)
        unmitigated_count = len(self.identify_unmitigated_modes())

        by_severity: dict[str, int] = {}
        by_detection: dict[str, int] = {}
        for m in self._modes:
            sev_key = m.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1
            det_key = m.detection_method.value
            by_detection[det_key] = by_detection.get(det_key, 0) + 1

        # Calculate average MTBF across all modes with >= 2 occurrences
        mtbf_values: list[float] = []
        for m in self._modes:
            mtbf = self.calculate_mtbf(m.id)
            if mtbf["mtbf_hours"] > 0:
                mtbf_values.append(mtbf["mtbf_hours"])
        avg_mtbf_hours = round(sum(mtbf_values) / len(mtbf_values), 2) if mtbf_values else 0.0

        recommendations: list[str] = []
        if unmitigated_count > 0:
            recommendations.append(
                f"{unmitigated_count} failure mode(s) are unmitigated — "
                f"define mitigation strategies"
            )
        detection_coverage = self.analyze_detection_coverage()
        if detection_coverage["automated_pct"] < 80.0 and total_modes > 0:
            recommendations.append(
                f"Only {detection_coverage['automated_pct']}% automated detection — "
                f"increase automated monitoring coverage"
            )
        critical_count = by_severity.get(FailureSeverity.CRITICAL.value, 0) + by_severity.get(
            FailureSeverity.CATASTROPHIC.value, 0
        )
        if critical_count > 0:
            recommendations.append(
                f"{critical_count} critical/catastrophic failure mode(s) — "
                f"ensure comprehensive mitigation and runbooks"
            )

        report = FailureModeCatalogReport(
            total_modes=total_modes,
            total_occurrences=total_occurrences,
            unmitigated_count=unmitigated_count,
            by_severity=by_severity,
            by_detection=by_detection,
            avg_mtbf_hours=avg_mtbf_hours,
            recommendations=recommendations,
        )
        logger.info(
            "failure_mode_catalog.report_generated",
            total_modes=total_modes,
            total_occurrences=total_occurrences,
            unmitigated_count=unmitigated_count,
            avg_mtbf_hours=avg_mtbf_hours,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored failure modes and occurrences."""
        self._modes.clear()
        self._occurrences.clear()
        logger.info("failure_mode_catalog.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored failure modes."""
        severities: dict[str, int] = {}
        detections: dict[str, int] = {}
        mitigations: dict[str, int] = {}
        services: set[str] = set()
        for m in self._modes:
            severities[m.severity.value] = severities.get(m.severity.value, 0) + 1
            detections[m.detection_method.value] = detections.get(m.detection_method.value, 0) + 1
            mitigations[m.mitigation_strategy.value] = (
                mitigations.get(m.mitigation_strategy.value, 0) + 1
            )
            if m.service_name:
                services.add(m.service_name)
        return {
            "total_modes": len(self._modes),
            "total_occurrences": len(self._occurrences),
            "unique_services": len(services),
            "severity_distribution": severities,
            "detection_distribution": detections,
            "mitigation_distribution": mitigations,
        }
