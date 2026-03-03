"""Erasure Request Orchestrator — orchestrate data erasure and deletion requests."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RequestType(StrEnum):
    GDPR_ERASURE = "gdpr_erasure"
    CCPA_DELETE = "ccpa_delete"
    RIGHT_TO_FORGET = "right_to_forget"
    DATA_PORTABILITY = "data_portability"
    RECTIFICATION = "rectification"


class RequestStatus(StrEnum):
    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class DataSystem(StrEnum):
    DATABASE = "database"
    CACHE = "cache"
    BACKUP = "backup"
    ANALYTICS = "analytics"
    THIRD_PARTY = "third_party"


# --- Models ---


class ErasureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str = ""
    request_type: RequestType = RequestType.GDPR_ERASURE
    request_status: RequestStatus = RequestStatus.RECEIVED
    data_system: DataSystem = DataSystem.DATABASE
    completion_score: float = 0.0
    requester: str = ""
    data_owner: str = ""
    created_at: float = Field(default_factory=time.time)


class ErasureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str = ""
    request_type: RequestType = RequestType.GDPR_ERASURE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ErasureComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_completion_score: float = 0.0
    by_request_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_data_system: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ErasureRequestOrchestrator:
    """Orchestrate data erasure requests; track completion across all data systems."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ErasureRecord] = []
        self._analyses: list[ErasureAnalysis] = []
        logger.info(
            "erasure_request_orchestrator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_erasure(
        self,
        subject_id: str,
        request_type: RequestType = RequestType.GDPR_ERASURE,
        request_status: RequestStatus = RequestStatus.RECEIVED,
        data_system: DataSystem = DataSystem.DATABASE,
        completion_score: float = 0.0,
        requester: str = "",
        data_owner: str = "",
    ) -> ErasureRecord:
        record = ErasureRecord(
            subject_id=subject_id,
            request_type=request_type,
            request_status=request_status,
            data_system=data_system,
            completion_score=completion_score,
            requester=requester,
            data_owner=data_owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "erasure_request_orchestrator.erasure_recorded",
            record_id=record.id,
            subject_id=subject_id,
            request_type=request_type.value,
            request_status=request_status.value,
        )
        return record

    def get_erasure(self, record_id: str) -> ErasureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_erasures(
        self,
        request_type: RequestType | None = None,
        request_status: RequestStatus | None = None,
        requester: str | None = None,
        limit: int = 50,
    ) -> list[ErasureRecord]:
        results = list(self._records)
        if request_type is not None:
            results = [r for r in results if r.request_type == request_type]
        if request_status is not None:
            results = [r for r in results if r.request_status == request_status]
        if requester is not None:
            results = [r for r in results if r.requester == requester]
        return results[-limit:]

    def add_analysis(
        self,
        subject_id: str,
        request_type: RequestType = RequestType.GDPR_ERASURE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ErasureAnalysis:
        analysis = ErasureAnalysis(
            subject_id=subject_id,
            request_type=request_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "erasure_request_orchestrator.analysis_added",
            subject_id=subject_id,
            request_type=request_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_request_distribution(self) -> dict[str, Any]:
        """Group by request_type; return count and avg completion_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.request_type.value
            type_data.setdefault(key, []).append(r.completion_score)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_completion_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_erasure_gaps(self) -> list[dict[str, Any]]:
        """Return records where completion_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.completion_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "subject_id": r.subject_id,
                        "request_type": r.request_type.value,
                        "completion_score": r.completion_score,
                        "requester": r.requester,
                        "data_owner": r.data_owner,
                    }
                )
        return sorted(results, key=lambda x: x["completion_score"])

    def rank_by_completion(self) -> list[dict[str, Any]]:
        """Group by data_system, avg completion_score, sort ascending."""
        sys_scores: dict[str, list[float]] = {}
        for r in self._records:
            sys_scores.setdefault(r.data_system.value, []).append(r.completion_score)
        results: list[dict[str, Any]] = []
        for sys, scores in sys_scores.items():
            results.append(
                {
                    "data_system": sys,
                    "avg_completion_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_completion_score"])
        return results

    def detect_erasure_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ErasureComplianceReport:
        by_request_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_data_system: dict[str, int] = {}
        for r in self._records:
            by_request_type[r.request_type.value] = by_request_type.get(r.request_type.value, 0) + 1
            by_status[r.request_status.value] = by_status.get(r.request_status.value, 0) + 1
            by_data_system[r.data_system.value] = by_data_system.get(r.data_system.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.completion_score < self._threshold)
        scores = [r.completion_score for r in self._records]
        avg_completion_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_erasure_gaps()
        top_gaps = [o["subject_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} request(s) below completion threshold ({self._threshold})")
        if self._records and avg_completion_score < self._threshold:
            recs.append(
                f"Avg completion score {avg_completion_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Erasure request compliance is healthy")
        return ErasureComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_completion_score=avg_completion_score,
            by_request_type=by_request_type,
            by_status=by_status,
            by_data_system=by_data_system,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("erasure_request_orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.request_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "request_type_distribution": type_dist,
            "unique_requesters": len({r.requester for r in self._records}),
            "unique_owners": len({r.data_owner for r in self._records}),
        }
