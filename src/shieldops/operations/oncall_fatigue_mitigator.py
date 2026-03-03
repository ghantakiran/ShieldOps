"""Oncall Fatigue Mitigator — detect and mitigate on-call fatigue."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FatigueSource(StrEnum):
    ALERT_VOLUME = "alert_volume"
    NIGHT_PAGES = "night_pages"
    WEEKEND_PAGES = "weekend_pages"
    LONG_INCIDENTS = "long_incidents"
    CONSECUTIVE_SHIFTS = "consecutive_shifts"


class MitigationAction(StrEnum):
    REDISTRIBUTE = "redistribute"
    SUPPRESS = "suppress"
    AUTOMATE = "automate"
    ESCALATE = "escalate"
    BUFFER = "buffer"


class FatigueLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class FatigueRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    team: str = ""
    fatigue_source: FatigueSource = FatigueSource.ALERT_VOLUME
    mitigation_action: MitigationAction = MitigationAction.REDISTRIBUTE
    fatigue_level: FatigueLevel = FatigueLevel.MINIMAL
    fatigue_score: float = 0.0
    page_count: int = 0
    created_at: float = Field(default_factory=time.time)


class FatigueAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    fatigue_source: FatigueSource = FatigueSource.ALERT_VOLUME
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FatigueReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_fatigue_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OncallFatigueMitigator:
    """Detect on-call fatigue sources and recommend mitigation actions."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[FatigueRecord] = []
        self._analyses: list[FatigueAnalysis] = []
        logger.info(
            "oncall_fatigue_mitigator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_fatigue(
        self,
        engineer: str,
        team: str = "",
        fatigue_source: FatigueSource = FatigueSource.ALERT_VOLUME,
        mitigation_action: MitigationAction = MitigationAction.REDISTRIBUTE,
        fatigue_level: FatigueLevel = FatigueLevel.MINIMAL,
        fatigue_score: float = 0.0,
        page_count: int = 0,
    ) -> FatigueRecord:
        record = FatigueRecord(
            engineer=engineer,
            team=team,
            fatigue_source=fatigue_source,
            mitigation_action=mitigation_action,
            fatigue_level=fatigue_level,
            fatigue_score=fatigue_score,
            page_count=page_count,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "oncall_fatigue_mitigator.fatigue_recorded",
            record_id=record.id,
            engineer=engineer,
            fatigue_source=fatigue_source.value,
            fatigue_level=fatigue_level.value,
        )
        return record

    def get_fatigue(self, record_id: str) -> FatigueRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_fatigues(
        self,
        fatigue_source: FatigueSource | None = None,
        fatigue_level: FatigueLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FatigueRecord]:
        results = list(self._records)
        if fatigue_source is not None:
            results = [r for r in results if r.fatigue_source == fatigue_source]
        if fatigue_level is not None:
            results = [r for r in results if r.fatigue_level == fatigue_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        engineer: str,
        fatigue_source: FatigueSource = FatigueSource.ALERT_VOLUME,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FatigueAnalysis:
        analysis = FatigueAnalysis(
            engineer=engineer,
            fatigue_source=fatigue_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "oncall_fatigue_mitigator.analysis_added",
            engineer=engineer,
            fatigue_source=fatigue_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by fatigue_source; return count and avg fatigue_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.fatigue_source.value
            src_data.setdefault(key, []).append(r.fatigue_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_fatigue_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_fatigue_gaps(self) -> list[dict[str, Any]]:
        """Return records where fatigue_score >= threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.fatigue_score >= self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "engineer": r.engineer,
                        "fatigue_source": r.fatigue_source.value,
                        "fatigue_score": r.fatigue_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["fatigue_score"], reverse=True)

    def rank_by_fatigue(self) -> list[dict[str, Any]]:
        """Group by engineer, avg fatigue_score, sort descending."""
        eng_scores: dict[str, list[float]] = {}
        for r in self._records:
            eng_scores.setdefault(r.engineer, []).append(r.fatigue_score)
        results: list[dict[str, Any]] = []
        for engineer, scores in eng_scores.items():
            results.append(
                {
                    "engineer": engineer,
                    "avg_fatigue_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_fatigue_score"], reverse=True)
        return results

    def detect_fatigue_trends(self) -> dict[str, Any]:
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
            trend = "worsening"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> FatigueReport:
        by_source: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_source[r.fatigue_source.value] = by_source.get(r.fatigue_source.value, 0) + 1
            by_action[r.mitigation_action.value] = by_action.get(r.mitigation_action.value, 0) + 1
            by_level[r.fatigue_level.value] = by_level.get(r.fatigue_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.fatigue_score >= self._threshold)
        scores = [r.fatigue_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_fatigue_gaps()
        top_gaps = [o["engineer"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} engineer(s) above fatigue threshold ({self._threshold})")
        if self._records and avg_score >= self._threshold:
            recs.append(f"Avg fatigue score {avg_score} at or above threshold ({self._threshold})")
        if not recs:
            recs.append("Oncall fatigue is at healthy levels")
        return FatigueReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_fatigue_score=avg_score,
            by_source=by_source,
            by_action=by_action,
            by_level=by_level,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("oncall_fatigue_mitigator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        src_dist: dict[str, int] = {}
        for r in self._records:
            key = r.fatigue_source.value
            src_dist[key] = src_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "source_distribution": src_dist,
            "unique_engineers": len({r.engineer for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
