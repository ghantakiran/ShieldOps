"""Security Control Assessor — assess effectiveness of security controls."""

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
    ACCESS_MANAGEMENT = "access_management"
    DATA_SECURITY = "data_security"
    NETWORK_SECURITY = "network_security"
    APPLICATION_SECURITY = "application_security"
    OPERATIONAL_SECURITY = "operational_security"


class AssessmentResult(StrEnum):
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"
    NOT_TESTED = "not_tested"
    NOT_APPLICABLE = "not_applicable"


class AssessmentMethod(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    HYBRID = "hybrid"
    CONTINUOUS = "continuous"
    SAMPLING = "sampling"


# --- Models ---


class ControlRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    control_domain: ControlDomain = ControlDomain.ACCESS_MANAGEMENT
    assessment_result: AssessmentResult = AssessmentResult.EFFECTIVE
    assessment_method: AssessmentMethod = AssessmentMethod.AUTOMATED
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    control_domain: ControlDomain = ControlDomain.ACCESS_MANAGEMENT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlAssessmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityControlAssessor:
    """Assess security control effectiveness, track domains, identify assessment gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ControlRecord] = []
        self._analyses: list[ControlAnalysis] = []
        logger.info(
            "security_control_assessor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_control(
        self,
        control_name: str,
        control_domain: ControlDomain = ControlDomain.ACCESS_MANAGEMENT,
        assessment_result: AssessmentResult = AssessmentResult.EFFECTIVE,
        assessment_method: AssessmentMethod = AssessmentMethod.AUTOMATED,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ControlRecord:
        record = ControlRecord(
            control_name=control_name,
            control_domain=control_domain,
            assessment_result=assessment_result,
            assessment_method=assessment_method,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_control_assessor.control_recorded",
            record_id=record.id,
            control_name=control_name,
            control_domain=control_domain.value,
            assessment_result=assessment_result.value,
        )
        return record

    def get_record(self, record_id: str) -> ControlRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        control_domain: ControlDomain | None = None,
        assessment_result: AssessmentResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ControlRecord]:
        results = list(self._records)
        if control_domain is not None:
            results = [r for r in results if r.control_domain == control_domain]
        if assessment_result is not None:
            results = [r for r in results if r.assessment_result == assessment_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        control_name: str,
        control_domain: ControlDomain = ControlDomain.ACCESS_MANAGEMENT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ControlAnalysis:
        analysis = ControlAnalysis(
            control_name=control_name,
            control_domain=control_domain,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_control_assessor.analysis_added",
            control_name=control_name,
            control_domain=control_domain.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
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

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "control_name": r.control_name,
                        "control_domain": r.control_domain.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending (lowest first)."""
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

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> ControlAssessmentReport:
        by_domain: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_domain[r.control_domain.value] = by_domain.get(r.control_domain.value, 0) + 1
            by_result[r.assessment_result.value] = by_result.get(r.assessment_result.value, 0) + 1
            by_method[r.assessment_method.value] = by_method.get(r.assessment_method.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.effectiveness_score < self._threshold)
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["control_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} control(s) below effectiveness threshold ({self._threshold})")
        if self._records and avg_effectiveness_score < self._threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._threshold})"
            )
        if not recs:
            recs.append("Security control assessment is healthy")
        return ControlAssessmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_domain=by_domain,
            by_result=by_result,
            by_method=by_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_control_assessor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "domain_distribution": domain_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
