"""Model Drift Detector — detect and analyze ML model drift over time."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftType(StrEnum):
    DATA = "data"
    CONCEPT = "concept"
    PREDICTION = "prediction"
    FEATURE = "feature"
    PERFORMANCE = "performance"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class DetectionMethod(StrEnum):
    KS_TEST = "ks_test"
    PSI = "psi"
    WASSERSTEIN = "wasserstein"
    CHI_SQUARE = "chi_square"
    ADWIN = "adwin"


# --- Models ---


class DriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    drift_type: DriftType = DriftType.DATA
    drift_severity: DriftSeverity = DriftSeverity.LOW
    detection_method: DetectionMethod = DetectionMethod.KS_TEST
    drift_score: float = 0.0
    feature_name: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    drift_type: DriftType = DriftType.DATA
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    severe_count: int = 0
    avg_drift_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_drifting: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ModelDriftDetector:
    """Detect and analyze ML model drift over time."""

    def __init__(
        self,
        max_records: int = 200000,
        drift_threshold: float = 0.05,
    ) -> None:
        self._max_records = max_records
        self._drift_threshold = drift_threshold
        self._records: list[DriftRecord] = []
        self._analyses: list[DriftAnalysis] = []
        logger.info(
            "model_drift_detector.initialized",
            max_records=max_records,
            drift_threshold=drift_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_drift(
        self,
        model_id: str,
        drift_type: DriftType = DriftType.DATA,
        drift_severity: DriftSeverity = DriftSeverity.LOW,
        detection_method: DetectionMethod = DetectionMethod.KS_TEST,
        drift_score: float = 0.0,
        feature_name: str = "",
        service: str = "",
        team: str = "",
    ) -> DriftRecord:
        record = DriftRecord(
            model_id=model_id,
            drift_type=drift_type,
            drift_severity=drift_severity,
            detection_method=detection_method,
            drift_score=drift_score,
            feature_name=feature_name,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "model_drift_detector.drift_recorded",
            record_id=record.id,
            model_id=model_id,
            drift_type=drift_type.value,
            drift_severity=drift_severity.value,
        )
        return record

    def get_drift(self, record_id: str) -> DriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
        self,
        drift_type: DriftType | None = None,
        drift_severity: DriftSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DriftRecord]:
        results = list(self._records)
        if drift_type is not None:
            results = [r for r in results if r.drift_type == drift_type]
        if drift_severity is not None:
            results = [r for r in results if r.drift_severity == drift_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        drift_type: DriftType = DriftType.DATA,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DriftAnalysis:
        analysis = DriftAnalysis(
            model_id=model_id,
            drift_type=drift_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "model_drift_detector.analysis_added",
            model_id=model_id,
            drift_type=drift_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by drift_type; return count and avg drift_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.drift_type.value
            type_data.setdefault(key, []).append(r.drift_score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
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
                        "model_id": r.model_id,
                        "drift_type": r.drift_type.value,
                        "drift_score": r.drift_score,
                        "feature_name": r.feature_name,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["drift_score"], reverse=True)

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg drift_score, sort descending."""
        model_scores: dict[str, list[float]] = {}
        for r in self._records:
            model_scores.setdefault(r.model_id, []).append(r.drift_score)
        results: list[dict[str, Any]] = []
        for model_id, scores in model_scores.items():
            results.append(
                {
                    "model_id": model_id,
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

    def generate_report(self) -> DriftReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_type[r.drift_type.value] = by_type.get(r.drift_type.value, 0) + 1
            by_severity[r.drift_severity.value] = by_severity.get(r.drift_severity.value, 0) + 1
            by_method[r.detection_method.value] = by_method.get(r.detection_method.value, 0) + 1
        severe_count = sum(1 for r in self._records if r.drift_score > self._drift_threshold)
        scores = [r.drift_score for r in self._records]
        avg_drift_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        severe_list = self.identify_severe_drifts()
        top_drifting = [o["model_id"] for o in severe_list[:5]]
        recs: list[str] = []
        if self._records and severe_count > 0:
            recs.append(
                f"{severe_count} model(s) exceeding drift threshold ({self._drift_threshold})"
            )
        if self._records and avg_drift_score > self._drift_threshold:
            recs.append(
                f"Avg drift score {avg_drift_score} exceeds threshold ({self._drift_threshold})"
            )
        if not recs:
            recs.append("Model drift is within acceptable bounds")
        return DriftReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            severe_count=severe_count,
            avg_drift_score=avg_drift_score,
            by_type=by_type,
            by_severity=by_severity,
            by_method=by_method,
            top_drifting=top_drifting,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("model_drift_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "drift_threshold": self._drift_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
