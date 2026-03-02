"""IOC Lifecycle Manager — manage the full lifecycle of indicators of compromise."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IOCType(StrEnum):
    IP_ADDRESS = "ip_address"
    DOMAIN = "domain"
    FILE_HASH = "file_hash"
    URL = "url"
    EMAIL = "email"


class IOCStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DEPRECATED = "deprecated"
    QUARANTINED = "quarantined"


class IOCConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


# --- Models ---


class IOCRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ioc_value: str = ""
    ioc_type: IOCType = IOCType.IP_ADDRESS
    ioc_status: IOCStatus = IOCStatus.ACTIVE
    ioc_confidence: IOCConfidence = IOCConfidence.MEDIUM
    relevance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IOCAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ioc_value: str = ""
    ioc_type: IOCType = IOCType.IP_ADDRESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IOCLifecycleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_relevance_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IOCLifecycleManager:
    """Manage the full lifecycle of indicators of compromise."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[IOCRecord] = []
        self._analyses: list[IOCAnalysis] = []
        logger.info(
            "ioc_lifecycle_manager.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_ioc(
        self,
        ioc_value: str,
        ioc_type: IOCType = IOCType.IP_ADDRESS,
        ioc_status: IOCStatus = IOCStatus.ACTIVE,
        ioc_confidence: IOCConfidence = IOCConfidence.MEDIUM,
        relevance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> IOCRecord:
        record = IOCRecord(
            ioc_value=ioc_value,
            ioc_type=ioc_type,
            ioc_status=ioc_status,
            ioc_confidence=ioc_confidence,
            relevance_score=relevance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ioc_lifecycle_manager.recorded",
            record_id=record.id,
            ioc_value=ioc_value,
            ioc_type=ioc_type.value,
        )
        return record

    def get_record(self, record_id: str) -> IOCRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        ioc_type: IOCType | None = None,
        ioc_status: IOCStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IOCRecord]:
        results = list(self._records)
        if ioc_type is not None:
            results = [r for r in results if r.ioc_type == ioc_type]
        if ioc_status is not None:
            results = [r for r in results if r.ioc_status == ioc_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        ioc_value: str,
        ioc_type: IOCType = IOCType.IP_ADDRESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> IOCAnalysis:
        analysis = IOCAnalysis(
            ioc_value=ioc_value,
            ioc_type=ioc_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "ioc_lifecycle_manager.analysis_added",
            ioc_value=ioc_value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_type_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.ioc_type.value
            type_data.setdefault(key, []).append(r.relevance_score)
        result: dict[str, Any] = {}
        for itype, scores in type_data.items():
            result[itype] = {
                "count": len(scores),
                "avg_relevance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.relevance_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "ioc_value": r.ioc_value,
                        "ioc_type": r.ioc_type.value,
                        "relevance_score": r.relevance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["relevance_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.relevance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_relevance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_relevance_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> IOCLifecycleReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_type[r.ioc_type.value] = by_type.get(r.ioc_type.value, 0) + 1
            by_status[r.ioc_status.value] = by_status.get(r.ioc_status.value, 0) + 1
            by_confidence[r.ioc_confidence.value] = by_confidence.get(r.ioc_confidence.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.relevance_score < self._quality_threshold)
        scores = [r.relevance_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["ioc_value"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} IOC(s) below quality threshold ({self._quality_threshold})")
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg relevance score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("IOC lifecycle management is healthy")
        return IOCLifecycleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_relevance_score=avg_score,
            by_type=by_type,
            by_status=by_status,
            by_confidence=by_confidence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("ioc_lifecycle_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.ioc_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
