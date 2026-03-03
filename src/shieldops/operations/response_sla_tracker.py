"""Response SLA Tracker — track incident response SLA compliance and metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SLAMetric(StrEnum):
    TIME_TO_DETECT = "time_to_detect"
    TIME_TO_CONTAIN = "time_to_contain"
    TIME_TO_ERADICATE = "time_to_eradicate"
    TIME_TO_RECOVER = "time_to_recover"
    TIME_TO_CLOSE = "time_to_close"


class SLAStatus(StrEnum):
    WITHIN_TARGET = "within_target"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    EXCEEDED = "exceeded"
    NOT_APPLICABLE = "not_applicable"


class SLASeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# --- Models ---


class SLARecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    sla_metric: SLAMetric = SLAMetric.TIME_TO_DETECT
    sla_status: SLAStatus = SLAStatus.WITHIN_TARGET
    sla_severity: SLASeverity = SLASeverity.MEDIUM
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SLAAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    sla_metric: SLAMetric = SLAMetric.TIME_TO_DETECT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLAReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResponseSLATracker:
    """Track incident response SLA compliance — detect, contain, eradicate, recover, close."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._records: list[SLARecord] = []
        self._analyses: list[SLAAnalysis] = []
        logger.info(
            "response_sla_tracker.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_sla(
        self,
        name: str,
        sla_metric: SLAMetric = SLAMetric.TIME_TO_DETECT,
        sla_status: SLAStatus = SLAStatus.WITHIN_TARGET,
        sla_severity: SLASeverity = SLASeverity.MEDIUM,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SLARecord:
        record = SLARecord(
            name=name,
            sla_metric=sla_metric,
            sla_status=sla_status,
            sla_severity=sla_severity,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_sla_tracker.recorded",
            record_id=record.id,
            name=name,
            sla_metric=sla_metric.value,
            sla_status=sla_status.value,
        )
        return record

    def get_record(self, record_id: str) -> SLARecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        sla_metric: SLAMetric | None = None,
        sla_status: SLAStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SLARecord]:
        results = list(self._records)
        if sla_metric is not None:
            results = [r for r in results if r.sla_metric == sla_metric]
        if sla_status is not None:
            results = [r for r in results if r.sla_status == sla_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        sla_metric: SLAMetric = SLAMetric.TIME_TO_DETECT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SLAAnalysis:
        analysis = SLAAnalysis(
            name=name,
            sla_metric=sla_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "response_sla_tracker.analysis_added",
            name=name,
            sla_metric=sla_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_metric_distribution(self) -> dict[str, Any]:
        """Group by sla_metric; return count and avg score."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.sla_metric.value
            metric_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in metric_data.items():
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
                        "sla_metric": r.sla_metric.value,
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

    def generate_report(self) -> SLAReport:
        by_metric: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_metric[r.sla_metric.value] = by_metric.get(r.sla_metric.value, 0) + 1
            by_status[r.sla_status.value] = by_status.get(r.sla_status.value, 0) + 1
            by_severity[r.sla_severity.value] = by_severity.get(r.sla_severity.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._score_threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} SLA(s) below threshold ({self._score_threshold})")
        if self._records and avg_score < self._score_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("Response SLA metrics within healthy range")
        return SLAReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_metric=by_metric,
            by_status=by_status,
            by_severity=by_severity,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("response_sla_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.sla_metric.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "score_threshold": self._score_threshold,
            "metric_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
