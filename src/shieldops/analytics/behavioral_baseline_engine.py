"""Behavioral Baseline Engine — user/service behavioral baselines, deviation detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BaselineType(StrEnum):
    USER_BEHAVIOR = "user_behavior"
    SERVICE_BEHAVIOR = "service_behavior"
    NETWORK_TRAFFIC = "network_traffic"
    API_USAGE = "api_usage"
    DATA_ACCESS = "data_access"


class DeviationLevel(StrEnum):
    CRITICAL = "critical"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"
    NORMAL = "normal"


class BaselineStatus(StrEnum):
    ESTABLISHED = "established"
    LEARNING = "learning"
    UPDATING = "updating"
    STALE = "stale"
    INVALID = "invalid"


# --- Models ---


class BaselineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baseline_name: str = ""
    baseline_type: BaselineType = BaselineType.USER_BEHAVIOR
    deviation_level: DeviationLevel = DeviationLevel.CRITICAL
    baseline_status: BaselineStatus = BaselineStatus.ESTABLISHED
    deviation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baseline_name: str = ""
    baseline_type: BaselineType = BaselineType.USER_BEHAVIOR
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_deviation_count: int = 0
    avg_deviation_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_deviation: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_high_deviation: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BehavioralBaselineEngine:
    """User/service behavioral baselines and deviation detection."""

    def __init__(
        self,
        max_records: int = 200000,
        deviation_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._deviation_threshold = deviation_threshold
        self._records: list[BaselineRecord] = []
        self._analyses: list[BaselineAnalysis] = []
        logger.info(
            "behavioral_baseline_engine.initialized",
            max_records=max_records,
            deviation_threshold=deviation_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_baseline(
        self,
        baseline_name: str,
        baseline_type: BaselineType = BaselineType.USER_BEHAVIOR,
        deviation_level: DeviationLevel = DeviationLevel.CRITICAL,
        baseline_status: BaselineStatus = BaselineStatus.ESTABLISHED,
        deviation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BaselineRecord:
        record = BaselineRecord(
            baseline_name=baseline_name,
            baseline_type=baseline_type,
            deviation_level=deviation_level,
            baseline_status=baseline_status,
            deviation_score=deviation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "behavioral_baseline_engine.baseline_recorded",
            record_id=record.id,
            baseline_name=baseline_name,
            baseline_type=baseline_type.value,
            deviation_level=deviation_level.value,
        )
        return record

    def get_baseline(self, record_id: str) -> BaselineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_baselines(
        self,
        baseline_type: BaselineType | None = None,
        deviation_level: DeviationLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BaselineRecord]:
        results = list(self._records)
        if baseline_type is not None:
            results = [r for r in results if r.baseline_type == baseline_type]
        if deviation_level is not None:
            results = [r for r in results if r.deviation_level == deviation_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        baseline_name: str,
        baseline_type: BaselineType = BaselineType.USER_BEHAVIOR,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BaselineAnalysis:
        analysis = BaselineAnalysis(
            baseline_name=baseline_name,
            baseline_type=baseline_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "behavioral_baseline_engine.analysis_added",
            baseline_name=baseline_name,
            baseline_type=baseline_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_baseline_distribution(self) -> dict[str, Any]:
        """Group by baseline_type; return count and avg deviation_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.baseline_type.value
            src_data.setdefault(key, []).append(r.deviation_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_deviation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_deviation_baselines(self) -> list[dict[str, Any]]:
        """Return records where deviation_score > deviation_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.deviation_score > self._deviation_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "baseline_name": r.baseline_name,
                        "baseline_type": r.baseline_type.value,
                        "deviation_score": r.deviation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["deviation_score"], reverse=True)

    def rank_by_deviation(self) -> list[dict[str, Any]]:
        """Group by service, avg deviation_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.deviation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_deviation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_deviation_score"], reverse=True)
        return results

    def detect_baseline_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> BaselineReport:
        by_type: dict[str, int] = {}
        by_deviation: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.baseline_type.value] = by_type.get(r.baseline_type.value, 0) + 1
            by_deviation[r.deviation_level.value] = by_deviation.get(r.deviation_level.value, 0) + 1
            by_status[r.baseline_status.value] = by_status.get(r.baseline_status.value, 0) + 1
        high_deviation_count = sum(
            1 for r in self._records if r.deviation_score > self._deviation_threshold
        )
        scores = [r.deviation_score for r in self._records]
        avg_deviation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_deviation_baselines()
        top_high_deviation = [o["baseline_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_deviation_count > 0:
            recs.append(
                f"{high_deviation_count} baseline(s) above deviation threshold "
                f"({self._deviation_threshold})"
            )
        if self._records and avg_deviation_score > self._deviation_threshold:
            recs.append(
                f"Avg deviation score {avg_deviation_score} above threshold "
                f"({self._deviation_threshold})"
            )
        if not recs:
            recs.append("Behavioral baseline deviation is healthy")
        return BaselineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_deviation_count=high_deviation_count,
            avg_deviation_score=avg_deviation_score,
            by_type=by_type,
            by_deviation=by_deviation,
            by_status=by_status,
            top_high_deviation=top_high_deviation,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("behavioral_baseline_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.baseline_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "deviation_threshold": self._deviation_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
