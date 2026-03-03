"""MTTR Optimization Engine — optimize mean-time-to-respond across response phases."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResponsePhase(StrEnum):
    TRIAGE = "triage"
    INVESTIGATION = "investigation"
    CONTAINMENT = "containment"
    REMEDIATION = "remediation"
    RECOVERY = "recovery"


class OptimizationType(StrEnum):
    AUTOMATION = "automation"
    RUNBOOK = "runbook"
    STAFFING = "staffing"
    TOOLING = "tooling"
    PROCESS = "process"


class ImprovementStatus(StrEnum):
    IMPLEMENTED = "implemented"
    IN_PROGRESS = "in_progress"
    PLANNED = "planned"
    EVALUATED = "evaluated"
    DEFERRED = "deferred"


# --- Models ---


class MTTRRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mttr_id: str = ""
    response_phase: ResponsePhase = ResponsePhase.TRIAGE
    optimization_type: OptimizationType = OptimizationType.AUTOMATION
    improvement_status: ImprovementStatus = ImprovementStatus.PLANNED
    response_time_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MTTRAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mttr_id: str = ""
    response_phase: ResponsePhase = ResponsePhase.TRIAGE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MTTRReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_response_time_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_optimization: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MTTROptimizationEngine:
    """Optimize mean-time-to-respond across response phases and optimization types."""

    def __init__(
        self,
        max_records: int = 200000,
        response_time_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._response_time_threshold = response_time_threshold
        self._records: list[MTTRRecord] = []
        self._analyses: list[MTTRAnalysis] = []
        logger.info(
            "mttr_optimization_engine.initialized",
            max_records=max_records,
            response_time_threshold=response_time_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mttr(
        self,
        mttr_id: str,
        response_phase: ResponsePhase = ResponsePhase.TRIAGE,
        optimization_type: OptimizationType = OptimizationType.AUTOMATION,
        improvement_status: ImprovementStatus = ImprovementStatus.PLANNED,
        response_time_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MTTRRecord:
        record = MTTRRecord(
            mttr_id=mttr_id,
            response_phase=response_phase,
            optimization_type=optimization_type,
            improvement_status=improvement_status,
            response_time_score=response_time_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mttr_optimization_engine.mttr_recorded",
            record_id=record.id,
            mttr_id=mttr_id,
            response_phase=response_phase.value,
            optimization_type=optimization_type.value,
        )
        return record

    def get_mttr(self, record_id: str) -> MTTRRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mttrs(
        self,
        response_phase: ResponsePhase | None = None,
        optimization_type: OptimizationType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MTTRRecord]:
        results = list(self._records)
        if response_phase is not None:
            results = [r for r in results if r.response_phase == response_phase]
        if optimization_type is not None:
            results = [r for r in results if r.optimization_type == optimization_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        mttr_id: str,
        response_phase: ResponsePhase = ResponsePhase.TRIAGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MTTRAnalysis:
        analysis = MTTRAnalysis(
            mttr_id=mttr_id,
            response_phase=response_phase,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "mttr_optimization_engine.analysis_added",
            mttr_id=mttr_id,
            response_phase=response_phase.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_phase_distribution(self) -> dict[str, Any]:
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.response_phase.value
            phase_data.setdefault(key, []).append(r.response_time_score)
        result: dict[str, Any] = {}
        for phase, scores in phase_data.items():
            result[phase] = {
                "count": len(scores),
                "avg_response_time_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_response_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.response_time_score < self._response_time_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "mttr_id": r.mttr_id,
                        "response_phase": r.response_phase.value,
                        "response_time_score": r.response_time_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["response_time_score"])

    def rank_by_response_time(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.response_time_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_response_time_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_response_time_score"])
        return results

    def detect_response_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> MTTRReport:
        by_phase: dict[str, int] = {}
        by_optimization: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_phase[r.response_phase.value] = by_phase.get(r.response_phase.value, 0) + 1
            by_optimization[r.optimization_type.value] = (
                by_optimization.get(r.optimization_type.value, 0) + 1
            )
            by_status[r.improvement_status.value] = by_status.get(r.improvement_status.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.response_time_score < self._response_time_threshold
        )
        scores = [r.response_time_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_response_gaps()
        top_gaps = [o["mttr_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} response(s) below threshold ({self._response_time_threshold})"
            )
        if self._records and avg_score < self._response_time_threshold:
            recs.append(
                f"Avg response time score {avg_score} below threshold "
                f"({self._response_time_threshold})"
            )
        if not recs:
            recs.append("MTTR optimization is healthy")
        return MTTRReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_response_time_score=avg_score,
            by_phase=by_phase,
            by_optimization=by_optimization,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("mttr_optimization_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.response_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "response_time_threshold": self._response_time_threshold,
            "phase_distribution": phase_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
