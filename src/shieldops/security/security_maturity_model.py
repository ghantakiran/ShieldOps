"""Security Maturity Model — CMMI/NIST CSF maturity scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaturityDomain(StrEnum):
    IDENTIFY = "identify"
    PROTECT = "protect"
    DETECT = "detect"
    RESPOND = "respond"
    RECOVER = "recover"


class MaturityTier(StrEnum):
    ADAPTIVE = "adaptive"
    REPEATABLE = "repeatable"
    RISK_INFORMED = "risk_informed"
    PARTIAL = "partial"
    INITIAL = "initial"


class AssessmentMethod(StrEnum):
    SELF_ASSESSMENT = "self_assessment"
    EXTERNAL_AUDIT = "external_audit"
    PEER_REVIEW = "peer_review"
    AUTOMATED = "automated"
    HYBRID = "hybrid"


# --- Models ---


class MaturityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    maturity_domain: MaturityDomain = MaturityDomain.IDENTIFY
    maturity_tier: MaturityTier = MaturityTier.ADAPTIVE
    assessment_method: AssessmentMethod = AssessmentMethod.SELF_ASSESSMENT
    maturity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MaturityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    maturity_domain: MaturityDomain = MaturityDomain.IDENTIFY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MaturityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_maturity_count: int = 0
    avg_maturity_score: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_low_maturity: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityMaturityModel:
    """Assess security maturity using CMMI/NIST CSF framework scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        maturity_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._maturity_threshold = maturity_threshold
        self._records: list[MaturityRecord] = []
        self._analyses: list[MaturityAnalysis] = []
        logger.info(
            "security_maturity_model.initialized",
            max_records=max_records,
            maturity_threshold=maturity_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_assessment(
        self,
        domain_name: str,
        maturity_domain: MaturityDomain = MaturityDomain.IDENTIFY,
        maturity_tier: MaturityTier = MaturityTier.ADAPTIVE,
        assessment_method: AssessmentMethod = AssessmentMethod.SELF_ASSESSMENT,
        maturity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MaturityRecord:
        record = MaturityRecord(
            domain_name=domain_name,
            maturity_domain=maturity_domain,
            maturity_tier=maturity_tier,
            assessment_method=assessment_method,
            maturity_score=maturity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_maturity_model.assessment_recorded",
            record_id=record.id,
            domain_name=domain_name,
            maturity_domain=maturity_domain.value,
            maturity_tier=maturity_tier.value,
        )
        return record

    def get_assessment(self, record_id: str) -> MaturityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        maturity_domain: MaturityDomain | None = None,
        maturity_tier: MaturityTier | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MaturityRecord]:
        results = list(self._records)
        if maturity_domain is not None:
            results = [r for r in results if r.maturity_domain == maturity_domain]
        if maturity_tier is not None:
            results = [r for r in results if r.maturity_tier == maturity_tier]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        domain_name: str,
        maturity_domain: MaturityDomain = MaturityDomain.IDENTIFY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MaturityAnalysis:
        analysis = MaturityAnalysis(
            domain_name=domain_name,
            maturity_domain=maturity_domain,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_maturity_model.analysis_added",
            domain_name=domain_name,
            maturity_domain=maturity_domain.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_maturity_distribution(self) -> dict[str, Any]:
        """Group by maturity_domain; return count and avg maturity_score."""
        domain_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.maturity_domain.value
            domain_data.setdefault(key, []).append(r.maturity_score)
        result: dict[str, Any] = {}
        for domain, scores in domain_data.items():
            result[domain] = {
                "count": len(scores),
                "avg_maturity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_maturity_assessments(self) -> list[dict[str, Any]]:
        """Return records where maturity_score < maturity_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.maturity_score < self._maturity_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "domain_name": r.domain_name,
                        "maturity_domain": r.maturity_domain.value,
                        "maturity_score": r.maturity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["maturity_score"])

    def rank_by_maturity(self) -> list[dict[str, Any]]:
        """Group by service, avg maturity_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.maturity_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_maturity_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_maturity_score"])
        return results

    def detect_maturity_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> MaturityReport:
        by_domain: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_domain[r.maturity_domain.value] = by_domain.get(r.maturity_domain.value, 0) + 1
            by_tier[r.maturity_tier.value] = by_tier.get(r.maturity_tier.value, 0) + 1
            by_method[r.assessment_method.value] = by_method.get(r.assessment_method.value, 0) + 1
        low_maturity_count = sum(
            1 for r in self._records if r.maturity_score < self._maturity_threshold
        )
        scores = [r.maturity_score for r in self._records]
        avg_maturity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_maturity_assessments()
        top_low_maturity = [o["domain_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_maturity_count > 0:
            recs.append(
                f"{low_maturity_count} assessment(s) below maturity threshold "
                f"({self._maturity_threshold})"
            )
        if self._records and avg_maturity_score < self._maturity_threshold:
            recs.append(
                f"Avg maturity score {avg_maturity_score} below threshold "
                f"({self._maturity_threshold})"
            )
        if not recs:
            recs.append("Security maturity levels are healthy")
        return MaturityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_maturity_count=low_maturity_count,
            avg_maturity_score=avg_maturity_score,
            by_domain=by_domain,
            by_tier=by_tier,
            by_method=by_method,
            top_low_maturity=top_low_maturity,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_maturity_model.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.maturity_domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "maturity_threshold": self._maturity_threshold,
            "domain_distribution": domain_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
