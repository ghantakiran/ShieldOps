"""Security SLA Tracker
SLA monitoring, MTTD/MTTR tracking, breach enforcement, escalation triggers."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SlaCategory(StrEnum):
    MTTD = "mttd"
    MTTR = "mttr"
    PATCH_SLA = "patch_sla"
    INCIDENT_RESPONSE = "incident_response"
    EVIDENCE_COLLECTION = "evidence_collection"


class SlaStatus(StrEnum):
    WITHIN_SLA = "within_sla"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    WAIVED = "waived"
    NOT_APPLICABLE = "not_applicable"


class EscalationLevel(StrEnum):
    NONE = "none"
    L1_TEAM_LEAD = "l1_team_lead"
    L2_MANAGER = "l2_manager"
    L3_DIRECTOR = "l3_director"
    L4_EXECUTIVE = "l4_executive"


# --- Models ---


class SlaRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sla_name: str = ""
    sla_category: SlaCategory = SlaCategory.MTTD
    sla_status: SlaStatus = SlaStatus.WITHIN_SLA
    escalation_level: EscalationLevel = EscalationLevel.NONE
    target_hours: float = 0.0
    actual_hours: float = 0.0
    severity: str = "medium"
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SlaAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sla_name: str = ""
    sla_category: SlaCategory = SlaCategory.MTTD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecuritySlaReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_pct: float = 0.0
    breach_count: int = 0
    avg_mttd_hours: float = 0.0
    avg_mttr_hours: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_escalation: dict[str, int] = Field(default_factory=dict)
    breached_slas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecuritySlaTracker:
    """Security SLA monitoring, MTTD/MTTR tracking, breach SLA enforcement, escalation triggers."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[SlaRecord] = []
        self._analyses: list[SlaAnalysis] = []
        logger.info(
            "security_sla_tracker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        sla_name: str,
        sla_category: SlaCategory = SlaCategory.MTTD,
        sla_status: SlaStatus = SlaStatus.WITHIN_SLA,
        escalation_level: EscalationLevel = EscalationLevel.NONE,
        target_hours: float = 0.0,
        actual_hours: float = 0.0,
        severity: str = "medium",
        service: str = "",
        team: str = "",
    ) -> SlaRecord:
        record = SlaRecord(
            sla_name=sla_name,
            sla_category=sla_category,
            sla_status=sla_status,
            escalation_level=escalation_level,
            target_hours=target_hours,
            actual_hours=actual_hours,
            severity=severity,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_sla_tracker.record_added",
            record_id=record.id,
            sla_name=sla_name,
            sla_category=sla_category.value,
        )
        return record

    def get_record(self, record_id: str) -> SlaRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        sla_category: SlaCategory | None = None,
        sla_status: SlaStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SlaRecord]:
        results = list(self._records)
        if sla_category is not None:
            results = [r for r in results if r.sla_category == sla_category]
        if sla_status is not None:
            results = [r for r in results if r.sla_status == sla_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        sla_name: str,
        sla_category: SlaCategory = SlaCategory.MTTD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SlaAnalysis:
        analysis = SlaAnalysis(
            sla_name=sla_name,
            sla_category=sla_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_sla_tracker.analysis_added",
            sla_name=sla_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def compute_mttd_mttr(self) -> dict[str, Any]:
        mttd_hours: list[float] = []
        mttr_hours: list[float] = []
        for r in self._records:
            if r.sla_category == SlaCategory.MTTD:
                mttd_hours.append(r.actual_hours)
            elif r.sla_category == SlaCategory.MTTR:
                mttr_hours.append(r.actual_hours)
        return {
            "avg_mttd_hours": round(sum(mttd_hours) / len(mttd_hours), 2) if mttd_hours else 0.0,
            "avg_mttr_hours": round(sum(mttr_hours) / len(mttr_hours), 2) if mttr_hours else 0.0,
            "mttd_samples": len(mttd_hours),
            "mttr_samples": len(mttr_hours),
            "p90_mttd": round(
                sorted(mttd_hours)[int(len(mttd_hours) * 0.9)] if mttd_hours else 0.0, 2
            ),
            "p90_mttr": round(
                sorted(mttr_hours)[int(len(mttr_hours) * 0.9)] if mttr_hours else 0.0, 2
            ),
        }

    def identify_breaches(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.sla_status == SlaStatus.BREACHED or (
                r.target_hours > 0 and r.actual_hours > r.target_hours
            ):
                overshoot = round(r.actual_hours - r.target_hours, 2) if r.target_hours > 0 else 0
                results.append(
                    {
                        "sla_name": r.sla_name,
                        "sla_category": r.sla_category.value,
                        "target_hours": r.target_hours,
                        "actual_hours": r.actual_hours,
                        "overshoot_hours": overshoot,
                        "severity": r.severity,
                        "escalation_level": r.escalation_level.value,
                    }
                )
        return sorted(results, key=lambda x: x["overshoot_hours"], reverse=True)

    def compute_compliance_rate(self) -> dict[str, Any]:
        if not self._records:
            return {"compliance_pct": 0.0, "total_slas": 0}
        within = sum(1 for r in self._records if r.sla_status == SlaStatus.WITHIN_SLA)
        at_risk = sum(1 for r in self._records if r.sla_status == SlaStatus.AT_RISK)
        breached = sum(1 for r in self._records if r.sla_status == SlaStatus.BREACHED)
        total = len(self._records)
        return {
            "compliance_pct": round(within / total * 100, 2),
            "within_sla": within,
            "at_risk": at_risk,
            "breached": breached,
            "total_slas": total,
        }

    def determine_escalation(self, sla_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.sla_name == sla_name]
        if not matching:
            return {"sla_name": sla_name, "escalation": "no_data"}
        latest = matching[-1]
        if latest.sla_status == SlaStatus.BREACHED:
            if latest.severity in ("critical", "high"):
                level = EscalationLevel.L3_DIRECTOR
            else:
                level = EscalationLevel.L2_MANAGER
        elif latest.sla_status == SlaStatus.AT_RISK:
            level = EscalationLevel.L1_TEAM_LEAD
        else:
            level = EscalationLevel.NONE
        return {
            "sla_name": sla_name,
            "recommended_escalation": level.value,
            "current_status": latest.sla_status.value,
            "severity": latest.severity,
        }

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def process(self, sla_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.sla_name == sla_name]
        if not matching:
            return {"sla_name": sla_name, "status": "no_data"}
        actuals = [r.actual_hours for r in matching]
        breached = sum(1 for r in matching if r.sla_status == SlaStatus.BREACHED)
        return {
            "sla_name": sla_name,
            "record_count": len(matching),
            "avg_actual_hours": round(sum(actuals) / len(actuals), 2),
            "breach_count": breached,
            "compliance_pct": round((len(matching) - breached) / len(matching) * 100, 2),
        }

    def generate_report(self) -> SecuritySlaReport:
        by_cat: dict[str, int] = {}
        by_st: dict[str, int] = {}
        by_esc: dict[str, int] = {}
        for r in self._records:
            by_cat[r.sla_category.value] = by_cat.get(r.sla_category.value, 0) + 1
            by_st[r.sla_status.value] = by_st.get(r.sla_status.value, 0) + 1
            by_esc[r.escalation_level.value] = by_esc.get(r.escalation_level.value, 0) + 1
        breach_count = sum(1 for r in self._records if r.sla_status == SlaStatus.BREACHED)
        compliance = self.compute_compliance_rate()
        metrics = self.compute_mttd_mttr()
        breaches = self.identify_breaches()
        breached_names = [b["sla_name"] for b in breaches[:5]]
        recs: list[str] = []
        if breach_count > 0:
            recs.append(f"{breach_count} SLA breach(es) detected — immediate action required")
        if compliance.get("compliance_pct", 100) < self._threshold:
            recs.append(
                f"SLA compliance at {compliance['compliance_pct']}% — below {self._threshold}%"
            )
        at_risk = by_st.get("at_risk", 0)
        if at_risk > 0:
            recs.append(f"{at_risk} SLA(s) at risk — proactive intervention recommended")
        if not recs:
            recs.append("Security SLA compliance is healthy")
        return SecuritySlaReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=breach_count,
            avg_compliance_pct=compliance.get("compliance_pct", 0.0),
            breach_count=breach_count,
            avg_mttd_hours=metrics["avg_mttd_hours"],
            avg_mttr_hours=metrics["avg_mttr_hours"],
            by_category=by_cat,
            by_status=by_st,
            by_escalation=by_esc,
            breached_slas=breached_names,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.sla_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "category_distribution": cat_dist,
            "unique_slas": len({r.sla_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_sla_tracker.cleared")
        return {"status": "cleared"}
