"""TraceContextPropagation — trace context propagation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PropagationFormat(StrEnum):
    W3C = "w3c"
    B3 = "b3"
    JAEGER = "jaeger"
    XRAY = "xray"


class PropagationIssue(StrEnum):
    MISSING_HEADER = "missing_header"
    FORMAT_MISMATCH = "format_mismatch"
    CONTEXT_LOST = "context_lost"
    ID_COLLISION = "id_collision"


class ServiceBoundary(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    THIRD_PARTY = "third_party"
    LEGACY = "legacy"


# --- Models ---


class TraceContextPropagationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    propagation_format: PropagationFormat = PropagationFormat.W3C
    propagation_issue: PropagationIssue = PropagationIssue.MISSING_HEADER
    service_boundary: ServiceBoundary = ServiceBoundary.INTERNAL
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceContextPropagationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    propagation_format: PropagationFormat = PropagationFormat.W3C
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceContextPropagationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_propagation_format: dict[str, int] = Field(default_factory=dict)
    by_propagation_issue: dict[str, int] = Field(default_factory=dict)
    by_service_boundary: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceContextPropagation:
    """Trace context propagation engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TraceContextPropagationRecord] = []
        self._analyses: list[TraceContextPropagationAnalysis] = []
        logger.info(
            "trace.context.propagation.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        propagation_format: PropagationFormat = (PropagationFormat.W3C),
        propagation_issue: PropagationIssue = (PropagationIssue.MISSING_HEADER),
        service_boundary: ServiceBoundary = (ServiceBoundary.INTERNAL),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TraceContextPropagationRecord:
        record = TraceContextPropagationRecord(
            name=name,
            propagation_format=propagation_format,
            propagation_issue=propagation_issue,
            service_boundary=service_boundary,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace.context.propagation.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = TraceContextPropagationAnalysis(
                    name=r.name,
                    propagation_format=(r.propagation_format),
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def detect_propagation_breaks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect propagation breaks."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.propagation_issue in (
                PropagationIssue.CONTEXT_LOST,
                PropagationIssue.FORMAT_MISMATCH,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "issue": (r.propagation_issue.value),
                        "format": (r.propagation_format.value),
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return results

    def compute_context_coverage(
        self,
    ) -> dict[str, Any]:
        """Compute context coverage by format."""
        format_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.propagation_format.value
            format_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in format_data.items():
            result[k] = {
                "count": len(scores),
                "avg_coverage": round(sum(scores) / len(scores), 2),
            }
        return result

    def recommend_propagation_fixes(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend propagation fixes per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_score": avg,
                    "fix": ("add_propagation_headers" if avg < self._threshold else "no_action"),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> TraceContextPropagationReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.propagation_format.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.propagation_issue.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.service_boundary.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Trace Context Propagation is healthy")
        return TraceContextPropagationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_propagation_format=by_e1,
            by_propagation_issue=by_e2,
            by_service_boundary=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("trace.context.propagation.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.propagation_format.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "propagation_format_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
