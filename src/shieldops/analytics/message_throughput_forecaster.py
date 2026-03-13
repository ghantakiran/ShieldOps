"""Message Throughput Forecaster —
forecast throughput demand, detect bottlenecks,
rank topics by scaling urgency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastWindow(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BottleneckType(StrEnum):
    PRODUCER = "producer"
    BROKER = "broker"
    CONSUMER = "consumer"
    NETWORK = "network"


class ScalingUrgency(StrEnum):
    IMMEDIATE = "immediate"
    SOON = "soon"
    PLANNED = "planned"
    NONE = "none"


# --- Models ---


class ThroughputRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic_name: str = ""
    forecast_window: ForecastWindow = ForecastWindow.HOURLY
    bottleneck_type: BottleneckType = BottleneckType.BROKER
    scaling_urgency: ScalingUrgency = ScalingUrgency.NONE
    current_throughput: float = 0.0
    peak_throughput: float = 0.0
    capacity_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThroughputAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic_name: str = ""
    forecast_window: ForecastWindow = ForecastWindow.HOURLY
    forecast_demand: float = 0.0
    bottleneck_detected: bool = False
    scaling_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThroughputReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_throughput: float = 0.0
    by_window: dict[str, int] = Field(default_factory=dict)
    by_bottleneck: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    urgent_topics: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MessageThroughputForecaster:
    """Forecast throughput demand, detect bottlenecks,
    rank topics by scaling urgency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ThroughputRecord] = []
        self._analyses: dict[str, ThroughputAnalysis] = {}
        logger.info(
            "message_throughput_forecaster.init",
            max_records=max_records,
        )

    def add_record(
        self,
        topic_name: str = "",
        forecast_window: ForecastWindow = (ForecastWindow.HOURLY),
        bottleneck_type: BottleneckType = (BottleneckType.BROKER),
        scaling_urgency: ScalingUrgency = (ScalingUrgency.NONE),
        current_throughput: float = 0.0,
        peak_throughput: float = 0.0,
        capacity_pct: float = 0.0,
        description: str = "",
    ) -> ThroughputRecord:
        record = ThroughputRecord(
            topic_name=topic_name,
            forecast_window=forecast_window,
            bottleneck_type=bottleneck_type,
            scaling_urgency=scaling_urgency,
            current_throughput=current_throughput,
            peak_throughput=peak_throughput,
            capacity_pct=capacity_pct,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "throughput_forecaster.record_added",
            record_id=record.id,
            topic_name=topic_name,
        )
        return record

    def process(self, key: str) -> ThroughputAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        forecast = round(rec.current_throughput * 1.2, 2)
        bottleneck = rec.capacity_pct > 80.0
        scaling = round(rec.capacity_pct * 1.25, 2)
        analysis = ThroughputAnalysis(
            topic_name=rec.topic_name,
            forecast_window=rec.forecast_window,
            forecast_demand=forecast,
            bottleneck_detected=bottleneck,
            scaling_score=scaling,
            description=(f"Topic {rec.topic_name} forecast {forecast}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ThroughputReport:
        by_w: dict[str, int] = {}
        by_b: dict[str, int] = {}
        by_u: dict[str, int] = {}
        thrpts: list[float] = []
        for r in self._records:
            k = r.forecast_window.value
            by_w[k] = by_w.get(k, 0) + 1
            k2 = r.bottleneck_type.value
            by_b[k2] = by_b.get(k2, 0) + 1
            k3 = r.scaling_urgency.value
            by_u[k3] = by_u.get(k3, 0) + 1
            thrpts.append(r.current_throughput)
        avg = round(sum(thrpts) / len(thrpts), 2) if thrpts else 0.0
        urgent = list(
            {
                r.topic_name
                for r in self._records
                if r.scaling_urgency
                in (
                    ScalingUrgency.IMMEDIATE,
                    ScalingUrgency.SOON,
                )
            }
        )[:10]
        recs: list[str] = []
        if urgent:
            recs.append(f"{len(urgent)} topics need scaling")
        if not recs:
            recs.append("Throughput capacity adequate")
        return ThroughputReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_throughput=avg,
            by_window=by_w,
            by_bottleneck=by_b,
            by_urgency=by_u,
            urgent_topics=urgent,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        w_dist: dict[str, int] = {}
        for r in self._records:
            k = r.forecast_window.value
            w_dist[k] = w_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "window_distribution": w_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("message_throughput_forecaster.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def forecast_throughput_demand(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast throughput demand per topic."""
        topic_data: dict[str, list[float]] = {}
        for r in self._records:
            topic_data.setdefault(r.topic_name, []).append(r.current_throughput)
        results: list[dict[str, Any]] = []
        for tn, thrpts in topic_data.items():
            avg = sum(thrpts) / len(thrpts)
            forecast = round(avg * 1.2, 2)
            results.append(
                {
                    "topic_name": tn,
                    "avg_throughput": round(avg, 2),
                    "forecast_demand": forecast,
                    "peak": round(max(thrpts), 2),
                    "samples": len(thrpts),
                }
            )
        results.sort(
            key=lambda x: x["forecast_demand"],
            reverse=True,
        )
        return results

    def detect_throughput_bottlenecks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect throughput bottlenecks."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.capacity_pct > 80.0 and r.topic_name not in seen:
                seen.add(r.topic_name)
                results.append(
                    {
                        "topic_name": r.topic_name,
                        "bottleneck_type": (r.bottleneck_type.value),
                        "capacity_pct": (r.capacity_pct),
                        "current_throughput": (r.current_throughput),
                    }
                )
        results.sort(
            key=lambda x: x["capacity_pct"],
            reverse=True,
        )
        return results

    def rank_topics_by_scaling_urgency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank topics by scaling urgency."""
        urgency_weights = {
            "immediate": 4,
            "soon": 3,
            "planned": 2,
            "none": 1,
        }
        topic_scores: dict[str, float] = {}
        for r in self._records:
            w = urgency_weights.get(r.scaling_urgency.value, 1)
            score = w * r.capacity_pct
            topic_scores[r.topic_name] = topic_scores.get(r.topic_name, 0.0) + score
        results: list[dict[str, Any]] = []
        for tn, score in topic_scores.items():
            results.append(
                {
                    "topic_name": tn,
                    "urgency_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["urgency_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
