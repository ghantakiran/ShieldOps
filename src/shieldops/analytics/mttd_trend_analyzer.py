"""MTTD Trend Analyzer — analyze mean-time-to-detect trends across detection sources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DetectionSource(StrEnum):
    SIEM = "siem"
    EDR = "edr"
    NDR = "ndr"
    MANUAL = "manual"
    AUTOMATED = "automated"


class MetricPeriod(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT = "insufficient"


# --- Models ---


class MTTDRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mttd_id: str = ""
    detection_source: DetectionSource = DetectionSource.SIEM
    metric_period: MetricPeriod = MetricPeriod.DAILY
    trend_direction: TrendDirection = TrendDirection.STABLE
    detection_time_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MTTDAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mttd_id: str = ""
    detection_source: DetectionSource = DetectionSource.SIEM
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MTTDReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_time_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_period: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MTTDTrendAnalyzer:
    """Analyze mean-time-to-detect trends across detection sources and periods."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_time_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_time_threshold = detection_time_threshold
        self._records: list[MTTDRecord] = []
        self._analyses: list[MTTDAnalysis] = []
        logger.info(
            "mttd_trend_analyzer.initialized",
            max_records=max_records,
            detection_time_threshold=detection_time_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mttd(
        self,
        mttd_id: str,
        detection_source: DetectionSource = DetectionSource.SIEM,
        metric_period: MetricPeriod = MetricPeriod.DAILY,
        trend_direction: TrendDirection = TrendDirection.STABLE,
        detection_time_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MTTDRecord:
        record = MTTDRecord(
            mttd_id=mttd_id,
            detection_source=detection_source,
            metric_period=metric_period,
            trend_direction=trend_direction,
            detection_time_score=detection_time_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mttd_trend_analyzer.mttd_recorded",
            record_id=record.id,
            mttd_id=mttd_id,
            detection_source=detection_source.value,
            metric_period=metric_period.value,
        )
        return record

    def get_mttd(self, record_id: str) -> MTTDRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mttds(
        self,
        detection_source: DetectionSource | None = None,
        metric_period: MetricPeriod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MTTDRecord]:
        results = list(self._records)
        if detection_source is not None:
            results = [r for r in results if r.detection_source == detection_source]
        if metric_period is not None:
            results = [r for r in results if r.metric_period == metric_period]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        mttd_id: str,
        detection_source: DetectionSource = DetectionSource.SIEM,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MTTDAnalysis:
        analysis = MTTDAnalysis(
            mttd_id=mttd_id,
            detection_source=detection_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "mttd_trend_analyzer.analysis_added",
            mttd_id=mttd_id,
            detection_source=detection_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_source_distribution(self) -> dict[str, Any]:
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.detection_source.value
            source_data.setdefault(key, []).append(r.detection_time_score)
        result: dict[str, Any] = {}
        for source, scores in source_data.items():
            result[source] = {
                "count": len(scores),
                "avg_detection_time_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_time_score < self._detection_time_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "mttd_id": r.mttd_id,
                        "detection_source": r.detection_source.value,
                        "detection_time_score": r.detection_time_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_time_score"])

    def rank_by_detection_time(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_time_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_time_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_time_score"])
        return results

    def detect_mttd_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> MTTDReport:
        by_source: dict[str, int] = {}
        by_period: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_source[r.detection_source.value] = by_source.get(r.detection_source.value, 0) + 1
            by_period[r.metric_period.value] = by_period.get(r.metric_period.value, 0) + 1
            by_trend[r.trend_direction.value] = by_trend.get(r.trend_direction.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.detection_time_score < self._detection_time_threshold
        )
        scores = [r.detection_time_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["mttd_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} detection(s) below threshold ({self._detection_time_threshold})"
            )
        if self._records and avg_score < self._detection_time_threshold:
            recs.append(
                f"Avg detection time score {avg_score} below threshold "
                f"({self._detection_time_threshold})"
            )
        if not recs:
            recs.append("MTTD trends are healthy")
        return MTTDReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_time_score=avg_score,
            by_source=by_source,
            by_period=by_period,
            by_trend=by_trend,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("mttd_trend_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.detection_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_time_threshold": self._detection_time_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
