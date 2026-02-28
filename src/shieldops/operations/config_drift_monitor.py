"""Config Drift Monitor — detect and track configuration drift."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftType(StrEnum):
    PARAMETER_CHANGE = "parameter_change"
    VERSION_MISMATCH = "version_mismatch"
    MISSING_CONFIG = "missing_config"
    EXTRA_CONFIG = "extra_config"
    SCHEMA_VIOLATION = "schema_violation"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class DriftSource(StrEnum):
    MANUAL_CHANGE = "manual_change"
    AUTOMATION_BUG = "automation_bug"
    ENVIRONMENT_SYNC = "environment_sync"
    UPGRADE_SIDE_EFFECT = "upgrade_side_effect"
    UNKNOWN = "unknown"


# --- Models ---


class DriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    resource_id: str = ""
    drift_type: DriftType = DriftType.PARAMETER_CHANGE
    severity: DriftSeverity = DriftSeverity.MODERATE
    source: DriftSource = DriftSource.UNKNOWN
    expected_value: str = ""
    actual_value: str = ""
    environment: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftResolution(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    drift_id: str = ""
    resolved_by: str = ""
    resolution_method: str = ""
    resolution_time_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ConfigDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_resolutions: int = 0
    by_drift_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    unresolved_count: int = 0
    avg_resolution_time: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConfigDriftMonitor:
    """Detect and track configuration drift across environments."""

    def __init__(
        self,
        max_records: int = 200000,
        max_drift_count: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_drift_count = max_drift_count
        self._records: list[DriftRecord] = []
        self._resolutions: list[DriftResolution] = []
        logger.info(
            "config_drift_monitor.initialized",
            max_records=max_records,
            max_drift_count=max_drift_count,
        )

    # -- record / get / list -----------------------------------------

    def record_drift(
        self,
        resource_id: str,
        drift_type: DriftType = DriftType.PARAMETER_CHANGE,
        severity: DriftSeverity = DriftSeverity.MODERATE,
        source: DriftSource = DriftSource.UNKNOWN,
        expected_value: str = "",
        actual_value: str = "",
        environment: str = "",
        team: str = "",
    ) -> DriftRecord:
        record = DriftRecord(
            resource_id=resource_id,
            drift_type=drift_type,
            severity=severity,
            source=source,
            expected_value=expected_value,
            actual_value=actual_value,
            environment=environment,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "config_drift_monitor.recorded",
            record_id=record.id,
            resource_id=resource_id,
            drift_type=drift_type.value,
            severity=severity.value,
        )
        return record

    def get_drift(self, record_id: str) -> DriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
        self,
        drift_type: DriftType | None = None,
        severity: DriftSeverity | None = None,
        environment: str | None = None,
        limit: int = 50,
    ) -> list[DriftRecord]:
        results = list(self._records)
        if drift_type is not None:
            results = [r for r in results if r.drift_type == drift_type]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if environment is not None:
            results = [r for r in results if r.environment == environment]
        return results[-limit:]

    def add_resolution(
        self,
        drift_id: str,
        resolved_by: str,
        resolution_method: str,
        resolution_time_minutes: float,
    ) -> DriftResolution:
        resolution = DriftResolution(
            drift_id=drift_id,
            resolved_by=resolved_by,
            resolution_method=resolution_method,
            resolution_time_minutes=resolution_time_minutes,
        )
        self._resolutions.append(resolution)
        if len(self._resolutions) > self._max_records:
            self._resolutions = self._resolutions[-self._max_records :]
        logger.info(
            "config_drift_monitor.resolution_added",
            resolution_id=resolution.id,
            drift_id=drift_id,
            resolved_by=resolved_by,
        )
        return resolution

    # -- domain operations -------------------------------------------

    def analyze_drift_by_environment(
        self,
    ) -> dict[str, Any]:
        """Analyze drift grouped by environment."""
        env_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            env = r.environment or "unknown"
            if env not in env_data:
                env_data[env] = {
                    "total": 0,
                    "critical": 0,
                }
            env_data[env]["total"] += 1
            if r.severity in (
                DriftSeverity.CRITICAL,
                DriftSeverity.HIGH,
            ):
                env_data[env]["critical"] += 1
        breakdown: list[dict[str, Any]] = []
        for env, data in env_data.items():
            breakdown.append(
                {
                    "environment": env,
                    "total_drifts": data["total"],
                    "critical_count": data["critical"],
                }
            )
        breakdown.sort(
            key=lambda x: x["total_drifts"],
            reverse=True,
        )
        return {
            "total_environments": len(env_data),
            "breakdown": breakdown,
        }

    def identify_critical_drifts(
        self,
    ) -> list[dict[str, Any]]:
        """Find drifts with CRITICAL or HIGH severity."""
        critical = [
            r for r in self._records if r.severity in (DriftSeverity.CRITICAL, DriftSeverity.HIGH)
        ]
        return [
            {
                "record_id": r.id,
                "resource_id": r.resource_id,
                "drift_type": r.drift_type.value,
                "severity": r.severity.value,
                "environment": r.environment,
            }
            for r in critical
        ]

    def rank_by_severity(
        self,
    ) -> list[dict[str, Any]]:
        """Rank resources by drift severity."""
        sev_order = {
            DriftSeverity.CRITICAL: 5,
            DriftSeverity.HIGH: 4,
            DriftSeverity.MODERATE: 3,
            DriftSeverity.LOW: 2,
            DriftSeverity.INFORMATIONAL: 1,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "resource_id": r.resource_id,
                    "severity": r.severity.value,
                    "severity_score": sev_order.get(r.severity, 0),
                    "drift_type": r.drift_type.value,
                }
            )
        results.sort(
            key=lambda x: x["severity_score"],
            reverse=True,
        )
        return results

    def detect_drift_trends(
        self,
    ) -> dict[str, Any]:
        """Detect drift trends via split-half comparison."""
        if len(self._records) < 4:
            return {
                "trend": "insufficient_data",
                "sample_count": len(self._records),
            }
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]
        first_count = len(first_half)
        second_count = len(second_half)
        delta = float(second_count - first_count)
        if delta > 5.0:
            trend = "worsening"
        elif delta < -5.0:
            trend = "improving"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_count": first_count,
            "second_half_count": second_count,
            "delta": delta,
            "total_records": len(self._records),
        }

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> ConfigDriftReport:
        by_drift_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_drift_type[r.drift_type.value] = by_drift_type.get(r.drift_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
        resolved_ids = {res.drift_id for res in self._resolutions}
        unresolved = sum(1 for r in self._records if r.id not in resolved_ids)
        avg_res_time = (
            round(
                sum(res.resolution_time_minutes for res in self._resolutions)
                / len(self._resolutions),
                2,
            )
            if self._resolutions
            else 0.0
        )
        recs: list[str] = []
        critical_count = sum(
            1 for r in self._records if r.severity in (DriftSeverity.CRITICAL, DriftSeverity.HIGH)
        )
        if critical_count > 0:
            recs.append(f"{critical_count} critical/high severity drift(s) detected")
        if unresolved > 0:
            recs.append(f"{unresolved} unresolved drift(s) require attention")
        if not recs:
            recs.append("Configuration drift within acceptable limits")
        return ConfigDriftReport(
            total_records=len(self._records),
            total_resolutions=len(self._resolutions),
            by_drift_type=by_drift_type,
            by_severity=by_severity,
            by_source=by_source,
            unresolved_count=unresolved,
            avg_resolution_time=avg_res_time,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._resolutions.clear()
        logger.info("config_drift_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_resolutions": len(self._resolutions),
            "max_drift_count": self._max_drift_count,
            "drift_type_distribution": type_dist,
            "unique_resources": len({r.resource_id for r in self._records}),
        }
