"""Knowledge Gap Identifier — identify and prioritize team knowledge gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class KnowledgeDomain(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    APPLICATION = "application"
    ARCHITECTURE = "architecture"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class LearningPath(StrEnum):
    DOCUMENTATION = "documentation"
    MENTORING = "mentoring"
    TRAINING = "training"
    SHADOWING = "shadowing"
    CERTIFICATION = "certification"


# --- Models ---


class KnowledgeGapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    team: str = ""
    domain: KnowledgeDomain = KnowledgeDomain.INFRASTRUCTURE
    gap_severity: GapSeverity = GapSeverity.NONE
    learning_path: LearningPath = LearningPath.DOCUMENTATION
    gap_score: float = 0.0
    coverage_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class GapAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    domain: KnowledgeDomain = KnowledgeDomain.INFRASTRUCTURE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeGapReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_gap_score: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_learning_path: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeGapIdentifier:
    """Identify team knowledge gaps across domains and recommend learning paths."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[KnowledgeGapRecord] = []
        self._analyses: list[GapAnalysis] = []
        logger.info(
            "knowledge_gap_identifier.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_gap(
        self,
        engineer: str,
        team: str = "",
        domain: KnowledgeDomain = KnowledgeDomain.INFRASTRUCTURE,
        gap_severity: GapSeverity = GapSeverity.NONE,
        learning_path: LearningPath = LearningPath.DOCUMENTATION,
        gap_score: float = 0.0,
        coverage_pct: float = 0.0,
    ) -> KnowledgeGapRecord:
        record = KnowledgeGapRecord(
            engineer=engineer,
            team=team,
            domain=domain,
            gap_severity=gap_severity,
            learning_path=learning_path,
            gap_score=gap_score,
            coverage_pct=coverage_pct,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_gap_identifier.gap_recorded",
            record_id=record.id,
            engineer=engineer,
            domain=domain.value,
            gap_severity=gap_severity.value,
        )
        return record

    def get_gap(self, record_id: str) -> KnowledgeGapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gaps(
        self,
        domain: KnowledgeDomain | None = None,
        gap_severity: GapSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeGapRecord]:
        results = list(self._records)
        if domain is not None:
            results = [r for r in results if r.domain == domain]
        if gap_severity is not None:
            results = [r for r in results if r.gap_severity == gap_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        engineer: str,
        domain: KnowledgeDomain = KnowledgeDomain.INFRASTRUCTURE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> GapAnalysis:
        analysis = GapAnalysis(
            engineer=engineer,
            domain=domain,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "knowledge_gap_identifier.analysis_added",
            engineer=engineer,
            domain=domain.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by domain; return count and avg gap_score."""
        domain_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.domain.value
            domain_data.setdefault(key, []).append(r.gap_score)
        result: dict[str, Any] = {}
        for domain, scores in domain_data.items():
            result[domain] = {
                "count": len(scores),
                "avg_gap_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_knowledge_gaps(self) -> list[dict[str, Any]]:
        """Return records where gap_score >= threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gap_score >= self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "engineer": r.engineer,
                        "domain": r.domain.value,
                        "gap_score": r.gap_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["gap_score"], reverse=True)

    def rank_by_gap(self) -> list[dict[str, Any]]:
        """Group by engineer, avg gap_score, sort descending."""
        eng_scores: dict[str, list[float]] = {}
        for r in self._records:
            eng_scores.setdefault(r.engineer, []).append(r.gap_score)
        results: list[dict[str, Any]] = []
        for engineer, scores in eng_scores.items():
            results.append(
                {
                    "engineer": engineer,
                    "avg_gap_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_gap_score"], reverse=True)
        return results

    def detect_gap_trends(self) -> dict[str, Any]:
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
            trend = "worsening"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> KnowledgeGapReport:
        by_domain: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_learning_path: dict[str, int] = {}
        for r in self._records:
            by_domain[r.domain.value] = by_domain.get(r.domain.value, 0) + 1
            by_severity[r.gap_severity.value] = by_severity.get(r.gap_severity.value, 0) + 1
            by_learning_path[r.learning_path.value] = (
                by_learning_path.get(r.learning_path.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.gap_score >= self._threshold)
        scores = [r.gap_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_knowledge_gaps()
        top_gaps = [o["engineer"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} engineer(s) with knowledge gaps above threshold ({self._threshold})"
            )
        if self._records and avg_score >= self._threshold:
            recs.append(f"Avg gap score {avg_score} at or above threshold ({self._threshold})")
        if not recs:
            recs.append("Knowledge coverage is healthy")
        return KnowledgeGapReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_gap_score=avg_score,
            by_domain=by_domain,
            by_severity=by_severity,
            by_learning_path=by_learning_path,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("knowledge_gap_identifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "domain_distribution": domain_dist,
            "unique_engineers": len({r.engineer for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
