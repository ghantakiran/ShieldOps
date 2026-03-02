"""Audit Scope Optimizer — optimize audit scope, identify inefficient scopes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScopeCategory(StrEnum):
    HIGH_RISK = "high_risk"
    MEDIUM_RISK = "medium_risk"
    LOW_RISK = "low_risk"
    COMPLIANCE_REQUIRED = "compliance_required"
    DISCRETIONARY = "discretionary"


class AssessmentOutcome(StrEnum):
    FINDING_DENSE = "finding_dense"
    FINDING_SPARSE = "finding_sparse"
    CLEAN = "clean"
    DEFERRED = "deferred"
    ESCALATED = "escalated"


class OptimizationAction(StrEnum):
    EXPAND_SCOPE = "expand_scope"
    REDUCE_SCOPE = "reduce_scope"
    MAINTAIN_SCOPE = "maintain_scope"
    AUTOMATE = "automate"
    DELEGATE = "delegate"


# --- Models ---


class ScopeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_name: str = ""
    scope_category: ScopeCategory = ScopeCategory.HIGH_RISK
    assessment_outcome: AssessmentOutcome = AssessmentOutcome.FINDING_DENSE
    optimization_action: OptimizationAction = OptimizationAction.EXPAND_SCOPE
    efficiency_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ScopeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_name: str = ""
    scope_category: ScopeCategory = ScopeCategory.HIGH_RISK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditScopeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_efficiency_count: int = 0
    avg_efficiency_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_inefficient: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditScopeOptimizer:
    """Optimize audit scope, identify inefficient scopes, track scope efficiency."""

    def __init__(
        self,
        max_records: int = 200000,
        scope_efficiency_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._scope_efficiency_threshold = scope_efficiency_threshold
        self._records: list[ScopeRecord] = []
        self._analyses: list[ScopeAnalysis] = []
        logger.info(
            "audit_scope_optimizer.initialized",
            max_records=max_records,
            scope_efficiency_threshold=scope_efficiency_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_scope(
        self,
        audit_name: str,
        scope_category: ScopeCategory = ScopeCategory.HIGH_RISK,
        assessment_outcome: AssessmentOutcome = AssessmentOutcome.FINDING_DENSE,
        optimization_action: OptimizationAction = OptimizationAction.EXPAND_SCOPE,
        efficiency_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ScopeRecord:
        record = ScopeRecord(
            audit_name=audit_name,
            scope_category=scope_category,
            assessment_outcome=assessment_outcome,
            optimization_action=optimization_action,
            efficiency_score=efficiency_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_scope_optimizer.scope_recorded",
            record_id=record.id,
            audit_name=audit_name,
            scope_category=scope_category.value,
            assessment_outcome=assessment_outcome.value,
        )
        return record

    def get_scope(self, record_id: str) -> ScopeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scopes(
        self,
        scope_category: ScopeCategory | None = None,
        assessment_outcome: AssessmentOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ScopeRecord]:
        results = list(self._records)
        if scope_category is not None:
            results = [r for r in results if r.scope_category == scope_category]
        if assessment_outcome is not None:
            results = [r for r in results if r.assessment_outcome == assessment_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        audit_name: str,
        scope_category: ScopeCategory = ScopeCategory.HIGH_RISK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ScopeAnalysis:
        analysis = ScopeAnalysis(
            audit_name=audit_name,
            scope_category=scope_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "audit_scope_optimizer.analysis_added",
            audit_name=audit_name,
            scope_category=scope_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_scope_distribution(self) -> dict[str, Any]:
        """Group by scope_category; return count and avg efficiency_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.scope_category.value
            cat_data.setdefault(key, []).append(r.efficiency_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_efficiency_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_inefficient_scopes(self) -> list[dict[str, Any]]:
        """Return records where efficiency_score < scope_efficiency_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.efficiency_score < self._scope_efficiency_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "audit_name": r.audit_name,
                        "scope_category": r.scope_category.value,
                        "efficiency_score": r.efficiency_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["efficiency_score"])

    def rank_by_efficiency(self) -> list[dict[str, Any]]:
        """Group by service, avg efficiency_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.efficiency_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_efficiency_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_efficiency_score"])
        return results

    def detect_scope_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AuditScopeReport:
        by_category: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_category[r.scope_category.value] = by_category.get(r.scope_category.value, 0) + 1
            by_outcome[r.assessment_outcome.value] = (
                by_outcome.get(r.assessment_outcome.value, 0) + 1
            )
            by_action[r.optimization_action.value] = (
                by_action.get(r.optimization_action.value, 0) + 1
            )
        low_efficiency_count = sum(
            1 for r in self._records if r.efficiency_score < self._scope_efficiency_threshold
        )
        scores = [r.efficiency_score for r in self._records]
        avg_efficiency_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        ineff_list = self.identify_inefficient_scopes()
        top_inefficient = [o["audit_name"] for o in ineff_list[:5]]
        recs: list[str] = []
        if low_efficiency_count > 0:
            recs.append(f"{low_efficiency_count} inefficient scope(s) — review for optimization")
        if self._records and avg_efficiency_score < self._scope_efficiency_threshold:
            recs.append(
                f"Avg efficiency score {avg_efficiency_score} below threshold "
                f"({self._scope_efficiency_threshold})"
            )
        if not recs:
            recs.append("Audit scope efficiency levels are healthy")
        return AuditScopeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_efficiency_count=low_efficiency_count,
            avg_efficiency_score=avg_efficiency_score,
            by_category=by_category,
            by_outcome=by_outcome,
            by_action=by_action,
            top_inefficient=top_inefficient,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("audit_scope_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scope_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "scope_efficiency_threshold": self._scope_efficiency_threshold,
            "scope_category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
