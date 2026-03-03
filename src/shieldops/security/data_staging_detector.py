"""Data Staging Detector — detect data staging and pre-exfiltration activities."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StagingMethod(StrEnum):
    COMPRESSION = "compression"
    ENCRYPTION = "encryption"
    DIRECTORY_COLLECTION = "directory_collection"
    CLOUD_STAGING = "cloud_staging"
    TEMP_STORAGE = "temp_storage"


class DataType(StrEnum):
    PII = "pii"
    FINANCIAL = "financial"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    CREDENTIALS = "credentials"  # noqa: S105
    CONFIGURATION = "configuration"


class StagingIndicator(StrEnum):
    CONFIRMED = "confirmed"
    SUSPICIOUS = "suspicious"
    ELEVATED = "elevated"
    NORMAL = "normal"
    FALSE_POSITIVE = "false_positive"


# --- Models ---


class StagingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    staging_id: str = ""
    staging_method: StagingMethod = StagingMethod.COMPRESSION
    data_type: DataType = DataType.PII
    staging_indicator: StagingIndicator = StagingIndicator.CONFIRMED
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class StagingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    staging_id: str = ""
    staging_method: StagingMethod = StagingMethod.COMPRESSION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataStagingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_data_type: dict[str, int] = Field(default_factory=dict)
    by_indicator: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataStagingDetector:
    """Detect data staging and pre-exfiltration activities via method and data type analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[StagingRecord] = []
        self._analyses: list[StagingAnalysis] = []
        logger.info(
            "data_staging_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_staging(
        self,
        staging_id: str,
        staging_method: StagingMethod = StagingMethod.COMPRESSION,
        data_type: DataType = DataType.PII,
        staging_indicator: StagingIndicator = StagingIndicator.CONFIRMED,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> StagingRecord:
        record = StagingRecord(
            staging_id=staging_id,
            staging_method=staging_method,
            data_type=data_type,
            staging_indicator=staging_indicator,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_staging_detector.staging_recorded",
            record_id=record.id,
            staging_id=staging_id,
            staging_method=staging_method.value,
            data_type=data_type.value,
        )
        return record

    def get_staging(self, record_id: str) -> StagingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_stagings(
        self,
        staging_method: StagingMethod | None = None,
        data_type: DataType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[StagingRecord]:
        results = list(self._records)
        if staging_method is not None:
            results = [r for r in results if r.staging_method == staging_method]
        if data_type is not None:
            results = [r for r in results if r.data_type == data_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        staging_id: str,
        staging_method: StagingMethod = StagingMethod.COMPRESSION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> StagingAnalysis:
        analysis = StagingAnalysis(
            staging_id=staging_id,
            staging_method=staging_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_staging_detector.analysis_added",
            staging_id=staging_id,
            staging_method=staging_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_method_distribution(self) -> dict[str, Any]:
        """Group by staging_method; return count and avg detection_score."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.staging_method.value
            method_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "staging_id": r.staging_id,
                        "staging_method": r.staging_method.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        """Group by service, avg detection_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_detection_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DataStagingReport:
        by_method: dict[str, int] = {}
        by_data_type: dict[str, int] = {}
        by_indicator: dict[str, int] = {}
        for r in self._records:
            by_method[r.staging_method.value] = by_method.get(r.staging_method.value, 0) + 1
            by_data_type[r.data_type.value] = by_data_type.get(r.data_type.value, 0) + 1
            by_indicator[r.staging_indicator.value] = (
                by_indicator.get(r.staging_indicator.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["staging_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} staging record(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Data staging detection is healthy")
        return DataStagingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_method=by_method,
            by_data_type=by_data_type,
            by_indicator=by_indicator,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_staging_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.staging_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
