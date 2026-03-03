"""Sensitive Data Discovery Engine — discover sensitive data across storage locations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DataClassification(StrEnum):
    TOP_SECRET = "top_secret"  # noqa: S105
    CONFIDENTIAL = "confidential"
    INTERNAL = "internal"
    PUBLIC = "public"
    UNCLASSIFIED = "unclassified"


class DiscoveryMethod(StrEnum):
    PATTERN_MATCHING = "pattern_matching"
    ML_CLASSIFICATION = "ml_classification"
    DLP_SCAN = "dlp_scan"
    METADATA_ANALYSIS = "metadata_analysis"
    MANUAL = "manual"


class StorageLocation(StrEnum):
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    CLOUD_STORAGE = "cloud_storage"
    API_RESPONSE = "api_response"
    LOG_FILE = "log_file"


# --- Models ---


class DiscoveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    discovery_id: str = ""
    data_classification: DataClassification = DataClassification.INTERNAL
    discovery_method: DiscoveryMethod = DiscoveryMethod.PATTERN_MATCHING
    storage_location: StorageLocation = StorageLocation.DATABASE
    discovery_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DiscoveryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    discovery_id: str = ""
    data_classification: DataClassification = DataClassification.INTERNAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DiscoveryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_discovery_score: float = 0.0
    by_classification: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_location: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SensitiveDataDiscoveryEngine:
    """Discover sensitive data across storage locations using multiple detection methods."""

    def __init__(
        self,
        max_records: int = 200000,
        discovery_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._discovery_threshold = discovery_threshold
        self._records: list[DiscoveryRecord] = []
        self._analyses: list[DiscoveryAnalysis] = []
        logger.info(
            "sensitive_data_discovery_engine.initialized",
            max_records=max_records,
            discovery_threshold=discovery_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_discovery(
        self,
        discovery_id: str,
        data_classification: DataClassification = DataClassification.INTERNAL,
        discovery_method: DiscoveryMethod = DiscoveryMethod.PATTERN_MATCHING,
        storage_location: StorageLocation = StorageLocation.DATABASE,
        discovery_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DiscoveryRecord:
        record = DiscoveryRecord(
            discovery_id=discovery_id,
            data_classification=data_classification,
            discovery_method=discovery_method,
            storage_location=storage_location,
            discovery_score=discovery_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sensitive_data_discovery_engine.discovery_recorded",
            record_id=record.id,
            discovery_id=discovery_id,
            data_classification=data_classification.value,
            discovery_method=discovery_method.value,
        )
        return record

    def get_discovery(self, record_id: str) -> DiscoveryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_discoveries(
        self,
        data_classification: DataClassification | None = None,
        discovery_method: DiscoveryMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DiscoveryRecord]:
        results = list(self._records)
        if data_classification is not None:
            results = [r for r in results if r.data_classification == data_classification]
        if discovery_method is not None:
            results = [r for r in results if r.discovery_method == discovery_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        discovery_id: str,
        data_classification: DataClassification = DataClassification.INTERNAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DiscoveryAnalysis:
        analysis = DiscoveryAnalysis(
            discovery_id=discovery_id,
            data_classification=data_classification,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "sensitive_data_discovery_engine.analysis_added",
            discovery_id=discovery_id,
            data_classification=data_classification.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_classification_distribution(self) -> dict[str, Any]:
        classification_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.data_classification.value
            classification_data.setdefault(key, []).append(r.discovery_score)
        result: dict[str, Any] = {}
        for classification, scores in classification_data.items():
            result[classification] = {
                "count": len(scores),
                "avg_discovery_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_discovery_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.discovery_score < self._discovery_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "discovery_id": r.discovery_id,
                        "data_classification": r.data_classification.value,
                        "discovery_score": r.discovery_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["discovery_score"])

    def rank_by_discovery(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.discovery_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_discovery_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_discovery_score"])
        return results

    def detect_discovery_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DiscoveryReport:
        by_classification: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_location: dict[str, int] = {}
        for r in self._records:
            by_classification[r.data_classification.value] = (
                by_classification.get(r.data_classification.value, 0) + 1
            )
            by_method[r.discovery_method.value] = by_method.get(r.discovery_method.value, 0) + 1
            by_location[r.storage_location.value] = by_location.get(r.storage_location.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.discovery_score < self._discovery_threshold)
        scores = [r.discovery_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_discovery_gaps()
        top_gaps = [o["discovery_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} discovery(ies) below threshold ({self._discovery_threshold})")
        if self._records and avg_score < self._discovery_threshold:
            recs.append(
                f"Avg discovery score {avg_score} below threshold ({self._discovery_threshold})"
            )
        if not recs:
            recs.append("Sensitive data discovery is healthy")
        return DiscoveryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_discovery_score=avg_score,
            by_classification=by_classification,
            by_method=by_method,
            by_location=by_location,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("sensitive_data_discovery_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        classification_dist: dict[str, int] = {}
        for r in self._records:
            key = r.data_classification.value
            classification_dist[key] = classification_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "discovery_threshold": self._discovery_threshold,
            "classification_distribution": classification_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
