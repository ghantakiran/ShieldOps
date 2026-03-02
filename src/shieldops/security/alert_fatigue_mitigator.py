"""Alert Fatigue Mitigator — reduce alert fatigue through intelligent mitigation strategies."""

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
    VOLUME_OVERLOAD = "volume_overload"
    REPETITIVE_ALERTS = "repetitive_alerts"
    LOW_FIDELITY = "low_fidelity"
    POOR_CONTEXT = "poor_context"
    IRRELEVANT = "irrelevant"


class MitigationStrategy(StrEnum):
    AGGREGATION = "aggregation"
    DEDUPLICATION = "deduplication"
    PRIORITIZATION = "prioritization"
    SUPPRESSION = "suppression"
    ENRICHMENT = "enrichment"


class FatigueLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    HEALTHY = "healthy"


# --- Models ---


class FatigueRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = ""
    fatigue_source: FatigueSource = FatigueSource.VOLUME_OVERLOAD
    mitigation_strategy: MitigationStrategy = MitigationStrategy.AGGREGATION
    fatigue_level: FatigueLevel = FatigueLevel.MODERATE
    fatigue_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FatigueAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = ""
    fatigue_source: FatigueSource = FatigueSource.VOLUME_OVERLOAD
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
    avg_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertFatigueMitigator:
    """Reduce alert fatigue through intelligent mitigation strategies and scoring."""

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
            "alert_fatigue_mitigator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_fatigue(
        self,
        source_name: str,
        fatigue_source: FatigueSource = FatigueSource.VOLUME_OVERLOAD,
        mitigation_strategy: MitigationStrategy = MitigationStrategy.AGGREGATION,
        fatigue_level: FatigueLevel = FatigueLevel.MODERATE,
        fatigue_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FatigueRecord:
        record = FatigueRecord(
            source_name=source_name,
            fatigue_source=fatigue_source,
            mitigation_strategy=mitigation_strategy,
            fatigue_level=fatigue_level,
            fatigue_score=fatigue_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_fatigue_mitigator.fatigue_recorded",
            record_id=record.id,
            source_name=source_name,
            fatigue_source=fatigue_source.value,
            mitigation_strategy=mitigation_strategy.value,
        )
        return record

    def get_record(self, record_id: str) -> FatigueRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        fatigue_source: FatigueSource | None = None,
        mitigation_strategy: MitigationStrategy | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FatigueRecord]:
        results = list(self._records)
        if fatigue_source is not None:
            results = [r for r in results if r.fatigue_source == fatigue_source]
        if mitigation_strategy is not None:
            results = [r for r in results if r.mitigation_strategy == mitigation_strategy]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        source_name: str,
        fatigue_source: FatigueSource = FatigueSource.VOLUME_OVERLOAD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FatigueAnalysis:
        analysis = FatigueAnalysis(
            source_name=source_name,
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
            "alert_fatigue_mitigator.analysis_added",
            source_name=source_name,
            fatigue_source=fatigue_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by fatigue_source; return count and avg fatigue_score."""
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.fatigue_source.value
            source_data.setdefault(key, []).append(r.fatigue_score)
        result: dict[str, Any] = {}
        for source, scores in source_data.items():
            result[source] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where fatigue_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.fatigue_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "source_name": r.source_name,
                        "fatigue_source": r.fatigue_source.value,
                        "fatigue_score": r.fatigue_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["fatigue_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg fatigue_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.fatigue_score)
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

    def generate_report(self) -> FatigueReport:
        by_source: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_source[r.fatigue_source.value] = by_source.get(r.fatigue_source.value, 0) + 1
            by_strategy[r.mitigation_strategy.value] = (
                by_strategy.get(r.mitigation_strategy.value, 0) + 1
            )
            by_level[r.fatigue_level.value] = by_level.get(r.fatigue_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.fatigue_score < self._threshold)
        scores = [r.fatigue_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["source_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} source(s) below fatigue mitigation threshold ({self._threshold})"
            )
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg fatigue score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Alert fatigue mitigation is healthy")
        return FatigueReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_source=by_source,
            by_strategy=by_strategy,
            by_level=by_level,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("alert_fatigue_mitigator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.fatigue_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
