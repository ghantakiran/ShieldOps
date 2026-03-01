"""Reliability Metrics Collector — collect reliability metrics, track service reliability."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MetricType(StrEnum):
    MTTR = "mttr"
    MTBF = "mtbf"
    CHANGE_FAILURE_RATE = "change_failure_rate"
    DEPLOYMENT_FREQUENCY = "deployment_frequency"
    AVAILABILITY = "availability"


class ReliabilityTier(StrEnum):
    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRELIABLE = "unreliable"


class MetricSource(StrEnum):
    INCIDENT_DATA = "incident_data"
    DEPLOYMENT_DATA = "deployment_data"
    MONITORING = "monitoring"
    SLO_TRACKING = "slo_tracking"
    MANUAL_ENTRY = "manual_entry"


# --- Models ---


class ReliabilityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    metric_type: MetricType = MetricType.MTTR
    reliability_tier: ReliabilityTier = ReliabilityTier.UNRELIABLE
    metric_source: MetricSource = MetricSource.INCIDENT_DATA
    reliability_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_point_name: str = ""
    metric_type: MetricType = MetricType.MTTR
    value: float = 0.0
    samples_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReliabilityMetricsReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_data_points: int = 0
    reliable_services: int = 0
    avg_reliability_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    low_reliability: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReliabilityMetricsCollector:
    """Collect reliability metrics, identify low-reliability services, track trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_reliability_score: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_reliability_score = min_reliability_score
        self._records: list[ReliabilityRecord] = []
        self._data_points: list[MetricDataPoint] = []
        logger.info(
            "reliability_metrics.initialized",
            max_records=max_records,
            min_reliability_score=min_reliability_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_metric(
        self,
        service_id: str,
        metric_type: MetricType = MetricType.MTTR,
        reliability_tier: ReliabilityTier = ReliabilityTier.UNRELIABLE,
        metric_source: MetricSource = MetricSource.INCIDENT_DATA,
        reliability_score: float = 0.0,
        team: str = "",
    ) -> ReliabilityRecord:
        record = ReliabilityRecord(
            service_id=service_id,
            metric_type=metric_type,
            reliability_tier=reliability_tier,
            metric_source=metric_source,
            reliability_score=reliability_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reliability_metrics.metric_recorded",
            record_id=record.id,
            service_id=service_id,
            metric_type=metric_type.value,
            reliability_tier=reliability_tier.value,
        )
        return record

    def get_metric(self, record_id: str) -> ReliabilityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_metrics(
        self,
        metric_type: MetricType | None = None,
        reliability_tier: ReliabilityTier | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReliabilityRecord]:
        results = list(self._records)
        if metric_type is not None:
            results = [r for r in results if r.metric_type == metric_type]
        if reliability_tier is not None:
            results = [r for r in results if r.reliability_tier == reliability_tier]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_data_point(
        self,
        data_point_name: str,
        metric_type: MetricType = MetricType.MTTR,
        value: float = 0.0,
        samples_count: int = 0,
        description: str = "",
    ) -> MetricDataPoint:
        dp = MetricDataPoint(
            data_point_name=data_point_name,
            metric_type=metric_type,
            value=value,
            samples_count=samples_count,
            description=description,
        )
        self._data_points.append(dp)
        if len(self._data_points) > self._max_records:
            self._data_points = self._data_points[-self._max_records :]
        logger.info(
            "reliability_metrics.data_point_added",
            data_point_name=data_point_name,
            metric_type=metric_type.value,
            value=value,
        )
        return dp

    # -- domain operations --------------------------------------------------

    def analyze_reliability_trends(self) -> dict[str, Any]:
        """Group by metric_type; return count and avg reliability_score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.metric_type.value
            type_data.setdefault(key, []).append(r.reliability_score)
        result: dict[str, Any] = {}
        for mtype, scores in type_data.items():
            result[mtype] = {
                "count": len(scores),
                "avg_reliability_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_reliability_services(self) -> list[dict[str, Any]]:
        """Return records where reliability_score < min_reliability_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.reliability_score < self._min_reliability_score:
                results.append(
                    {
                        "record_id": r.id,
                        "service_id": r.service_id,
                        "reliability_score": r.reliability_score,
                        "metric_type": r.metric_type.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_reliability_score(self) -> list[dict[str, Any]]:
        """Group by team, total reliability_score, sort descending."""
        team_scores: dict[str, float] = {}
        for r in self._records:
            team_scores[r.team] = team_scores.get(r.team, 0) + r.reliability_score
        results: list[dict[str, Any]] = []
        for team, total in team_scores.items():
            results.append(
                {
                    "team": team,
                    "total_reliability": total,
                }
            )
        results.sort(key=lambda x: x["total_reliability"], reverse=True)
        return results

    def detect_reliability_regression(self) -> dict[str, Any]:
        """Split-half on reliability_score; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.reliability_score for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ReliabilityMetricsReport:
        by_type: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_type[r.metric_type.value] = by_type.get(r.metric_type.value, 0) + 1
            by_tier[r.reliability_tier.value] = by_tier.get(r.reliability_tier.value, 0) + 1
            by_source[r.metric_source.value] = by_source.get(r.metric_source.value, 0) + 1
        low_count = sum(
            1 for r in self._records if r.reliability_score < self._min_reliability_score
        )
        reliable_services = len({r.service_id for r in self._records if r.reliability_score > 0})
        avg_rel = (
            round(sum(r.reliability_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        low_ids = [
            r.service_id for r in self._records if r.reliability_score < self._min_reliability_score
        ][:5]
        recs: list[str] = []
        if low_count > 0:
            recs.append(
                f"{low_count} service(s) below minimum reliability ({self._min_reliability_score})"
            )
        if self._records and avg_rel < self._min_reliability_score:
            recs.append(
                f"Average reliability {avg_rel} is below threshold ({self._min_reliability_score})"
            )
        if not recs:
            recs.append("Reliability metrics levels are healthy")
        return ReliabilityMetricsReport(
            total_records=len(self._records),
            total_data_points=len(self._data_points),
            reliable_services=reliable_services,
            avg_reliability_score=avg_rel,
            by_type=by_type,
            by_tier=by_tier,
            by_source=by_source,
            low_reliability=low_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._data_points.clear()
        logger.info("reliability_metrics.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.metric_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_data_points": len(self._data_points),
            "min_reliability_score": self._min_reliability_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_id for r in self._records}),
        }
