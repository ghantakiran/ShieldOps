"""Licensing Audit Tracker — track software license compliance and audits."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LicenseStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    UNDER_REVIEW = "under_review"


class AuditScope(StrEnum):
    FULL = "full"
    TARGETED = "targeted"
    SPOT_CHECK = "spot_check"
    RENEWAL = "renewal"
    VENDOR = "vendor"


class RemediationAction(StrEnum):
    PURCHASE = "purchase"
    REMOVE = "remove"
    DOWNGRADE = "downgrade"
    NEGOTIATE = "negotiate"
    WAIVER = "waiver"


# --- Models ---


class LicenseAuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    license_status: LicenseStatus = LicenseStatus.UNDER_REVIEW
    audit_scope: AuditScope = AuditScope.FULL
    remediation_action: RemediationAction = RemediationAction.PURCHASE
    license_count: int = 0
    used_count: int = 0
    cost: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LicenseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    license_status: LicenseStatus = LicenseStatus.UNDER_REVIEW
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LicensingAuditReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    non_compliant_count: int = 0
    avg_utilization_pct: float = 0.0
    by_license_status: dict[str, int] = Field(default_factory=dict)
    by_audit_scope: dict[str, int] = Field(default_factory=dict)
    by_remediation_action: dict[str, int] = Field(default_factory=dict)
    top_violations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class LicensingAuditTracker:
    """Track software license compliance, utilization, and audit findings."""

    def __init__(
        self,
        max_records: int = 200000,
        utilization_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._utilization_threshold = utilization_threshold
        self._records: list[LicenseAuditRecord] = []
        self._analyses: list[LicenseAnalysis] = []
        logger.info(
            "licensing_audit_tracker.initialized",
            max_records=max_records,
            utilization_threshold=utilization_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_license_audit(
        self,
        license_status: LicenseStatus = LicenseStatus.UNDER_REVIEW,
        audit_scope: AuditScope = AuditScope.FULL,
        remediation_action: RemediationAction = RemediationAction.PURCHASE,
        license_count: int = 0,
        used_count: int = 0,
        cost: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LicenseAuditRecord:
        record = LicenseAuditRecord(
            license_status=license_status,
            audit_scope=audit_scope,
            remediation_action=remediation_action,
            license_count=license_count,
            used_count=used_count,
            cost=cost,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "licensing_audit_tracker.audit_recorded",
            record_id=record.id,
            license_status=license_status.value,
            cost=cost,
        )
        return record

    def get_license_audit(self, record_id: str) -> LicenseAuditRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_license_audits(
        self,
        license_status: LicenseStatus | None = None,
        audit_scope: AuditScope | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LicenseAuditRecord]:
        results = list(self._records)
        if license_status is not None:
            results = [r for r in results if r.license_status == license_status]
        if audit_scope is not None:
            results = [r for r in results if r.audit_scope == audit_scope]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        license_status: LicenseStatus = LicenseStatus.UNDER_REVIEW,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LicenseAnalysis:
        analysis = LicenseAnalysis(
            license_status=license_status,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "licensing_audit_tracker.analysis_added",
            license_status=license_status.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_status_distribution(self) -> dict[str, Any]:
        """Group by license_status; return count and avg cost."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.license_status.value
            status_data.setdefault(key, []).append(r.cost)
        result: dict[str, Any] = {}
        for status, costs in status_data.items():
            result[status] = {
                "count": len(costs),
                "avg_cost": round(sum(costs) / len(costs), 2),
            }
        return result

    def identify_non_compliant_licenses(self) -> list[dict[str, Any]]:
        """Return records where license_status is NON_COMPLIANT or EXPIRED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.license_status in (
                LicenseStatus.NON_COMPLIANT,
                LicenseStatus.EXPIRED,
            ):
                utilization = (r.used_count / r.license_count * 100) if r.license_count > 0 else 0.0
                results.append(
                    {
                        "record_id": r.id,
                        "license_status": r.license_status.value,
                        "license_count": r.license_count,
                        "used_count": r.used_count,
                        "utilization_pct": round(utilization, 2),
                        "cost": r.cost,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["cost"], reverse=True)

    def rank_by_cost(self) -> list[dict[str, Any]]:
        """Group by service, total cost, sort descending."""
        svc_costs: dict[str, float] = {}
        for r in self._records:
            svc_costs[r.service] = svc_costs.get(r.service, 0.0) + r.cost
        results: list[dict[str, Any]] = [
            {"service": svc, "total_cost": round(cost, 2)} for svc, cost in svc_costs.items()
        ]
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> LicensingAuditReport:
        by_status: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_status[r.license_status.value] = by_status.get(r.license_status.value, 0) + 1
            by_scope[r.audit_scope.value] = by_scope.get(r.audit_scope.value, 0) + 1
            by_action[r.remediation_action.value] = by_action.get(r.remediation_action.value, 0) + 1
        non_compliant_count = sum(
            1
            for r in self._records
            if r.license_status
            in (
                LicenseStatus.NON_COMPLIANT,
                LicenseStatus.EXPIRED,
            )
        )
        utilization_values = []
        for r in self._records:
            if r.license_count > 0:
                utilization_values.append(r.used_count / r.license_count * 100)
        avg_utilization_pct = (
            round(sum(utilization_values) / len(utilization_values), 2)
            if utilization_values
            else 0.0
        )
        violations = self.identify_non_compliant_licenses()
        top_violations = [o["record_id"] for o in violations[:5]]
        recs: list[str] = []
        if non_compliant_count > 0:
            recs.append(f"{non_compliant_count} non-compliant or expired license(s) found")
        if avg_utilization_pct < self._utilization_threshold and self._records:
            recs.append(
                f"Avg utilization {avg_utilization_pct}% below target "
                f"({self._utilization_threshold}%)"
            )
        if not recs:
            recs.append("License compliance is healthy")
        return LicensingAuditReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            non_compliant_count=non_compliant_count,
            avg_utilization_pct=avg_utilization_pct,
            by_license_status=by_status,
            by_audit_scope=by_scope,
            by_remediation_action=by_action,
            top_violations=top_violations,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("licensing_audit_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.license_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "utilization_threshold": self._utilization_threshold,
            "license_status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
