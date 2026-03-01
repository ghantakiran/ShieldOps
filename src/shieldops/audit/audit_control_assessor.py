"""Audit Control Assessor — assess audit control effectiveness, detect control gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControlDomain(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    CHANGE_MANAGEMENT = "change_management"
    MONITORING = "monitoring"
    INCIDENT_RESPONSE = "incident_response"


class ControlEffectiveness(StrEnum):
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"
    NOT_TESTED = "not_tested"
    NOT_APPLICABLE = "not_applicable"


class AssessmentType(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    HYBRID = "hybrid"
    CONTINUOUS = "continuous"
    PERIODIC = "periodic"


# --- Models ---


class ControlRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    control_domain: ControlDomain = ControlDomain.ACCESS_CONTROL
    control_effectiveness: ControlEffectiveness = ControlEffectiveness.NOT_TESTED
    assessment_type: AssessmentType = AssessmentType.AUTOMATED
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    control_domain: ControlDomain = ControlDomain.ACCESS_CONTROL
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditControlReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    ineffective_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    by_assessment_type: dict[str, int] = Field(default_factory=dict)
    top_ineffective: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditControlAssessor:
    """Assess audit control effectiveness, detect control gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        min_effectiveness_score: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._min_effectiveness_score = min_effectiveness_score
        self._records: list[ControlRecord] = []
        self._assessments: list[ControlAssessment] = []
        logger.info(
            "audit_control_assessor.initialized",
            max_records=max_records,
            min_effectiveness_score=min_effectiveness_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_control(
        self,
        control_id: str,
        control_domain: ControlDomain = ControlDomain.ACCESS_CONTROL,
        control_effectiveness: ControlEffectiveness = ControlEffectiveness.NOT_TESTED,
        assessment_type: AssessmentType = AssessmentType.AUTOMATED,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ControlRecord:
        record = ControlRecord(
            control_id=control_id,
            control_domain=control_domain,
            control_effectiveness=control_effectiveness,
            assessment_type=assessment_type,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_control_assessor.control_recorded",
            record_id=record.id,
            control_id=control_id,
            control_domain=control_domain.value,
            control_effectiveness=control_effectiveness.value,
        )
        return record

    def get_control(self, record_id: str) -> ControlRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_controls(
        self,
        domain: ControlDomain | None = None,
        effectiveness: ControlEffectiveness | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ControlRecord]:
        results = list(self._records)
        if domain is not None:
            results = [r for r in results if r.control_domain == domain]
        if effectiveness is not None:
            results = [r for r in results if r.control_effectiveness == effectiveness]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        control_id: str,
        control_domain: ControlDomain = ControlDomain.ACCESS_CONTROL,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ControlAssessment:
        assessment = ControlAssessment(
            control_id=control_id,
            control_domain=control_domain,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "audit_control_assessor.assessment_added",
            control_id=control_id,
            control_domain=control_domain.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_control_distribution(self) -> dict[str, Any]:
        """Group by control_domain; return count and avg effectiveness_score."""
        domain_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.control_domain.value
            domain_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for domain, scores in domain_data.items():
            result[domain] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_ineffective_controls(self) -> list[dict[str, Any]]:
        """Return records where control_effectiveness is INEFFECTIVE or NOT_TESTED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.control_effectiveness in (
                ControlEffectiveness.INEFFECTIVE,
                ControlEffectiveness.NOT_TESTED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "control_id": r.control_id,
                        "control_effectiveness": r.control_effectiveness.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_control_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> AuditControlReport:
        by_domain: dict[str, int] = {}
        by_effectiveness: dict[str, int] = {}
        by_assessment_type: dict[str, int] = {}
        for r in self._records:
            by_domain[r.control_domain.value] = by_domain.get(r.control_domain.value, 0) + 1
            by_effectiveness[r.control_effectiveness.value] = (
                by_effectiveness.get(r.control_effectiveness.value, 0) + 1
            )
            by_assessment_type[r.assessment_type.value] = (
                by_assessment_type.get(r.assessment_type.value, 0) + 1
            )
        ineffective_count = sum(
            1
            for r in self._records
            if r.control_effectiveness
            in (
                ControlEffectiveness.INEFFECTIVE,
                ControlEffectiveness.NOT_TESTED,
            )
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        ineffective_list = self.identify_ineffective_controls()
        top_ineffective = [i["control_id"] for i in ineffective_list[:5]]
        recs: list[str] = []
        if self._records and avg_effectiveness_score < self._min_effectiveness_score:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below "
                f"threshold ({self._min_effectiveness_score})"
            )
        if ineffective_count > 0:
            recs.append(f"{ineffective_count} ineffective control(s) — remediate gaps")
        if not recs:
            recs.append("Audit control effectiveness levels are healthy")
        return AuditControlReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            ineffective_count=ineffective_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_domain=by_domain,
            by_effectiveness=by_effectiveness,
            by_assessment_type=by_assessment_type,
            top_ineffective=top_ineffective,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("audit_control_assessor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_effectiveness_score": self._min_effectiveness_score,
            "control_domain_distribution": domain_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
