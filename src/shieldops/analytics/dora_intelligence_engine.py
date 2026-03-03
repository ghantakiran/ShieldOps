"""Dora Intelligence Engine — DORA metrics intelligence and engineering effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DORAMetric(StrEnum):
    DEPLOYMENT_FREQUENCY = "deployment_frequency"
    LEAD_TIME = "lead_time"
    CHANGE_FAILURE_RATE = "change_failure_rate"
    MTTR = "mttr"
    RELIABILITY = "reliability"


class DORASource(StrEnum):
    CI_CD_PIPELINE = "ci_cd_pipeline"
    GIT_HISTORY = "git_history"
    INCIDENT_TRACKER = "incident_tracker"
    DEPLOYMENT_LOG = "deployment_log"
    CUSTOM = "custom"


class DORAPerformance(StrEnum):
    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# --- Models ---


class DORARecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY
    dora_source: DORASource = DORASource.CI_CD_PIPELINE
    dora_performance: DORAPerformance = DORAPerformance.UNKNOWN
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DORAAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DORAIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_dora_metric: dict[str, int] = Field(default_factory=dict)
    by_dora_source: dict[str, int] = Field(default_factory=dict)
    by_dora_performance: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DORAIntelligenceEngine:
    """Dora Intelligence Engine — DORA metrics intelligence and engineering effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DORARecord] = []
        self._analyses: list[DORAAnalysis] = []
        logger.info(
            "dora_intelligence_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_entry(
        self,
        name: str,
        dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY,
        dora_source: DORASource = DORASource.CI_CD_PIPELINE,
        dora_performance: DORAPerformance = DORAPerformance.UNKNOWN,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DORARecord:
        record = DORARecord(
            name=name,
            dora_metric=dora_metric,
            dora_source=dora_source,
            dora_performance=dora_performance,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dora_intelligence_engine.entry_recorded",
            record_id=record.id,
            name=name,
            dora_metric=dora_metric.value,
            dora_source=dora_source.value,
        )
        return record

    def get_record(self, record_id: str) -> DORARecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        dora_metric: DORAMetric | None = None,
        dora_source: DORASource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DORARecord]:
        results = list(self._records)
        if dora_metric is not None:
            results = [r for r in results if r.dora_metric == dora_metric]
        if dora_source is not None:
            results = [r for r in results if r.dora_source == dora_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DORAAnalysis:
        analysis = DORAAnalysis(
            name=name,
            dora_metric=dora_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "dora_intelligence_engine.analysis_added",
            name=name,
            dora_metric=dora_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dora_metric.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in type_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "dora_metric": r.dora_metric.value,
                        "score": r.score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
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

    def generate_report(self) -> DORAIntelligenceReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.dora_metric.value] = by_e1.get(r.dora_metric.value, 0) + 1
            by_e2[r.dora_source.value] = by_e2.get(r.dora_source.value, 0) + 1
            by_e3[r.dora_performance.value] = by_e3.get(r.dora_performance.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Dora Intelligence Engine is healthy")
        return DORAIntelligenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_dora_metric=by_e1,
            by_dora_source=by_e2,
            by_dora_performance=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("dora_intelligence_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dora_metric.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "dora_metric_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
