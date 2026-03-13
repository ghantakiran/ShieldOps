"""Distributed Context Enrichment Engine —
evaluate distributed trace context completeness,
detect propagation gaps, optimize enrichment pipeline."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContextSource(StrEnum):
    BAGGAGE = "baggage"
    HEADERS = "headers"
    METADATA = "metadata"
    ENVIRONMENT = "environment"


class EnrichmentType(StrEnum):
    BUSINESS = "business"
    TECHNICAL = "technical"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class EnrichmentQuality(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    MISSING = "missing"


# --- Models ---


class DistributedContextRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    context_source: ContextSource = ContextSource.HEADERS
    enrichment_type: EnrichmentType = EnrichmentType.TECHNICAL
    enrichment_quality: EnrichmentQuality = EnrichmentQuality.COMPLETE
    completeness_score: float = 0.0
    propagation_hops: int = 0
    missing_keys: int = 0
    stale_fields: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DistributedContextAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    context_source: ContextSource = ContextSource.HEADERS
    gap_detected: bool = False
    effective_completeness: float = 0.0
    enrichment_quality: EnrichmentQuality = EnrichmentQuality.COMPLETE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DistributedContextReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_completeness_score: float = 0.0
    by_context_source: dict[str, int] = Field(default_factory=dict)
    by_enrichment_type: dict[str, int] = Field(default_factory=dict)
    by_enrichment_quality: dict[str, int] = Field(default_factory=dict)
    gap_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DistributedContextEnrichmentEngine:
    """Evaluate distributed trace context completeness,
    detect propagation gaps, optimize enrichment pipeline."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DistributedContextRecord] = []
        self._analyses: dict[str, DistributedContextAnalysis] = {}
        logger.info("distributed_context_enrichment_engine.init", max_records=max_records)

    def add_record(
        self,
        trace_id: str = "",
        service_name: str = "",
        context_source: ContextSource = ContextSource.HEADERS,
        enrichment_type: EnrichmentType = EnrichmentType.TECHNICAL,
        enrichment_quality: EnrichmentQuality = EnrichmentQuality.COMPLETE,
        completeness_score: float = 0.0,
        propagation_hops: int = 0,
        missing_keys: int = 0,
        stale_fields: int = 0,
        description: str = "",
    ) -> DistributedContextRecord:
        record = DistributedContextRecord(
            trace_id=trace_id,
            service_name=service_name,
            context_source=context_source,
            enrichment_type=enrichment_type,
            enrichment_quality=enrichment_quality,
            completeness_score=completeness_score,
            propagation_hops=propagation_hops,
            missing_keys=missing_keys,
            stale_fields=stale_fields,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "distributed_context.record_added",
            record_id=record.id,
            trace_id=trace_id,
        )
        return record

    def process(self, key: str) -> DistributedContextAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        penalty = (rec.missing_keys * 5.0) + (rec.stale_fields * 2.0)
        effective = max(0.0, round(rec.completeness_score - penalty, 2))
        gap = rec.enrichment_quality in (EnrichmentQuality.MISSING, EnrichmentQuality.STALE)
        analysis = DistributedContextAnalysis(
            trace_id=rec.trace_id,
            service_name=rec.service_name,
            context_source=rec.context_source,
            gap_detected=gap,
            effective_completeness=effective,
            enrichment_quality=rec.enrichment_quality,
            description=(f"{rec.service_name} context completeness {effective}% gap={gap}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> DistributedContextReport:
        by_src: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_qual: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            s = r.context_source.value
            by_src[s] = by_src.get(s, 0) + 1
            t = r.enrichment_type.value
            by_type[t] = by_type.get(t, 0) + 1
            q = r.enrichment_quality.value
            by_qual[q] = by_qual.get(q, 0) + 1
            scores.append(r.completeness_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_svcs = list(
            {
                r.service_name
                for r in self._records
                if r.enrichment_quality in (EnrichmentQuality.MISSING, EnrichmentQuality.STALE)
            }
        )[:10]
        recs: list[str] = []
        if gap_svcs:
            recs.append(f"{len(gap_svcs)} services with context propagation gaps")
        if not recs:
            recs.append("Context enrichment quality is healthy")
        return DistributedContextReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_completeness_score=avg,
            by_context_source=by_src,
            by_enrichment_type=by_type,
            by_enrichment_quality=by_qual,
            gap_services=gap_svcs,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        qual_dist: dict[str, int] = {}
        for r in self._records:
            k = r.enrichment_quality.value
            qual_dist[k] = qual_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_distribution": qual_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("distributed_context_enrichment_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def evaluate_context_completeness(self) -> list[dict[str, Any]]:
        """Evaluate context completeness per service."""
        svc_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_data.setdefault(r.service_name, []).append(
                {
                    "score": r.completeness_score,
                    "missing_keys": r.missing_keys,
                    "stale_fields": r.stale_fields,
                }
            )
        results: list[dict[str, Any]] = []
        for svc, items in svc_data.items():
            avg_score = sum(i["score"] for i in items) / len(items)
            avg_missing = sum(i["missing_keys"] for i in items) / len(items)
            results.append(
                {
                    "service_name": svc,
                    "avg_completeness_score": round(avg_score, 2),
                    "avg_missing_keys": round(avg_missing, 2),
                    "sample_count": len(items),
                    "completeness_ok": avg_score > 80.0,
                }
            )
        results.sort(key=lambda x: x["avg_completeness_score"], reverse=True)
        return results

    def detect_context_propagation_gaps(self) -> list[dict[str, Any]]:
        """Detect gaps in context propagation across hops."""
        hop_data: dict[int, list[dict[str, Any]]] = {}
        for r in self._records:
            hop_data.setdefault(r.propagation_hops, []).append(
                {
                    "service_name": r.service_name,
                    "completeness_score": r.completeness_score,
                    "missing_keys": r.missing_keys,
                }
            )
        results: list[dict[str, Any]] = []
        for hops, items in hop_data.items():
            avg_comp = sum(i["completeness_score"] for i in items) / len(items)
            total_missing = sum(i["missing_keys"] for i in items)
            results.append(
                {
                    "propagation_hops": hops,
                    "record_count": len(items),
                    "avg_completeness": round(avg_comp, 2),
                    "total_missing_keys": total_missing,
                    "gap_detected": avg_comp < 70.0,
                }
            )
        results.sort(key=lambda x: x["propagation_hops"])
        return results

    def optimize_enrichment_pipeline(self) -> list[dict[str, Any]]:
        """Recommend enrichment pipeline optimizations per source."""
        src_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            sv = r.context_source.value
            if sv not in src_data:
                src_data[sv] = {
                    "count": 0,
                    "total_score": 0.0,
                    "total_missing": 0,
                    "total_stale": 0,
                }
            src_data[sv]["count"] += 1
            src_data[sv]["total_score"] += r.completeness_score
            src_data[sv]["total_missing"] += r.missing_keys
            src_data[sv]["total_stale"] += r.stale_fields
        results: list[dict[str, Any]] = []
        for sv, data in src_data.items():
            cnt = data["count"]
            avg_score = round(data["total_score"] / cnt, 2)
            results.append(
                {
                    "context_source": sv,
                    "record_count": cnt,
                    "avg_completeness": avg_score,
                    "avg_missing_keys": round(data["total_missing"] / cnt, 2),
                    "avg_stale_fields": round(data["total_stale"] / cnt, 2),
                    "needs_optimization": avg_score < 75.0,
                }
            )
        results.sort(key=lambda x: x["avg_completeness"])
        return results
