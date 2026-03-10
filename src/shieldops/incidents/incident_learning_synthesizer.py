"""Incident Learning Synthesizer — learning extraction and synthesis from incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LearningType(StrEnum):
    PATTERN = "pattern"
    ANTIPATTERN = "antipattern"
    BEST_PRACTICE = "best_practice"
    FAILURE_MODE = "failure_mode"


class KnowledgeSource(StrEnum):
    POSTMORTEM = "postmortem"
    RUNBOOK = "runbook"
    ALERT_HISTORY = "alert_history"
    CHANGE_LOG = "change_log"


class ApplicabilityScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    ORGANIZATION = "organization"
    INDUSTRY = "industry"


# --- Models ---


class LearningRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    learning_type: LearningType = LearningType.PATTERN
    knowledge_source: KnowledgeSource = KnowledgeSource.POSTMORTEM
    applicability_scope: ApplicabilityScope = ApplicabilityScope.SERVICE
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LearningAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    learning_type: LearningType = LearningType.PATTERN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentLearningReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_learning_type: dict[str, int] = Field(default_factory=dict)
    by_knowledge_source: dict[str, int] = Field(default_factory=dict)
    by_applicability_scope: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentLearningSynthesizer:
    """Incident Learning Synthesizer
    for learning extraction and synthesis.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[LearningRecord] = []
        self._analyses: list[LearningAnalysis] = []
        logger.info(
            "incident_learning_synthesizer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        learning_type: LearningType = (LearningType.PATTERN),
        knowledge_source: KnowledgeSource = (KnowledgeSource.POSTMORTEM),
        applicability_scope: ApplicabilityScope = (ApplicabilityScope.SERVICE),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LearningRecord:
        record = LearningRecord(
            name=name,
            learning_type=learning_type,
            knowledge_source=knowledge_source,
            applicability_scope=applicability_scope,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_learning_synthesizer.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> LearningRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        learning_type: LearningType | None = None,
        knowledge_source: KnowledgeSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LearningRecord]:
        results = list(self._records)
        if learning_type is not None:
            results = [r for r in results if r.learning_type == learning_type]
        if knowledge_source is not None:
            results = [r for r in results if r.knowledge_source == knowledge_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        learning_type: LearningType = (LearningType.PATTERN),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LearningAnalysis:
        analysis = LearningAnalysis(
            name=name,
            learning_type=learning_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "incident_learning_synthesizer.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def extract_learnings(
        self,
    ) -> list[dict[str, Any]]:
        """Extract key learnings from incident records."""
        type_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            type_data.setdefault(r.learning_type.value, []).append(
                {
                    "name": r.name,
                    "score": r.score,
                    "source": r.knowledge_source.value,
                    "scope": r.applicability_scope.value,
                    "service": r.service,
                }
            )
        learnings: list[dict[str, Any]] = []
        for ltype, entries in type_data.items():
            avg = round(sum(e["score"] for e in entries) / len(entries), 2)
            learnings.append(
                {
                    "learning_type": ltype,
                    "count": len(entries),
                    "avg_score": avg,
                    "top_entries": sorted(
                        entries,
                        key=lambda x: x["score"],
                        reverse=True,
                    )[:3],
                    "actionable": avg >= self._threshold,
                }
            )
        learnings.sort(key=lambda x: x["avg_score"], reverse=True)
        return learnings

    def synthesize_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Synthesize recommendations from learnings."""
        scope_data: dict[str, list[float]] = {}
        source_data: dict[str, int] = {}
        for r in self._records:
            scope_data.setdefault(r.applicability_scope.value, []).append(r.score)
            source_data[r.knowledge_source.value] = source_data.get(r.knowledge_source.value, 0) + 1
        recs: list[dict[str, Any]] = []
        for scope, scores in scope_data.items():
            avg = round(sum(scores) / len(scores), 2)
            antipatterns = sum(
                1
                for r in self._records
                if r.applicability_scope.value == scope
                and r.learning_type == LearningType.ANTIPATTERN
            )
            recs.append(
                {
                    "scope": scope,
                    "avg_score": avg,
                    "antipattern_count": antipatterns,
                    "recommendation": (f"Address {antipatterns} antipatterns at {scope} level")
                    if antipatterns > 0
                    else (f"Maintain {scope} level practices"),
                    "priority": "high" if antipatterns > 0 and avg < self._threshold else "medium",
                }
            )
        recs.sort(key=lambda x: x["avg_score"])
        return recs

    def compute_learning_coverage(
        self,
    ) -> dict[str, Any]:
        """Compute coverage of learning across services."""
        svc_types: dict[str, set[str]] = {}
        svc_sources: dict[str, set[str]] = {}
        for r in self._records:
            svc_types.setdefault(r.service, set()).add(r.learning_type.value)
            svc_sources.setdefault(r.service, set()).add(r.knowledge_source.value)
        all_types = {t.value for t in LearningType}
        all_sources = {s.value for s in KnowledgeSource}
        coverage: list[dict[str, Any]] = []
        for svc in svc_types:
            type_cov = round(len(svc_types[svc]) / len(all_types) * 100, 2)
            src_cov = round(len(svc_sources.get(svc, set())) / len(all_sources) * 100, 2)
            coverage.append(
                {
                    "service": svc,
                    "type_coverage_pct": type_cov,
                    "source_coverage_pct": src_cov,
                    "overall_coverage": round((type_cov + src_cov) / 2, 2),
                }
            )
        coverage.sort(
            key=lambda x: x["overall_coverage"],
            reverse=True,
        )
        return {
            "service_coverage": coverage,
            "total_services": len(svc_types),
        }

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> IncidentLearningReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.learning_type.value] = by_e1.get(r.learning_type.value, 0) + 1
            by_e2[r.knowledge_source.value] = by_e2.get(r.knowledge_source.value, 0) + 1
            by_e3[r.applicability_scope.value] = by_e3.get(r.applicability_scope.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Incident Learning Synthesizer is healthy")
        return IncidentLearningReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_learning_type=by_e1,
            by_knowledge_source=by_e2,
            by_applicability_scope=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("incident_learning_synthesizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.learning_type.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "learning_type_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
