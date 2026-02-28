"""SLO Compliance Checker — track SLO compliance records, violations, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    NON_COMPLIANT = "non_compliant"
    CRITICAL_BREACH = "critical_breach"
    UNKNOWN = "unknown"


class SLOType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    DURABILITY = "durability"


class CompliancePeriod(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# --- Models ---


class ComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    slo_name: str = ""
    slo_type: SLOType = SLOType.AVAILABILITY
    period: CompliancePeriod = CompliancePeriod.DAILY
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    compliance_pct: float = 100.0
    target_pct: float = 99.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    slo_name: str = ""
    slo_type: SLOType = SLOType.AVAILABILITY
    status: ComplianceStatus = ComplianceStatus.NON_COMPLIANT
    breach_pct: float = 0.0
    duration_minutes: float = 0.0
    root_cause: str = ""
    resolved: bool = False
    created_at: float = Field(default_factory=time.time)


class SLOComplianceReport(BaseModel):
    total_compliances: int = 0
    total_violations: int = 0
    overall_compliance_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_slo_type: dict[str, int] = Field(default_factory=dict)
    non_compliant_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOComplianceChecker:
    """Track SLO compliance records, violations, and trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_pct: float = 99.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_pct = min_compliance_pct
        self._records: list[ComplianceRecord] = []
        self._violations: list[ComplianceViolation] = []
        logger.info(
            "slo_compliance.initialized",
            max_records=max_records,
            min_compliance_pct=min_compliance_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_compliance(
        self,
        service_name: str,
        slo_name: str = "",
        slo_type: SLOType = SLOType.AVAILABILITY,
        period: CompliancePeriod = CompliancePeriod.DAILY,
        status: ComplianceStatus = ComplianceStatus.COMPLIANT,
        compliance_pct: float = 100.0,
        target_pct: float = 99.0,
        details: str = "",
    ) -> ComplianceRecord:
        record = ComplianceRecord(
            service_name=service_name,
            slo_name=slo_name,
            slo_type=slo_type,
            period=period,
            status=status,
            compliance_pct=compliance_pct,
            target_pct=target_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_compliance.compliance_recorded",
            record_id=record.id,
            service_name=service_name,
            slo_name=slo_name,
            status=status.value,
            compliance_pct=compliance_pct,
        )
        return record

    def get_compliance(self, record_id: str) -> ComplianceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_compliances(
        self,
        service_name: str | None = None,
        slo_type: SLOType | None = None,
        limit: int = 50,
    ) -> list[ComplianceRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if slo_type is not None:
            results = [r for r in results if r.slo_type == slo_type]
        return results[-limit:]

    def add_violation(
        self,
        service_name: str,
        slo_name: str = "",
        slo_type: SLOType = SLOType.AVAILABILITY,
        status: ComplianceStatus = ComplianceStatus.NON_COMPLIANT,
        breach_pct: float = 0.0,
        duration_minutes: float = 0.0,
        root_cause: str = "",
        resolved: bool = False,
    ) -> ComplianceViolation:
        violation = ComplianceViolation(
            service_name=service_name,
            slo_name=slo_name,
            slo_type=slo_type,
            status=status,
            breach_pct=breach_pct,
            duration_minutes=duration_minutes,
            root_cause=root_cause,
            resolved=resolved,
        )
        self._violations.append(violation)
        if len(self._violations) > self._max_records:
            self._violations = self._violations[-self._max_records :]
        logger.info(
            "slo_compliance.violation_added",
            service_name=service_name,
            slo_name=slo_name,
            status=status.value,
            breach_pct=breach_pct,
        )
        return violation

    # -- domain operations -----------------------------------------------

    def analyze_compliance_by_service(self, service_name: str) -> dict[str, Any]:
        """Analyze SLO compliance breakdown for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_compliance = round(sum(r.compliance_pct for r in records) / len(records), 2)
        compliant_count = sum(1 for r in records if r.status == ComplianceStatus.COMPLIANT)
        slo_type_dist: dict[str, int] = {}
        for r in records:
            slo_type_dist[r.slo_type.value] = slo_type_dist.get(r.slo_type.value, 0) + 1
        return {
            "service_name": service_name,
            "total_slos": len(records),
            "compliant_count": compliant_count,
            "avg_compliance_pct": avg_compliance,
            "slo_type_distribution": slo_type_dist,
            "meets_threshold": avg_compliance >= self._min_compliance_pct,
        }

    def identify_non_compliant_slos(self) -> list[dict[str, Any]]:
        """Find SLOs that are non-compliant or in critical breach."""
        non_compliant_statuses = (
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.CRITICAL_BREACH,
        )
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in non_compliant_statuses:
                deficit = round(r.target_pct - r.compliance_pct, 4)
                results.append(
                    {
                        "service_name": r.service_name,
                        "slo_name": r.slo_name,
                        "slo_type": r.slo_type.value,
                        "compliance_pct": r.compliance_pct,
                        "target_pct": r.target_pct,
                        "deficit_pct": deficit,
                        "status": r.status.value,
                    }
                )
        results.sort(key=lambda x: x["deficit_pct"], reverse=True)
        return results

    def rank_by_compliance_score(self) -> list[dict[str, Any]]:
        """Rank services by average compliance percentage descending."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service_name, []).append(r.compliance_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_compliance_pct": avg,
                    "slo_count": len(scores),
                    "meets_threshold": avg >= self._min_compliance_pct,
                }
            )
        results.sort(key=lambda x: x["avg_compliance_pct"], reverse=True)
        return results

    def detect_compliance_trends(self) -> list[dict[str, Any]]:
        """Detect services with degrading compliance trends (at-risk or worsening)."""
        service_statuses: dict[str, list[str]] = {}
        service_scores: dict[str, list[float]] = {}
        for r in sorted(self._records, key=lambda x: x.created_at):
            service_statuses.setdefault(r.service_name, []).append(r.status.value)
            service_scores.setdefault(r.service_name, []).append(r.compliance_pct)
        results: list[dict[str, Any]] = []
        degrading_statuses = {
            ComplianceStatus.AT_RISK.value,
            ComplianceStatus.NON_COMPLIANT.value,
            ComplianceStatus.CRITICAL_BREACH.value,
        }
        for svc, statuses in service_statuses.items():
            scores = service_scores.get(svc, [])
            recent_bad = sum(1 for s in statuses[-3:] if s in degrading_statuses)
            if recent_bad >= 2 and len(statuses) >= 2:
                trend_direction = "degrading"
                if len(scores) >= 2:
                    trend_direction = "degrading" if scores[-1] < scores[0] else "stable"
                results.append(
                    {
                        "service_name": svc,
                        "recent_non_compliant_count": recent_bad,
                        "latest_compliance_pct": scores[-1] if scores else 0.0,
                        "trend": trend_direction,
                        "degradation_detected": True,
                    }
                )
        results.sort(key=lambda x: x["recent_non_compliant_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SLOComplianceReport:
        by_status: dict[str, int] = {}
        by_slo_type: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_slo_type[r.slo_type.value] = by_slo_type.get(r.slo_type.value, 0) + 1
        overall_compliance = (
            round(sum(r.compliance_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        non_compliant = self.identify_non_compliant_slos()
        trends = self.detect_compliance_trends()
        recs: list[str] = []
        if overall_compliance < self._min_compliance_pct:
            recs.append(
                f"Overall compliance {overall_compliance}% is below "
                f"{self._min_compliance_pct}% target"
            )
        if non_compliant:
            recs.append(f"{len(non_compliant)} SLO(s) are non-compliant or in critical breach")
        if trends:
            recs.append(f"{len(trends)} service(s) show degrading compliance trends")
        if not recs:
            recs.append("All SLOs are within compliance targets")
        return SLOComplianceReport(
            total_compliances=len(self._records),
            total_violations=len(self._violations),
            overall_compliance_pct=overall_compliance,
            by_status=by_status,
            by_slo_type=by_slo_type,
            non_compliant_count=len(non_compliant),
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._violations.clear()
        logger.info("slo_compliance.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_compliances": len(self._records),
            "total_violations": len(self._violations),
            "min_compliance_pct": self._min_compliance_pct,
            "status_distribution": status_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
