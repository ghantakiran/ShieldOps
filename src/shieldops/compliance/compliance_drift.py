"""Compliance Drift Detector — detect config drift from baselines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftSeverity(StrEnum):
    COSMETIC = "cosmetic"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    BLOCKING = "blocking"


class DriftCategory(StrEnum):
    CONFIGURATION = "configuration"
    ACCESS_CONTROL = "access_control"
    ENCRYPTION = "encryption"
    LOGGING = "logging"
    NETWORK = "network"


class RemediationUrgency(StrEnum):
    IMMEDIATE = "immediate"
    WITHIN_24H = "within_24h"
    WITHIN_WEEK = "within_week"
    NEXT_AUDIT = "next_audit"
    ACCEPTED_RISK = "accepted_risk"


# --- Models ---


class ComplianceDriftRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    resource_id: str = ""
    framework: str = ""
    control_id: str = ""
    drift_category: DriftCategory = DriftCategory.CONFIGURATION
    severity: DriftSeverity = DriftSeverity.MINOR
    expected_state: str = ""
    actual_state: str = ""
    remediation_urgency: RemediationUrgency = RemediationUrgency.WITHIN_WEEK
    is_remediated: bool = False
    detected_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class DriftBaseline(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    framework: str = ""
    control_count: int = 0
    last_audit_at: float = 0.0
    drift_count: int = 0
    compliance_pct: float = 100.0
    created_at: float = Field(default_factory=time.time)


class DriftReport(BaseModel):
    total_drifts: int = 0
    total_baselines: int = 0
    avg_compliance_pct: float = 0.0
    by_severity: dict[str, int] = Field(
        default_factory=dict,
    )
    by_category: dict[str, int] = Field(
        default_factory=dict,
    )
    by_urgency: dict[str, int] = Field(
        default_factory=dict,
    )
    critical_drifts: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Detector ---


class ComplianceDriftDetector:
    """Detect infrastructure drift from compliance baselines."""

    def __init__(
        self,
        max_records: int = 200000,
        max_drift_rate_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_drift_rate_pct = max_drift_rate_pct
        self._items: list[ComplianceDriftRecord] = []
        self._baselines: list[DriftBaseline] = []
        logger.info(
            "compliance_drift.initialized",
            max_records=max_records,
            max_drift_rate_pct=max_drift_rate_pct,
        )

    # -- record / get / list --

    def record_drift(
        self,
        resource_id: str = "",
        framework: str = "",
        control_id: str = "",
        drift_category: DriftCategory = DriftCategory.CONFIGURATION,
        severity: DriftSeverity = DriftSeverity.MINOR,
        expected_state: str = "",
        actual_state: str = "",
        remediation_urgency: RemediationUrgency = (RemediationUrgency.WITHIN_WEEK),
        **kw: Any,
    ) -> ComplianceDriftRecord:
        """Record a compliance drift event."""
        record = ComplianceDriftRecord(
            resource_id=resource_id,
            framework=framework,
            control_id=control_id,
            drift_category=drift_category,
            severity=severity,
            expected_state=expected_state,
            actual_state=actual_state,
            remediation_urgency=remediation_urgency,
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items.pop(0)
        logger.info(
            "compliance_drift.recorded",
            drift_id=record.id,
            resource_id=resource_id,
            framework=framework,
        )
        return record

    def get_drift(
        self,
        drift_id: str,
    ) -> ComplianceDriftRecord | None:
        """Get a single drift record by ID."""
        for item in self._items:
            if item.id == drift_id:
                return item
        return None

    def list_drifts(
        self,
        framework: str | None = None,
        severity: DriftSeverity | None = None,
        limit: int = 50,
    ) -> list[ComplianceDriftRecord]:
        """List drifts with optional filters."""
        results = list(self._items)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        return results[-limit:]

    # -- baseline operations --

    def create_baseline(
        self,
        framework: str = "",
        control_count: int = 0,
        last_audit_at: float = 0.0,
        **kw: Any,
    ) -> DriftBaseline:
        """Create a compliance baseline for a framework."""
        drifts = [r for r in self._items if r.framework == framework and not r.is_remediated]
        drift_count = len(drifts)
        compliance_pct = 100.0
        if control_count > 0:
            compliance_pct = round(
                max(
                    0.0,
                    (1 - drift_count / control_count) * 100,
                ),
                2,
            )
        baseline = DriftBaseline(
            framework=framework,
            control_count=control_count,
            last_audit_at=last_audit_at or time.time(),
            drift_count=drift_count,
            compliance_pct=compliance_pct,
            **kw,
        )
        self._baselines.append(baseline)
        logger.info(
            "compliance_drift.baseline_created",
            baseline_id=baseline.id,
            framework=framework,
            compliance_pct=compliance_pct,
        )
        return baseline

    def compare_to_baseline(
        self,
        framework: str,
    ) -> dict[str, Any]:
        """Compare current drifts to the latest baseline."""
        baselines = [b for b in self._baselines if b.framework == framework]
        if not baselines:
            return {
                "framework": framework,
                "has_baseline": False,
                "message": "No baseline found",
            }
        latest = baselines[-1]
        current_drifts = [
            r for r in self._items if r.framework == framework and not r.is_remediated
        ]
        current_count = len(current_drifts)
        delta = current_count - latest.drift_count
        current_pct = 100.0
        if latest.control_count > 0:
            current_pct = round(
                max(
                    0.0,
                    (1 - current_count / latest.control_count) * 100,
                ),
                2,
            )
        return {
            "framework": framework,
            "has_baseline": True,
            "baseline_drift_count": latest.drift_count,
            "current_drift_count": current_count,
            "delta": delta,
            "baseline_compliance_pct": latest.compliance_pct,
            "current_compliance_pct": current_pct,
            "trending": ("improving" if delta < 0 else "worsening" if delta > 0 else "stable"),
        }

    def calculate_drift_rate(
        self,
        framework: str,
    ) -> dict[str, Any]:
        """Calculate drift rate for a framework."""
        fw_drifts = [r for r in self._items if r.framework == framework]
        total = len(fw_drifts)
        unremediated = sum(1 for r in fw_drifts if not r.is_remediated)
        rate = 0.0
        if total > 0:
            rate = round(unremediated / total * 100, 2)
        exceeds = rate > self._max_drift_rate_pct
        return {
            "framework": framework,
            "total_drifts": total,
            "unremediated": unremediated,
            "drift_rate_pct": rate,
            "max_drift_rate_pct": self._max_drift_rate_pct,
            "exceeds_threshold": exceeds,
        }

    def identify_recurring_drifts(
        self,
    ) -> list[dict[str, Any]]:
        """Identify controls that drift repeatedly."""
        control_counts: dict[str, int] = {}
        for r in self._items:
            key = f"{r.framework}:{r.control_id}"
            control_counts[key] = control_counts.get(key, 0) + 1
        recurring: list[dict[str, Any]] = [
            {"control_key": k, "occurrences": v} for k, v in control_counts.items() if v > 1
        ]
        recurring.sort(
            key=lambda x: x.get("occurrences", 0),  # type: ignore[return-value]
            reverse=True,
        )
        return recurring

    def mark_remediated(
        self,
        drift_id: str,
    ) -> ComplianceDriftRecord | None:
        """Mark a drift as remediated."""
        record = self.get_drift(drift_id)
        if record is None:
            return None
        record.is_remediated = True
        logger.info(
            "compliance_drift.remediated",
            drift_id=drift_id,
        )
        return record

    # -- report --

    def generate_drift_report(self) -> DriftReport:
        """Generate a comprehensive drift report."""
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        critical_drifts: list[str] = []
        for r in self._items:
            sev = r.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            cat = r.drift_category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            urg = r.remediation_urgency.value
            by_urgency[urg] = by_urgency.get(urg, 0) + 1
            if r.severity in (
                DriftSeverity.CRITICAL,
                DriftSeverity.BLOCKING,
            ):
                critical_drifts.append(r.id)
        avg_pct = 0.0
        if self._baselines:
            avg_pct = round(
                sum(b.compliance_pct for b in self._baselines) / len(self._baselines),
                2,
            )
        recs = self._build_recommendations(
            len(self._items),
            len(critical_drifts),
            avg_pct,
        )
        return DriftReport(
            total_drifts=len(self._items),
            total_baselines=len(self._baselines),
            avg_compliance_pct=avg_pct,
            by_severity=by_severity,
            by_category=by_category,
            by_urgency=by_urgency,
            critical_drifts=critical_drifts,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns records cleared."""
        count = len(self._items)
        self._items.clear()
        self._baselines.clear()
        logger.info(
            "compliance_drift.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        sev_dist: dict[str, int] = {}
        for r in self._items:
            key = r.severity.value
            sev_dist[key] = sev_dist.get(key, 0) + 1
        return {
            "total_drifts": len(self._items),
            "total_baselines": len(self._baselines),
            "max_records": self._max_records,
            "max_drift_rate_pct": self._max_drift_rate_pct,
            "severity_distribution": sev_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        total: int,
        critical: int,
        avg_pct: float,
    ) -> list[str]:
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical/blocking drift(s) require immediate attention")
        if total == 0:
            recs.append("No drifts detected - maintain vigilance")
        if avg_pct > 0 and avg_pct < 95:
            recs.append(f"Average compliance at {avg_pct}% - target 95%+")
        if not recs:
            recs.append("Compliance drift within acceptable limits")
        return recs
