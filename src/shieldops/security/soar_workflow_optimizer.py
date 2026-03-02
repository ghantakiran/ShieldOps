"""SOAR Workflow Optimizer — optimize SOAR playbook workflows for efficiency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkflowCategory(StrEnum):
    ALERT_TRIAGE = "alert_triage"
    CONTAINMENT = "containment"
    INVESTIGATION = "investigation"
    ENRICHMENT = "enrichment"
    REPORTING = "reporting"


class OptimizationType(StrEnum):
    AUTOMATION = "automation"
    PARALLELIZATION = "parallelization"
    DEDUPLICATION = "deduplication"
    PRIORITIZATION = "prioritization"
    ELIMINATION = "elimination"


class OptimizationImpact(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"
    NEGATIVE = "negative"


# --- Models ---


class WorkflowOptRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    workflow_category: WorkflowCategory = WorkflowCategory.ALERT_TRIAGE
    optimization_type: OptimizationType = OptimizationType.AUTOMATION
    optimization_impact: OptimizationImpact = OptimizationImpact.MEDIUM
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowOptAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    workflow_category: WorkflowCategory = WorkflowCategory.ALERT_TRIAGE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowOptReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_optimization: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SOARWorkflowOptimizer:
    """Optimize SOAR workflows — automation, parallelization, deduplication, prioritization."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._records: list[WorkflowOptRecord] = []
        self._analyses: list[WorkflowOptAnalysis] = []
        logger.info(
            "soar_workflow_optimizer.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_optimization(
        self,
        name: str,
        workflow_category: WorkflowCategory = WorkflowCategory.ALERT_TRIAGE,
        optimization_type: OptimizationType = OptimizationType.AUTOMATION,
        optimization_impact: OptimizationImpact = OptimizationImpact.MEDIUM,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkflowOptRecord:
        record = WorkflowOptRecord(
            name=name,
            workflow_category=workflow_category,
            optimization_type=optimization_type,
            optimization_impact=optimization_impact,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "soar_workflow_optimizer.recorded",
            record_id=record.id,
            name=name,
            workflow_category=workflow_category.value,
            optimization_type=optimization_type.value,
        )
        return record

    def get_record(self, record_id: str) -> WorkflowOptRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        workflow_category: WorkflowCategory | None = None,
        optimization_type: OptimizationType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowOptRecord]:
        results = list(self._records)
        if workflow_category is not None:
            results = [r for r in results if r.workflow_category == workflow_category]
        if optimization_type is not None:
            results = [r for r in results if r.optimization_type == optimization_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        workflow_category: WorkflowCategory = WorkflowCategory.ALERT_TRIAGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkflowOptAnalysis:
        analysis = WorkflowOptAnalysis(
            name=name,
            workflow_category=workflow_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "soar_workflow_optimizer.analysis_added",
            name=name,
            workflow_category=workflow_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_category_distribution(self) -> dict[str, Any]:
        """Group by workflow_category; return count and avg score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.workflow_category.value
            cat_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in cat_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "workflow_category": r.workflow_category.value,
                        "score": r.score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
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

    def generate_report(self) -> WorkflowOptReport:
        by_category: dict[str, int] = {}
        by_optimization: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_category[r.workflow_category.value] = (
                by_category.get(r.workflow_category.value, 0) + 1
            )
            by_optimization[r.optimization_type.value] = (
                by_optimization.get(r.optimization_type.value, 0) + 1
            )
            by_impact[r.optimization_impact.value] = (
                by_impact.get(r.optimization_impact.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.score < self._score_threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} workflow(s) below threshold ({self._score_threshold})")
        if self._records and avg_score < self._score_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("SOAR workflow optimization metrics within healthy range")
        return WorkflowOptReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_category=by_category,
            by_optimization=by_optimization,
            by_impact=by_impact,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("soar_workflow_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.workflow_category.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "score_threshold": self._score_threshold,
            "category_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
