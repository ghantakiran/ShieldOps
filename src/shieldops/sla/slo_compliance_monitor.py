"""SLO Compliance Monitor — monitor SLO compliance in real-time, detect non-compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceState(StrEnum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    NON_COMPLIANT = "non_compliant"
    GRACE_PERIOD = "grace_period"
    EXEMPT = "exempt"


class ComplianceMetric(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    SATURATION = "saturation"


class MonitoringFrequency(StrEnum):
    REAL_TIME = "real_time"
    MINUTE = "minute"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


# --- Models ---


class ComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_id: str = ""
    compliance_state: ComplianceState = ComplianceState.COMPLIANT
    compliance_metric: ComplianceMetric = ComplianceMetric.AVAILABILITY
    monitoring_frequency: MonitoringFrequency = MonitoringFrequency.REAL_TIME
    compliance_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_id: str = ""
    compliance_state: ComplianceState = ComplianceState.COMPLIANT
    check_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_checks: int = 0
    non_compliant_count: int = 0
    avg_compliance_pct: float = 0.0
    by_state: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    top_non_compliant: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOComplianceMonitor:
    """Monitor SLO compliance in real-time, detect non-compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_pct = min_compliance_pct
        self._records: list[ComplianceRecord] = []
        self._checks: list[ComplianceCheck] = []
        logger.info(
            "slo_compliance_monitor.initialized",
            max_records=max_records,
            min_compliance_pct=min_compliance_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_compliance(
        self,
        slo_id: str,
        compliance_state: ComplianceState = ComplianceState.COMPLIANT,
        compliance_metric: ComplianceMetric = ComplianceMetric.AVAILABILITY,
        monitoring_frequency: MonitoringFrequency = MonitoringFrequency.REAL_TIME,
        compliance_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ComplianceRecord:
        record = ComplianceRecord(
            slo_id=slo_id,
            compliance_state=compliance_state,
            compliance_metric=compliance_metric,
            monitoring_frequency=monitoring_frequency,
            compliance_pct=compliance_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_compliance_monitor.compliance_recorded",
            record_id=record.id,
            slo_id=slo_id,
            compliance_state=compliance_state.value,
            compliance_metric=compliance_metric.value,
        )
        return record

    def get_compliance(self, record_id: str) -> ComplianceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_compliance(
        self,
        state: ComplianceState | None = None,
        metric: ComplianceMetric | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceRecord]:
        results = list(self._records)
        if state is not None:
            results = [r for r in results if r.compliance_state == state]
        if metric is not None:
            results = [r for r in results if r.compliance_metric == metric]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_check(
        self,
        slo_id: str,
        compliance_state: ComplianceState = ComplianceState.COMPLIANT,
        check_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ComplianceCheck:
        check = ComplianceCheck(
            slo_id=slo_id,
            compliance_state=compliance_state,
            check_score=check_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_records:
            self._checks = self._checks[-self._max_records :]
        logger.info(
            "slo_compliance_monitor.check_added",
            slo_id=slo_id,
            compliance_state=compliance_state.value,
            check_score=check_score,
        )
        return check

    # -- domain operations --------------------------------------------------

    def analyze_compliance_distribution(self) -> dict[str, Any]:
        """Group by compliance_state; return count and avg compliance_pct."""
        state_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compliance_state.value
            state_data.setdefault(key, []).append(r.compliance_pct)
        result: dict[str, Any] = {}
        for state, scores in state_data.items():
            result[state] = {
                "count": len(scores),
                "avg_compliance_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_non_compliant(self) -> list[dict[str, Any]]:
        """Return records where compliance_state is NON_COMPLIANT or AT_RISK."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_state in (
                ComplianceState.NON_COMPLIANT,
                ComplianceState.AT_RISK,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "slo_id": r.slo_id,
                        "compliance_state": r.compliance_state.value,
                        "compliance_pct": r.compliance_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_pct, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_pct": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_pct"])
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
        """Split-half comparison on check_score; delta threshold 5.0."""
        if len(self._checks) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.check_score for c in self._checks]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
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

    def generate_report(self) -> SLOComplianceReport:
        by_state: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_state[r.compliance_state.value] = by_state.get(r.compliance_state.value, 0) + 1
            by_metric[r.compliance_metric.value] = by_metric.get(r.compliance_metric.value, 0) + 1
            by_frequency[r.monitoring_frequency.value] = (
                by_frequency.get(r.monitoring_frequency.value, 0) + 1
            )
        non_compliant_count = sum(
            1
            for r in self._records
            if r.compliance_state in (ComplianceState.NON_COMPLIANT, ComplianceState.AT_RISK)
        )
        scores = [r.compliance_pct for r in self._records]
        avg_compliance_pct = round(sum(scores) / len(scores), 2) if scores else 0.0
        nc_list = self.identify_non_compliant()
        top_non_compliant = [o["slo_id"] for o in nc_list[:5]]
        recs: list[str] = []
        if self._records and avg_compliance_pct < self._min_compliance_pct:
            recs.append(
                f"Avg compliance {avg_compliance_pct}% below threshold "
                f"({self._min_compliance_pct}%)"
            )
        if non_compliant_count > 0:
            recs.append(
                f"{non_compliant_count} non-compliant/at-risk SLO(s) — review compliance posture"
            )
        if not recs:
            recs.append("SLO compliance levels are healthy")
        return SLOComplianceReport(
            total_records=len(self._records),
            total_checks=len(self._checks),
            non_compliant_count=non_compliant_count,
            avg_compliance_pct=avg_compliance_pct,
            by_state=by_state,
            by_metric=by_metric,
            by_frequency=by_frequency,
            top_non_compliant=top_non_compliant,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._checks.clear()
        logger.info("slo_compliance_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        state_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_state.value
            state_dist[key] = state_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_checks": len(self._checks),
            "min_compliance_pct": self._min_compliance_pct,
            "state_distribution": state_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
