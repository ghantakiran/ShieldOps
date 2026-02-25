"""Permission Drift Detector — detect IAM/RBAC permission creep."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftType(StrEnum):
    UNUSED_PERMISSION = "unused_permission"
    OVER_PRIVILEGED = "over_privileged"
    ORPHANED_ROLE = "orphaned_role"
    POLICY_VIOLATION = "policy_violation"
    ESCALATION_RISK = "escalation_risk"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class PermissionScope(StrEnum):
    IAM = "iam"
    RBAC = "rbac"
    SERVICE_ACCOUNT = "service_account"
    API_KEY = "api_key"
    DATABASE = "database"


# --- Models ---


class PermissionDriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    principal: str = ""
    scope: PermissionScope = PermissionScope.IAM
    drift_type: DriftType = DriftType.UNUSED_PERMISSION
    severity: DriftSeverity = DriftSeverity.MEDIUM
    permission: str = ""
    unused_days: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PermissionBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    principal: str = ""
    scope: PermissionScope = PermissionScope.IAM
    permissions: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class PermissionDriftReport(BaseModel):
    total_drifts: int = 0
    total_baselines: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PermissionDriftDetector:
    """Detect IAM/RBAC permission creep and drift from least-privilege baseline."""

    def __init__(
        self,
        max_records: int = 200000,
        unused_days_threshold: int = 90,
    ) -> None:
        self._max_records = max_records
        self._unused_days_threshold = unused_days_threshold
        self._records: list[PermissionDriftRecord] = []
        self._baselines: list[PermissionBaseline] = []
        logger.info(
            "permission_drift.initialized",
            max_records=max_records,
            unused_days_threshold=unused_days_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_drift(
        self,
        principal: str,
        scope: PermissionScope = PermissionScope.IAM,
        drift_type: DriftType = DriftType.UNUSED_PERMISSION,
        severity: DriftSeverity = DriftSeverity.MEDIUM,
        permission: str = "",
        unused_days: int = 0,
        details: str = "",
    ) -> PermissionDriftRecord:
        record = PermissionDriftRecord(
            principal=principal,
            scope=scope,
            drift_type=drift_type,
            severity=severity,
            permission=permission,
            unused_days=unused_days,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "permission_drift.drift_recorded",
            record_id=record.id,
            principal=principal,
            drift_type=drift_type.value,
            severity=severity.value,
        )
        return record

    def get_drift(self, record_id: str) -> PermissionDriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
        self,
        principal: str | None = None,
        drift_type: DriftType | None = None,
        severity: DriftSeverity | None = None,
        limit: int = 50,
    ) -> list[PermissionDriftRecord]:
        results = list(self._records)
        if principal is not None:
            results = [r for r in results if r.principal == principal]
        if drift_type is not None:
            results = [r for r in results if r.drift_type == drift_type]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        return results[-limit:]

    def set_baseline(
        self,
        principal: str,
        scope: PermissionScope = PermissionScope.IAM,
        permissions: list[str] | None = None,
    ) -> PermissionBaseline:
        baseline = PermissionBaseline(
            principal=principal,
            scope=scope,
            permissions=permissions or [],
        )
        self._baselines.append(baseline)
        if len(self._baselines) > self._max_records:
            self._baselines = self._baselines[-self._max_records :]
        logger.info(
            "permission_drift.baseline_set",
            principal=principal,
            scope=scope.value,
            permission_count=len(baseline.permissions),
        )
        return baseline

    # -- domain operations -----------------------------------------------

    def detect_unused_permissions(self) -> list[dict[str, Any]]:
        """Find permissions unused beyond threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if (
                r.drift_type == DriftType.UNUSED_PERMISSION
                and r.unused_days >= self._unused_days_threshold
            ):
                results.append(
                    {
                        "principal": r.principal,
                        "permission": r.permission,
                        "unused_days": r.unused_days,
                        "scope": r.scope.value,
                        "severity": r.severity.value,
                    }
                )
        results.sort(key=lambda x: x["unused_days"], reverse=True)
        return results

    def detect_over_privileged_principals(self) -> list[dict[str, Any]]:
        """Find over-privileged principals."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.drift_type == DriftType.OVER_PRIVILEGED:
                results.append(
                    {
                        "principal": r.principal,
                        "permission": r.permission,
                        "scope": r.scope.value,
                        "severity": r.severity.value,
                        "details": r.details,
                    }
                )
        results.sort(key=lambda x: list(DriftSeverity).index(DriftSeverity(x["severity"])))
        return results

    def compare_to_baseline(self, principal: str) -> dict[str, Any]:
        """Compare current permissions to baseline."""
        baselines = [b for b in self._baselines if b.principal == principal]
        drifts = [r for r in self._records if r.principal == principal]
        if not baselines:
            return {"principal": principal, "baseline_found": False}
        latest = baselines[-1]
        drift_perms = {r.permission for r in drifts}
        baseline_perms = set(latest.permissions)
        extra = drift_perms - baseline_perms
        return {
            "principal": principal,
            "baseline_found": True,
            "baseline_permissions": len(baseline_perms),
            "drift_count": len(drifts),
            "extra_permissions": sorted(extra),
        }

    def rank_principals_by_drift(self) -> list[dict[str, Any]]:
        """Rank principals by drift severity and count."""
        principal_counts: dict[str, int] = {}
        principal_critical: dict[str, int] = {}
        for r in self._records:
            principal_counts[r.principal] = principal_counts.get(r.principal, 0) + 1
            if r.severity in (DriftSeverity.CRITICAL, DriftSeverity.HIGH):
                principal_critical[r.principal] = principal_critical.get(r.principal, 0) + 1
        results: list[dict[str, Any]] = []
        for p, count in principal_counts.items():
            results.append(
                {
                    "principal": p,
                    "total_drifts": count,
                    "critical_high_count": principal_critical.get(p, 0),
                }
            )
        results.sort(key=lambda x: x["total_drifts"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PermissionDriftReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.drift_type.value] = by_type.get(r.drift_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        critical = sum(1 for r in self._records if r.severity == DriftSeverity.CRITICAL)
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical permission drift(s) detected")
        unused = len(self.detect_unused_permissions())
        if unused > 0:
            recs.append(
                f"{unused} unused permission(s) exceed {self._unused_days_threshold}-day threshold"
            )
        if not recs:
            recs.append("Permission configuration within acceptable drift limits")
        return PermissionDriftReport(
            total_drifts=len(self._records),
            total_baselines=len(self._baselines),
            by_type=by_type,
            by_severity=by_severity,
            critical_count=critical,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._baselines.clear()
        logger.info("permission_drift.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_drifts": len(self._records),
            "total_baselines": len(self._baselines),
            "unused_days_threshold": self._unused_days_threshold,
            "type_distribution": type_dist,
            "unique_principals": len({r.principal for r in self._records}),
        }
