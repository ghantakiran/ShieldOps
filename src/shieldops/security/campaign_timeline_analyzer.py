"""Campaign Timeline Analyzer — analyze and reconstruct campaign timelines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TimelinePhase(StrEnum):
    RECONNAISSANCE = "reconnaissance"
    WEAPONIZATION = "weaponization"
    DELIVERY = "delivery"
    EXPLOITATION = "exploitation"
    INSTALLATION = "installation"


class TimelineResolution(StrEnum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AnalysisDepth(StrEnum):
    SURFACE = "surface"
    STANDARD = "standard"
    DEEP = "deep"
    FORENSIC = "forensic"
    COMPREHENSIVE = "comprehensive"


# --- Models ---


class TimelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    timeline_phase: TimelinePhase = TimelinePhase.RECONNAISSANCE
    timeline_resolution: TimelineResolution = TimelineResolution.DAY
    analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD
    timeline_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TimelineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    timeline_phase: TimelinePhase = TimelinePhase.RECONNAISSANCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TimelineAnalysisReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_timeline_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_resolution: dict[str, int] = Field(default_factory=dict)
    by_depth: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CampaignTimelineAnalyzer:
    """Analyze and reconstruct campaign timelines across kill chain phases."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[TimelineRecord] = []
        self._analyses: list[TimelineAnalysis] = []
        logger.info(
            "campaign_timeline_analyzer.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_timeline(
        self,
        campaign_name: str,
        timeline_phase: TimelinePhase = TimelinePhase.RECONNAISSANCE,
        timeline_resolution: TimelineResolution = TimelineResolution.DAY,
        analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD,
        timeline_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TimelineRecord:
        record = TimelineRecord(
            campaign_name=campaign_name,
            timeline_phase=timeline_phase,
            timeline_resolution=timeline_resolution,
            analysis_depth=analysis_depth,
            timeline_score=timeline_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "campaign_timeline_analyzer.recorded",
            record_id=record.id,
            campaign_name=campaign_name,
            timeline_phase=timeline_phase.value,
        )
        return record

    def get_record(self, record_id: str) -> TimelineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        timeline_phase: TimelinePhase | None = None,
        timeline_resolution: TimelineResolution | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TimelineRecord]:
        results = list(self._records)
        if timeline_phase is not None:
            results = [r for r in results if r.timeline_phase == timeline_phase]
        if timeline_resolution is not None:
            results = [r for r in results if r.timeline_resolution == timeline_resolution]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        campaign_name: str,
        timeline_phase: TimelinePhase = TimelinePhase.RECONNAISSANCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TimelineAnalysis:
        analysis = TimelineAnalysis(
            campaign_name=campaign_name,
            timeline_phase=timeline_phase,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "campaign_timeline_analyzer.analysis_added",
            campaign_name=campaign_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_phase_distribution(self) -> dict[str, Any]:
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.timeline_phase.value
            phase_data.setdefault(key, []).append(r.timeline_score)
        result: dict[str, Any] = {}
        for phase, scores in phase_data.items():
            result[phase] = {
                "count": len(scores),
                "avg_timeline_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.timeline_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "campaign_name": r.campaign_name,
                        "timeline_phase": r.timeline_phase.value,
                        "timeline_score": r.timeline_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["timeline_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.timeline_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_timeline_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_timeline_score"])
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

    def generate_report(self) -> TimelineAnalysisReport:
        by_phase: dict[str, int] = {}
        by_resolution: dict[str, int] = {}
        by_depth: dict[str, int] = {}
        for r in self._records:
            by_phase[r.timeline_phase.value] = by_phase.get(r.timeline_phase.value, 0) + 1
            by_resolution[r.timeline_resolution.value] = (
                by_resolution.get(r.timeline_resolution.value, 0) + 1
            )
            by_depth[r.analysis_depth.value] = by_depth.get(r.analysis_depth.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.timeline_score < self._quality_threshold)
        scores = [r.timeline_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["campaign_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} timeline(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg timeline score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Campaign timeline analysis is healthy")
        return TimelineAnalysisReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_timeline_score=avg_score,
            by_phase=by_phase,
            by_resolution=by_resolution,
            by_depth=by_depth,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("campaign_timeline_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.timeline_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "phase_distribution": phase_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
