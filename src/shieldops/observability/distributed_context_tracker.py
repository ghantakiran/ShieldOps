"""Distributed Context Tracker

Cross-service context propagation tracking, baggage validation, context leak
detection, and W3C trace context compliance checking.
"""

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
    W3C_TRACEPARENT = "w3c_traceparent"
    W3C_TRACESTATE = "w3c_tracestate"
    B3_SINGLE = "b3_single"
    B3_MULTI = "b3_multi"
    JAEGER = "jaeger"
    XRAY = "xray"
    CUSTOM = "custom"


class ContextHealth(StrEnum):
    VALID = "valid"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    TRUNCATED = "truncated"
    LEAKED = "leaked"
    EXPIRED = "expired"


class ComplianceLevel(StrEnum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"


# --- Models ---


class ContextRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    source_service: str = ""
    target_service: str = ""
    propagation_format: PropagationFormat = PropagationFormat.W3C_TRACEPARENT
    context_health: ContextHealth = ContextHealth.VALID
    compliance_level: ComplianceLevel = ComplianceLevel.UNKNOWN
    baggage_items: dict[str, str] = Field(default_factory=dict)
    baggage_size_bytes: int = 0
    hop_count: int = 0
    context_age_ms: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ContextAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    propagation_format: PropagationFormat = PropagationFormat.W3C_TRACEPARENT
    compliance_score: float = 0.0
    leak_count: int = 0
    missing_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContextPropagationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    compliance_rate: float = 0.0
    leak_count: int = 0
    missing_context_count: int = 0
    corrupted_count: int = 0
    avg_hop_count: float = 0.0
    avg_baggage_size: float = 0.0
    by_propagation_format: dict[str, int] = Field(default_factory=dict)
    by_context_health: dict[str, int] = Field(default_factory=dict)
    by_compliance_level: dict[str, int] = Field(default_factory=dict)
    non_compliant_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DistributedContextTracker:
    """Distributed Context Tracker

    Cross-service context propagation tracking, baggage validation,
    context leak detection, and W3C compliance.
    """

    def __init__(
        self,
        max_records: int = 200000,
        max_baggage_size_bytes: int = 8192,
        max_hop_count: int = 25,
    ) -> None:
        self._max_records = max_records
        self._max_baggage_size = max_baggage_size_bytes
        self._max_hop_count = max_hop_count
        self._records: list[ContextRecord] = []
        self._analyses: list[ContextAnalysis] = []
        logger.info(
            "distributed_context_tracker.initialized",
            max_records=max_records,
            max_baggage_size_bytes=max_baggage_size_bytes,
        )

    def add_record(
        self,
        trace_id: str,
        span_id: str,
        source_service: str,
        target_service: str,
        propagation_format: PropagationFormat = PropagationFormat.W3C_TRACEPARENT,
        context_health: ContextHealth = ContextHealth.VALID,
        parent_span_id: str = "",
        baggage_items: dict[str, str] | None = None,
        baggage_size_bytes: int = 0,
        hop_count: int = 0,
        context_age_ms: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ContextRecord:
        baggage = baggage_items or {}
        compliance = ComplianceLevel.COMPLIANT
        if context_health != ContextHealth.VALID:
            compliance = ComplianceLevel.NON_COMPLIANT
        elif propagation_format not in (
            PropagationFormat.W3C_TRACEPARENT,
            PropagationFormat.W3C_TRACESTATE,
        ):
            compliance = ComplianceLevel.PARTIAL
        if baggage_size_bytes > self._max_baggage_size:
            compliance = ComplianceLevel.NON_COMPLIANT
        if hop_count > self._max_hop_count:
            compliance = ComplianceLevel.NON_COMPLIANT
        record = ContextRecord(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            source_service=source_service,
            target_service=target_service,
            propagation_format=propagation_format,
            context_health=context_health,
            compliance_level=compliance,
            baggage_items=baggage,
            baggage_size_bytes=baggage_size_bytes,
            hop_count=hop_count,
            context_age_ms=context_age_ms,
            service=service or source_service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "distributed_context_tracker.record_added",
            record_id=record.id,
            trace_id=trace_id,
            source_service=source_service,
            target_service=target_service,
            compliance=compliance.value,
        )
        return record

    def get_record(self, record_id: str) -> ContextRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        propagation_format: PropagationFormat | None = None,
        context_health: ContextHealth | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[ContextRecord]:
        results = list(self._records)
        if propagation_format is not None:
            results = [r for r in results if r.propagation_format == propagation_format]
        if context_health is not None:
            results = [r for r in results if r.context_health == context_health]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def detect_context_leaks(self) -> list[dict[str, Any]]:
        leaked = [r for r in self._records if r.context_health == ContextHealth.LEAKED]
        svc_leaks: dict[str, int] = {}
        for r in leaked:
            svc_leaks[r.source_service] = svc_leaks.get(r.source_service, 0) + 1
        return sorted(
            [{"service": svc, "leak_count": cnt} for svc, cnt in svc_leaks.items()],
            key=lambda x: x["leak_count"],
            reverse=True,
        )

    def validate_baggage(self) -> dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"status": "no_data"}
        oversized = sum(1 for r in self._records if r.baggage_size_bytes > self._max_baggage_size)
        empty = sum(1 for r in self._records if not r.baggage_items)
        sizes = [r.baggage_size_bytes for r in self._records]
        return {
            "total_records": total,
            "oversized_count": oversized,
            "oversized_rate": round(oversized / total, 4),
            "empty_baggage_count": empty,
            "avg_baggage_size": round(sum(sizes) / total, 2),
            "max_baggage_size": max(sizes) if sizes else 0,
            "max_allowed": self._max_baggage_size,
        }

    def check_w3c_compliance(self) -> dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"status": "no_data"}
        compliant = sum(1 for r in self._records if r.compliance_level == ComplianceLevel.COMPLIANT)
        partial = sum(1 for r in self._records if r.compliance_level == ComplianceLevel.PARTIAL)
        non_compliant_svcs = list(
            {
                r.source_service
                for r in self._records
                if r.compliance_level == ComplianceLevel.NON_COMPLIANT
            }
        )
        return {
            "total_records": total,
            "compliant_count": compliant,
            "compliance_rate": round(compliant / total, 4),
            "partial_count": partial,
            "non_compliant_services": non_compliant_svcs[:20],
        }

    def process(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        compliant = sum(1 for r in matching if r.compliance_level == ComplianceLevel.COMPLIANT)
        leaks = sum(1 for r in matching if r.context_health == ContextHealth.LEAKED)
        missing = sum(1 for r in matching if r.context_health == ContextHealth.MISSING)
        compliance_score = round(compliant / len(matching) * 100, 2)
        analysis = ContextAnalysis(
            service=service,
            compliance_score=compliance_score,
            leak_count=leaks,
            missing_count=missing,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return {
            "service": service,
            "total_contexts": len(matching),
            "compliance_score": compliance_score,
            "leak_count": leaks,
            "missing_count": missing,
            "avg_hop_count": round(sum(r.hop_count for r in matching) / len(matching), 2),
        }

    def generate_report(self) -> ContextPropagationReport:
        by_fmt: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_comp: dict[str, int] = {}
        for r in self._records:
            by_fmt[r.propagation_format.value] = by_fmt.get(r.propagation_format.value, 0) + 1
            by_health[r.context_health.value] = by_health.get(r.context_health.value, 0) + 1
            by_comp[r.compliance_level.value] = by_comp.get(r.compliance_level.value, 0) + 1
        total = len(self._records)
        compliant = sum(1 for r in self._records if r.compliance_level == ComplianceLevel.COMPLIANT)
        leaks = sum(1 for r in self._records if r.context_health == ContextHealth.LEAKED)
        missing = sum(1 for r in self._records if r.context_health == ContextHealth.MISSING)
        corrupted = sum(1 for r in self._records if r.context_health == ContextHealth.CORRUPTED)
        hops = [r.hop_count for r in self._records]
        sizes = [r.baggage_size_bytes for r in self._records]
        non_comp_svcs = list(
            {
                r.source_service
                for r in self._records
                if r.compliance_level == ComplianceLevel.NON_COMPLIANT
            }
        )
        recs: list[str] = []
        if leaks > 0:
            recs.append(f"{leaks} context leak(s) detected — review async boundaries")
        if missing > 0:
            recs.append(f"{missing} missing context(s) — ensure propagation in all clients")
        if corrupted > 0:
            recs.append(f"{corrupted} corrupted context(s) — validate serialization")
        if non_comp_svcs:
            recs.append(f"{len(non_comp_svcs)} non-compliant service(s) — migrate to W3C format")
        if not recs:
            recs.append("Context propagation is healthy and W3C compliant")
        return ContextPropagationReport(
            total_records=total,
            total_analyses=len(self._analyses),
            compliance_rate=round(compliant / max(1, total), 4),
            leak_count=leaks,
            missing_context_count=missing,
            corrupted_count=corrupted,
            avg_hop_count=round(sum(hops) / max(1, total), 2),
            avg_baggage_size=round(sum(sizes) / max(1, total), 2),
            by_propagation_format=by_fmt,
            by_context_health=by_health,
            by_compliance_level=by_comp,
            non_compliant_services=non_comp_svcs[:10],
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fmt_dist: dict[str, int] = {}
        for r in self._records:
            fmt_dist[r.propagation_format.value] = fmt_dist.get(r.propagation_format.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "max_baggage_size_bytes": self._max_baggage_size,
            "max_hop_count": self._max_hop_count,
            "format_distribution": fmt_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_traces": len({r.trace_id for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("distributed_context_tracker.cleared")
        return {"status": "cleared"}
