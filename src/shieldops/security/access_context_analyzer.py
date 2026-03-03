"""Access Context Analyzer — analyze access context factors and risk decisions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContextFactor(StrEnum):
    LOCATION = "location"
    DEVICE = "device"
    TIME = "time"
    NETWORK = "network"
    BEHAVIOR = "behavior"


class RiskDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CHALLENGE = "challenge"
    STEP_UP = "step_up"
    MONITOR = "monitor"


class AnalysisScope(StrEnum):
    USER = "user"
    APPLICATION = "application"
    RESOURCE = "resource"
    SESSION = "session"
    TRANSACTION = "transaction"


# --- Models ---


class ContextRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = ""
    context_factor: ContextFactor = ContextFactor.LOCATION
    risk_decision: RiskDecision = RiskDecision.ALLOW
    analysis_scope: AnalysisScope = AnalysisScope.USER
    context_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ContextAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = ""
    context_factor: ContextFactor = ContextFactor.LOCATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessContextReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_context_score: float = 0.0
    by_context_factor: dict[str, int] = Field(default_factory=dict)
    by_risk_decision: dict[str, int] = Field(default_factory=dict)
    by_analysis_scope: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AccessContextAnalyzer:
    """Analyze access context factors, risk decisions, and contextual access patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        context_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._context_gap_threshold = context_gap_threshold
        self._records: list[ContextRecord] = []
        self._analyses: list[ContextAnalysis] = []
        logger.info(
            "access_context_analyzer.initialized",
            max_records=max_records,
            context_gap_threshold=context_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_context(
        self,
        context_id: str,
        context_factor: ContextFactor = ContextFactor.LOCATION,
        risk_decision: RiskDecision = RiskDecision.ALLOW,
        analysis_scope: AnalysisScope = AnalysisScope.USER,
        context_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ContextRecord:
        record = ContextRecord(
            context_id=context_id,
            context_factor=context_factor,
            risk_decision=risk_decision,
            analysis_scope=analysis_scope,
            context_score=context_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "access_context_analyzer.context_recorded",
            record_id=record.id,
            context_id=context_id,
            context_factor=context_factor.value,
            risk_decision=risk_decision.value,
        )
        return record

    def get_context(self, record_id: str) -> ContextRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_contexts(
        self,
        context_factor: ContextFactor | None = None,
        risk_decision: RiskDecision | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ContextRecord]:
        results = list(self._records)
        if context_factor is not None:
            results = [r for r in results if r.context_factor == context_factor]
        if risk_decision is not None:
            results = [r for r in results if r.risk_decision == risk_decision]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        context_id: str,
        context_factor: ContextFactor = ContextFactor.LOCATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ContextAnalysis:
        analysis = ContextAnalysis(
            context_id=context_id,
            context_factor=context_factor,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "access_context_analyzer.analysis_added",
            context_id=context_id,
            context_factor=context_factor.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_context_distribution(self) -> dict[str, Any]:
        """Group by context_factor; return count and avg context_score."""
        factor_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.context_factor.value
            factor_data.setdefault(key, []).append(r.context_score)
        result: dict[str, Any] = {}
        for factor, scores in factor_data.items():
            result[factor] = {
                "count": len(scores),
                "avg_context_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_context_gaps(self) -> list[dict[str, Any]]:
        """Return records where context_score < context_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.context_score < self._context_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "context_id": r.context_id,
                        "context_factor": r.context_factor.value,
                        "context_score": r.context_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["context_score"])

    def rank_by_context(self) -> list[dict[str, Any]]:
        """Group by service, avg context_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.context_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_context_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_context_score"])
        return results

    def detect_context_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AccessContextReport:
        by_context_factor: dict[str, int] = {}
        by_risk_decision: dict[str, int] = {}
        by_analysis_scope: dict[str, int] = {}
        for r in self._records:
            by_context_factor[r.context_factor.value] = (
                by_context_factor.get(r.context_factor.value, 0) + 1
            )
            by_risk_decision[r.risk_decision.value] = (
                by_risk_decision.get(r.risk_decision.value, 0) + 1
            )
            by_analysis_scope[r.analysis_scope.value] = (
                by_analysis_scope.get(r.analysis_scope.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.context_score < self._context_gap_threshold)
        scores = [r.context_score for r in self._records]
        avg_context_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_context_gaps()
        top_gaps = [o["context_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} context(s) below context threshold ({self._context_gap_threshold})"
            )
        if self._records and avg_context_score < self._context_gap_threshold:
            recs.append(
                f"Avg context score {avg_context_score} below threshold "
                f"({self._context_gap_threshold})"
            )
        if not recs:
            recs.append("Access context analysis is healthy")
        return AccessContextReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_context_score=avg_context_score,
            by_context_factor=by_context_factor,
            by_risk_decision=by_risk_decision,
            by_analysis_scope=by_analysis_scope,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("access_context_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.context_factor.value
            factor_dist[key] = factor_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "context_gap_threshold": self._context_gap_threshold,
            "context_factor_distribution": factor_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
