"""IOC Sweep Engine — sweep infrastructure for known IOCs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SweepScope(StrEnum):
    FULL_INFRASTRUCTURE = "full_infrastructure"
    NETWORK_ONLY = "network_only"
    ENDPOINTS_ONLY = "endpoints_only"
    CLOUD_ONLY = "cloud_only"
    CRITICAL_ASSETS = "critical_assets"


class SweepResult(StrEnum):
    MATCH_FOUND = "match_found"
    NO_MATCH = "no_match"
    PARTIAL_MATCH = "partial_match"
    ERROR = "error"
    TIMEOUT = "timeout"


class IOCSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class SweepRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sweep_name: str = ""
    sweep_scope: SweepScope = SweepScope.FULL_INFRASTRUCTURE
    sweep_result: SweepResult = SweepResult.MATCH_FOUND
    ioc_severity: IOCSeverity = IOCSeverity.CRITICAL
    match_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SweepAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sweep_name: str = ""
    sweep_scope: SweepScope = SweepScope.FULL_INFRASTRUCTURE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SweepReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_match_count: int = 0
    avg_match_score: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_high_match: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IOCSweepEngine:
    """Sweep infrastructure for known IOCs and track match results."""

    def __init__(
        self,
        max_records: int = 200000,
        match_score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._match_score_threshold = match_score_threshold
        self._records: list[SweepRecord] = []
        self._analyses: list[SweepAnalysis] = []
        logger.info(
            "ioc_sweep_engine.initialized",
            max_records=max_records,
            match_score_threshold=match_score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_sweep(
        self,
        sweep_name: str,
        sweep_scope: SweepScope = SweepScope.FULL_INFRASTRUCTURE,
        sweep_result: SweepResult = SweepResult.MATCH_FOUND,
        ioc_severity: IOCSeverity = IOCSeverity.CRITICAL,
        match_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SweepRecord:
        record = SweepRecord(
            sweep_name=sweep_name,
            sweep_scope=sweep_scope,
            sweep_result=sweep_result,
            ioc_severity=ioc_severity,
            match_score=match_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ioc_sweep_engine.sweep_recorded",
            record_id=record.id,
            sweep_name=sweep_name,
            sweep_scope=sweep_scope.value,
            sweep_result=sweep_result.value,
        )
        return record

    def get_sweep(self, record_id: str) -> SweepRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_sweeps(
        self,
        sweep_scope: SweepScope | None = None,
        sweep_result: SweepResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SweepRecord]:
        results = list(self._records)
        if sweep_scope is not None:
            results = [r for r in results if r.sweep_scope == sweep_scope]
        if sweep_result is not None:
            results = [r for r in results if r.sweep_result == sweep_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        sweep_name: str,
        sweep_scope: SweepScope = SweepScope.FULL_INFRASTRUCTURE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SweepAnalysis:
        analysis = SweepAnalysis(
            sweep_name=sweep_name,
            sweep_scope=sweep_scope,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "ioc_sweep_engine.analysis_added",
            sweep_name=sweep_name,
            sweep_scope=sweep_scope.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_sweep_distribution(self) -> dict[str, Any]:
        """Group by sweep_scope; return count and avg match_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.sweep_scope.value
            src_data.setdefault(key, []).append(r.match_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_match_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_match_sweeps(self) -> list[dict[str, Any]]:
        """Return records where match_score > match_score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.match_score > self._match_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "sweep_name": r.sweep_name,
                        "sweep_scope": r.sweep_scope.value,
                        "match_score": r.match_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["match_score"], reverse=True)

    def rank_by_match(self) -> list[dict[str, Any]]:
        """Group by service, avg match_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.match_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_match_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_match_score"], reverse=True)
        return results

    def detect_sweep_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> SweepReport:
        by_scope: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_scope[r.sweep_scope.value] = by_scope.get(r.sweep_scope.value, 0) + 1
            by_result[r.sweep_result.value] = by_result.get(r.sweep_result.value, 0) + 1
            by_severity[r.ioc_severity.value] = by_severity.get(r.ioc_severity.value, 0) + 1
        high_match_count = sum(
            1 for r in self._records if r.match_score > self._match_score_threshold
        )
        scores = [r.match_score for r in self._records]
        avg_match_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_match_sweeps()
        top_high_match = [o["sweep_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_match_count > 0:
            recs.append(
                f"{high_match_count} sweep(s) above match score threshold "
                f"({self._match_score_threshold})"
            )
        if self._records and avg_match_score > self._match_score_threshold:
            recs.append(
                f"Avg match score {avg_match_score} above threshold ({self._match_score_threshold})"
            )
        if not recs:
            recs.append("IOC sweep results are healthy")
        return SweepReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_match_count=high_match_count,
            avg_match_score=avg_match_score,
            by_scope=by_scope,
            by_result=by_result,
            by_severity=by_severity,
            top_high_match=top_high_match,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("ioc_sweep_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.sweep_scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "match_score_threshold": self._match_score_threshold,
            "scope_distribution": scope_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
