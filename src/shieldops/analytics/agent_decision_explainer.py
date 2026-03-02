"""Agent Decision Explainer — explain agent and ML model decision rationale."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExplanationType(StrEnum):
    FEATURE_IMPORTANCE = "feature_importance"
    COUNTERFACTUAL = "counterfactual"
    RULE_BASED = "rule_based"
    ATTENTION = "attention"
    SHAPLEY = "shapley"


class ExplanationScope(StrEnum):
    LOCAL = "local"
    GLOBAL = "global"
    COHORT = "cohort"
    CONTRASTIVE = "contrastive"
    CAUSAL = "causal"


class ClarityLevel(StrEnum):
    VERY_CLEAR = "very_clear"
    CLEAR = "clear"
    MODERATE = "moderate"
    UNCLEAR = "unclear"
    OPAQUE = "opaque"


# --- Models ---


class ExplanationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    agent_id: str = ""
    explanation_type: ExplanationType = ExplanationType.FEATURE_IMPORTANCE
    explanation_scope: ExplanationScope = ExplanationScope.LOCAL
    clarity_level: ClarityLevel = ClarityLevel.MODERATE
    clarity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExplanationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    explanation_type: ExplanationType = ExplanationType.FEATURE_IMPORTANCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExplanationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    opaque_count: int = 0
    avg_clarity_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_clarity: dict[str, int] = Field(default_factory=dict)
    top_opaque: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentDecisionExplainer:
    """Explain agent and ML model decision rationale."""

    def __init__(
        self,
        max_records: int = 200000,
        clarity_threshold: float = 0.6,
    ) -> None:
        self._max_records = max_records
        self._clarity_threshold = clarity_threshold
        self._records: list[ExplanationRecord] = []
        self._analyses: list[ExplanationAnalysis] = []
        logger.info(
            "agent_decision_explainer.initialized",
            max_records=max_records,
            clarity_threshold=clarity_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_explanation(
        self,
        model_id: str,
        agent_id: str = "",
        explanation_type: ExplanationType = ExplanationType.FEATURE_IMPORTANCE,
        explanation_scope: ExplanationScope = ExplanationScope.LOCAL,
        clarity_level: ClarityLevel = ClarityLevel.MODERATE,
        clarity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ExplanationRecord:
        record = ExplanationRecord(
            model_id=model_id,
            agent_id=agent_id,
            explanation_type=explanation_type,
            explanation_scope=explanation_scope,
            clarity_level=clarity_level,
            clarity_score=clarity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "agent_decision_explainer.explanation_recorded",
            record_id=record.id,
            model_id=model_id,
            explanation_type=explanation_type.value,
        )
        return record

    def get_explanation(self, record_id: str) -> ExplanationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_explanations(
        self,
        explanation_type: ExplanationType | None = None,
        clarity_level: ClarityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExplanationRecord]:
        results = list(self._records)
        if explanation_type is not None:
            results = [r for r in results if r.explanation_type == explanation_type]
        if clarity_level is not None:
            results = [r for r in results if r.clarity_level == clarity_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        explanation_type: ExplanationType = ExplanationType.FEATURE_IMPORTANCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ExplanationAnalysis:
        analysis = ExplanationAnalysis(
            model_id=model_id,
            explanation_type=explanation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "agent_decision_explainer.analysis_added",
            model_id=model_id,
            explanation_type=explanation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by explanation_type; return count and avg clarity_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.explanation_type.value
            type_data.setdefault(key, []).append(r.clarity_score)
        result: dict[str, Any] = {}
        for etype, scores in type_data.items():
            result[etype] = {
                "count": len(scores),
                "avg_clarity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where clarity_score < clarity_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.clarity_score < self._clarity_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "explanation_type": r.explanation_type.value,
                        "clarity_score": r.clarity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["clarity_score"])

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg clarity_score, sort ascending (lowest first)."""
        model_scores: dict[str, list[float]] = {}
        for r in self._records:
            model_scores.setdefault(r.model_id, []).append(r.clarity_score)
        results: list[dict[str, Any]] = []
        for model_id, scores in model_scores.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_clarity_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_clarity_score"])
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

    def generate_report(self) -> ExplanationReport:
        by_type: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_clarity: dict[str, int] = {}
        for r in self._records:
            by_type[r.explanation_type.value] = by_type.get(r.explanation_type.value, 0) + 1
            by_scope[r.explanation_scope.value] = by_scope.get(r.explanation_scope.value, 0) + 1
            by_clarity[r.clarity_level.value] = by_clarity.get(r.clarity_level.value, 0) + 1
        opaque_count = sum(1 for r in self._records if r.clarity_score < self._clarity_threshold)
        scores = [r.clarity_score for r in self._records]
        avg_clarity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        opaque_list = self.identify_severe_drifts()
        top_opaque = [o["model_id"] for o in opaque_list[:5]]
        recs: list[str] = []
        if self._records and opaque_count > 0:
            recs.append(
                f"{opaque_count} model(s) below clarity threshold ({self._clarity_threshold})"
            )
        if self._records and avg_clarity_score < self._clarity_threshold:
            recs.append(
                f"Avg clarity score {avg_clarity_score} below threshold ({self._clarity_threshold})"
            )
        if not recs:
            recs.append("Decision explainability is within acceptable bounds")
        return ExplanationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            opaque_count=opaque_count,
            avg_clarity_score=avg_clarity_score,
            by_type=by_type,
            by_scope=by_scope,
            by_clarity=by_clarity,
            top_opaque=top_opaque,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("agent_decision_explainer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.explanation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "clarity_threshold": self._clarity_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
