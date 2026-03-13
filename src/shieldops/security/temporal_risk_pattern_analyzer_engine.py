"""Temporal Risk Pattern Analyzer Engine —
analyze temporal patterns in risk data,
detect risk periodicity, forecast risk windows."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TemporalPattern(StrEnum):
    PERIODIC = "periodic"
    BURST = "burst"
    GRADUAL = "gradual"
    SEASONAL = "seasonal"


class TimeWindow(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PatternSignificance(StrEnum):
    HIGHLY_SIGNIFICANT = "highly_significant"
    SIGNIFICANT = "significant"
    MARGINAL = "marginal"
    INSIGNIFICANT = "insignificant"


# --- Models ---


class TemporalRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    temporal_pattern: TemporalPattern = TemporalPattern.PERIODIC
    time_window: TimeWindow = TimeWindow.DAILY
    significance: PatternSignificance = PatternSignificance.MARGINAL
    risk_score: float = 0.0
    pattern_frequency: float = 0.0
    peak_risk_hour: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TemporalRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    temporal_pattern: TemporalPattern = TemporalPattern.PERIODIC
    composite_risk: float = 0.0
    periodicity_confirmed: bool = False
    forecast_window: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TemporalRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_temporal_pattern: dict[str, int] = Field(default_factory=dict)
    by_time_window: dict[str, int] = Field(default_factory=dict)
    by_significance: dict[str, int] = Field(default_factory=dict)
    high_risk_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TemporalRiskPatternAnalyzerEngine:
    """Analyze temporal patterns in risk data, detect risk periodicity,
    and forecast risk windows."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TemporalRiskRecord] = []
        self._analyses: dict[str, TemporalRiskAnalysis] = {}
        logger.info(
            "temporal_risk_pattern_analyzer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        entity_id: str = "",
        temporal_pattern: TemporalPattern = TemporalPattern.PERIODIC,
        time_window: TimeWindow = TimeWindow.DAILY,
        significance: PatternSignificance = PatternSignificance.MARGINAL,
        risk_score: float = 0.0,
        pattern_frequency: float = 0.0,
        peak_risk_hour: int = 0,
        description: str = "",
    ) -> TemporalRiskRecord:
        record = TemporalRiskRecord(
            entity_id=entity_id,
            temporal_pattern=temporal_pattern,
            time_window=time_window,
            significance=significance,
            risk_score=risk_score,
            pattern_frequency=pattern_frequency,
            peak_risk_hour=peak_risk_hour,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "temporal_risk_pattern.record_added",
            record_id=record.id,
            entity_id=entity_id,
        )
        return record

    def process(self, key: str) -> TemporalRiskAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sig_weights = {
            "highly_significant": 4,
            "significant": 3,
            "marginal": 2,
            "insignificant": 1,
        }
        w = sig_weights.get(rec.significance.value, 1)
        composite = round(w * rec.risk_score * (1 + rec.pattern_frequency * 0.1), 2)
        periodic = rec.temporal_pattern in (TemporalPattern.PERIODIC, TemporalPattern.SEASONAL)
        forecast = f"{rec.time_window.value}_window_peak_hour_{rec.peak_risk_hour}"
        analysis = TemporalRiskAnalysis(
            entity_id=rec.entity_id,
            temporal_pattern=rec.temporal_pattern,
            composite_risk=composite,
            periodicity_confirmed=periodic,
            forecast_window=forecast,
            description=(
                f"Entity {rec.entity_id} pattern={rec.temporal_pattern.value} "
                f"window={rec.time_window.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TemporalRiskReport:
        by_tp: dict[str, int] = {}
        by_tw: dict[str, int] = {}
        by_sg: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.temporal_pattern.value
            by_tp[k] = by_tp.get(k, 0) + 1
            k2 = r.time_window.value
            by_tw[k2] = by_tw.get(k2, 0) + 1
            k3 = r.significance.value
            by_sg[k3] = by_sg.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_risk = list(
            {
                r.entity_id
                for r in self._records
                if r.significance
                in (
                    PatternSignificance.HIGHLY_SIGNIFICANT,
                    PatternSignificance.SIGNIFICANT,
                )
                and r.risk_score > 0.6
            }
        )[:10]
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} entities with significant temporal risk patterns")
        if not recs:
            recs.append("No significant temporal risk patterns detected")
        return TemporalRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_temporal_pattern=by_tp,
            by_time_window=by_tw,
            by_significance=by_sg,
            high_risk_entities=high_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        tp_dist: dict[str, int] = {}
        for r in self._records:
            k = r.temporal_pattern.value
            tp_dist[k] = tp_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "temporal_pattern_distribution": tp_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("temporal_risk_pattern_analyzer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def analyze_temporal_patterns(self) -> list[dict[str, Any]]:
        """Analyze temporal risk patterns grouped by entity and time window."""
        entity_window_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            ew_key = f"{r.entity_id}:{r.time_window.value}"
            if ew_key not in entity_window_data:
                entity_window_data[ew_key] = {
                    "entity_id": r.entity_id,
                    "time_window": r.time_window.value,
                    "records": [],
                }
            entity_window_data[ew_key]["records"].append(r)
        results: list[dict[str, Any]] = []
        for ew_key, data in entity_window_data.items():
            recs = data["records"]
            avg_risk = sum(rec.risk_score for rec in recs) / len(recs)
            patterns = list({rec.temporal_pattern.value for rec in recs})
            peak_hours = [rec.peak_risk_hour for rec in recs if rec.peak_risk_hour > 0]
            results.append(
                {
                    "key": ew_key,
                    "entity_id": data["entity_id"],
                    "time_window": data["time_window"],
                    "avg_risk_score": round(avg_risk, 2),
                    "patterns": patterns,
                    "common_peak_hour": (
                        max(set(peak_hours), key=peak_hours.count) if peak_hours else 0
                    ),
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_periodicity(self) -> list[dict[str, Any]]:
        """Detect entities with confirmed periodic risk patterns."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.temporal_pattern in (TemporalPattern.PERIODIC, TemporalPattern.SEASONAL)
                and r.significance
                in (
                    PatternSignificance.HIGHLY_SIGNIFICANT,
                    PatternSignificance.SIGNIFICANT,
                )
                and r.entity_id not in seen
            ):
                seen.add(r.entity_id)
                results.append(
                    {
                        "entity_id": r.entity_id,
                        "pattern": r.temporal_pattern.value,
                        "time_window": r.time_window.value,
                        "significance": r.significance.value,
                        "pattern_frequency": r.pattern_frequency,
                        "peak_risk_hour": r.peak_risk_hour,
                    }
                )
        results.sort(key=lambda x: x["pattern_frequency"], reverse=True)
        return results

    def forecast_risk_windows(self) -> list[dict[str, Any]]:
        """Forecast upcoming risk windows per entity."""
        entity_data: dict[str, list[TemporalRiskRecord]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r)
        results: list[dict[str, Any]] = []
        for eid, recs in entity_data.items():
            max_risk = max(rec.risk_score for rec in recs)
            avg_freq = sum(rec.pattern_frequency for rec in recs) / len(recs)
            peak_hours = [rec.peak_risk_hour for rec in recs if rec.peak_risk_hour > 0]
            common_peak = max(set(peak_hours), key=peak_hours.count) if peak_hours else 0
            dominant_window = max(recs, key=lambda x: x.risk_score).time_window.value
            results.append(
                {
                    "entity_id": eid,
                    "forecast_peak_risk": round(max_risk, 2),
                    "avg_pattern_frequency": round(avg_freq, 2),
                    "predicted_peak_hour": common_peak,
                    "dominant_window": dominant_window,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["forecast_peak_risk"], reverse=True)
        return results
