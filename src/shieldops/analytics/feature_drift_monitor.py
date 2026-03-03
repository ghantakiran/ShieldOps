"""Feature Drift Monitor — monitor feature distribution drift in ML pipelines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FeatureType(StrEnum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    TEXT = "text"
    EMBEDDING = "embedding"


class DriftSource(StrEnum):
    UPSTREAM = "upstream"
    PIPELINE = "pipeline"
    SCHEMA = "schema"
    SEASONAL = "seasonal"
    UNKNOWN = "unknown"


class DriftStatus(StrEnum):
    DETECTED = "detected"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    ESCALATED = "escalated"


# --- Models ---


class FeatureDriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feature_name: str = ""
    model_id: str = ""
    feature_type: FeatureType = FeatureType.NUMERIC
    drift_source: DriftSource = DriftSource.UNKNOWN
    drift_status: DriftStatus = DriftStatus.MONITORING
    drift_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FeatureDriftAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feature_name: str = ""
    feature_type: FeatureType = FeatureType.NUMERIC
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FeatureDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    drifted_count: int = 0
    avg_drift_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_drifting: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class FeatureDriftMonitor:
    """Monitor feature distribution drift in ML pipelines."""

    def __init__(
        self,
        max_records: int = 200000,
        drift_threshold: float = 0.1,
    ) -> None:
        self._max_records = max_records
        self._drift_threshold = drift_threshold
        self._records: list[FeatureDriftRecord] = []
        self._analyses: list[FeatureDriftAnalysis] = []
        logger.info(
            "feature_drift_monitor.initialized",
            max_records=max_records,
            drift_threshold=drift_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_drift(
        self,
        feature_name: str,
        model_id: str = "",
        feature_type: FeatureType = FeatureType.NUMERIC,
        drift_source: DriftSource = DriftSource.UNKNOWN,
        drift_status: DriftStatus = DriftStatus.MONITORING,
        drift_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FeatureDriftRecord:
        record = FeatureDriftRecord(
            feature_name=feature_name,
            model_id=model_id,
            feature_type=feature_type,
            drift_source=drift_source,
            drift_status=drift_status,
            drift_score=drift_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "feature_drift_monitor.drift_recorded",
            record_id=record.id,
            feature_name=feature_name,
            feature_type=feature_type.value,
        )
        return record

    def get_drift(self, record_id: str) -> FeatureDriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
        self,
        feature_type: FeatureType | None = None,
        drift_status: DriftStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FeatureDriftRecord]:
        results = list(self._records)
        if feature_type is not None:
            results = [r for r in results if r.feature_type == feature_type]
        if drift_status is not None:
            results = [r for r in results if r.drift_status == drift_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        feature_name: str,
        feature_type: FeatureType = FeatureType.NUMERIC,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FeatureDriftAnalysis:
        analysis = FeatureDriftAnalysis(
            feature_name=feature_name,
            feature_type=feature_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "feature_drift_monitor.analysis_added",
            feature_name=feature_name,
            feature_type=feature_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by feature_type; return count and avg drift_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.feature_type.value
            type_data.setdefault(key, []).append(r.drift_score)
        result: dict[str, Any] = {}
        for ftype, scores in type_data.items():
            result[ftype] = {
                "count": len(scores),
                "avg_drift_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where drift_score > drift_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.drift_score > self._drift_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "feature_name": r.feature_name,
                        "feature_type": r.feature_type.value,
                        "drift_score": r.drift_score,
                        "model_id": r.model_id,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["drift_score"], reverse=True)

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by feature_name, avg drift_score, sort descending."""
        feat_scores: dict[str, list[float]] = {}
        for r in self._records:
            feat_scores.setdefault(r.feature_name, []).append(r.drift_score)
        results: list[dict[str, Any]] = []
        for feat, scores in feat_scores.items():
            results.append(
                {
                    "feature_name": feat,
                    "avg_drift_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_drift_score"], reverse=True)
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

    def generate_report(self) -> FeatureDriftReport:
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.feature_type.value] = by_type.get(r.feature_type.value, 0) + 1
            by_source[r.drift_source.value] = by_source.get(r.drift_source.value, 0) + 1
            by_status[r.drift_status.value] = by_status.get(r.drift_status.value, 0) + 1
        drifted_count = sum(1 for r in self._records if r.drift_score > self._drift_threshold)
        scores = [r.drift_score for r in self._records]
        avg_drift_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        severe_list = self.identify_severe_drifts()
        top_drifting = [o["feature_name"] for o in severe_list[:5]]
        recs: list[str] = []
        if self._records and drifted_count > 0:
            recs.append(
                f"{drifted_count} feature(s) exceeding drift threshold ({self._drift_threshold})"
            )
        if self._records and avg_drift_score > self._drift_threshold:
            recs.append(
                f"Avg drift score {avg_drift_score} exceeds threshold ({self._drift_threshold})"
            )
        if not recs:
            recs.append("Feature drift is within acceptable bounds")
        return FeatureDriftReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            drifted_count=drifted_count,
            avg_drift_score=avg_drift_score,
            by_type=by_type,
            by_source=by_source,
            by_status=by_status,
            top_drifting=top_drifting,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("feature_drift_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.feature_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "drift_threshold": self._drift_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_features": len({r.feature_name for r in self._records}),
        }
