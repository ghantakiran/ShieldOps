"""Knowledge Impact Analyzer — analyze knowledge impact on operations, identify low-impact docs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactCategory(StrEnum):
    MTTR_REDUCTION = "mttr_reduction"
    TOIL_ELIMINATION = "toil_elimination"
    ONBOARDING_SPEED = "onboarding_speed"
    ERROR_PREVENTION = "error_prevention"
    KNOWLEDGE_TRANSFER = "knowledge_transfer"


class DocumentType(StrEnum):
    RUNBOOK = "runbook"
    PLAYBOOK = "playbook"
    ARCHITECTURE_DOC = "architecture_doc"
    TROUBLESHOOTING_GUIDE = "troubleshooting_guide"
    POSTMORTEM = "postmortem"


class RelevanceLevel(StrEnum):
    ESSENTIAL = "essential"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    OBSOLETE = "obsolete"


# --- Models ---


class ImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    impact_category: ImpactCategory = ImpactCategory.MTTR_REDUCTION
    document_type: DocumentType = DocumentType.RUNBOOK
    relevance_level: RelevanceLevel = RelevanceLevel.ESSENTIAL
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    impact_category: ImpactCategory = ImpactCategory.MTTR_REDUCTION
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    low_impact_count: int = 0
    avg_impact_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_relevance: dict[str, int] = Field(default_factory=dict)
    top_low_impact: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeImpactAnalyzer:
    """Analyze knowledge impact on operations, identify low-impact docs, measure effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        impact_relevance_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._impact_relevance_threshold = impact_relevance_threshold
        self._records: list[ImpactRecord] = []
        self._assessments: list[ImpactAssessment] = []
        logger.info(
            "knowledge_impact_analyzer.initialized",
            max_records=max_records,
            impact_relevance_threshold=impact_relevance_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_impact(
        self,
        document_id: str,
        impact_category: ImpactCategory = ImpactCategory.MTTR_REDUCTION,
        document_type: DocumentType = DocumentType.RUNBOOK,
        relevance_level: RelevanceLevel = RelevanceLevel.ESSENTIAL,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ImpactRecord:
        record = ImpactRecord(
            document_id=document_id,
            impact_category=impact_category,
            document_type=document_type,
            relevance_level=relevance_level,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_impact_analyzer.impact_recorded",
            record_id=record.id,
            document_id=document_id,
            impact_category=impact_category.value,
            document_type=document_type.value,
        )
        return record

    def get_impact(self, record_id: str) -> ImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        impact_category: ImpactCategory | None = None,
        document_type: DocumentType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ImpactRecord]:
        results = list(self._records)
        if impact_category is not None:
            results = [r for r in results if r.impact_category == impact_category]
        if document_type is not None:
            results = [r for r in results if r.document_type == document_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        document_id: str,
        impact_category: ImpactCategory = ImpactCategory.MTTR_REDUCTION,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ImpactAssessment:
        assessment = ImpactAssessment(
            document_id=document_id,
            impact_category=impact_category,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "knowledge_impact_analyzer.assessment_added",
            document_id=document_id,
            impact_category=impact_category.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_impact_distribution(self) -> dict[str, Any]:
        """Group by impact_category; return count and avg impact_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.impact_category.value
            cat_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_impact_docs(self) -> list[dict[str, Any]]:
        """Return records where impact_score < impact_relevance_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_score < self._impact_relevance_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "document_id": r.document_id,
                        "impact_category": r.impact_category.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["impact_score"])

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Group by service, avg impact_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"])
        return results

    def detect_impact_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> KnowledgeImpactReport:
        by_category: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_relevance: dict[str, int] = {}
        for r in self._records:
            by_category[r.impact_category.value] = by_category.get(r.impact_category.value, 0) + 1
            by_type[r.document_type.value] = by_type.get(r.document_type.value, 0) + 1
            by_relevance[r.relevance_level.value] = by_relevance.get(r.relevance_level.value, 0) + 1
        low_impact_count = sum(
            1 for r in self._records if r.impact_score < self._impact_relevance_threshold
        )
        scores = [r.impact_score for r in self._records]
        avg_impact_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_impact_docs()
        top_low_impact = [o["document_id"] for o in low_list[:5]]
        recs: list[str] = []
        if low_impact_count > 0:
            recs.append(f"{low_impact_count} low-impact document(s) — review for improvement")
        if self._records and avg_impact_score < self._impact_relevance_threshold:
            recs.append(
                f"Avg impact score {avg_impact_score} below threshold "
                f"({self._impact_relevance_threshold})"
            )
        if not recs:
            recs.append("Knowledge impact levels are healthy")
        return KnowledgeImpactReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            low_impact_count=low_impact_count,
            avg_impact_score=avg_impact_score,
            by_category=by_category,
            by_type=by_type,
            by_relevance=by_relevance,
            top_low_impact=top_low_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("knowledge_impact_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.impact_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "impact_relevance_threshold": self._impact_relevance_threshold,
            "impact_category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
