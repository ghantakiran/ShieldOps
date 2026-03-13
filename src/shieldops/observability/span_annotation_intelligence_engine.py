"""Span Annotation Intelligence Engine —
evaluate span annotation coverage,
detect missing annotations, optimize annotation rules."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnnotationType(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    CUSTOM = "custom"


class AnnotationSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    ML_INFERRED = "ml_inferred"
    POLICY = "policy"


class AnnotationQuality(StrEnum):
    ACCURATE = "accurate"
    APPROXIMATE = "approximate"
    STALE = "stale"
    INCORRECT = "incorrect"


# --- Models ---


class SpanAnnotationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = ""
    trace_id: str = ""
    service_name: str = ""
    annotation_type: AnnotationType = AnnotationType.INFO
    annotation_source: AnnotationSource = AnnotationSource.AUTOMATIC
    annotation_quality: AnnotationQuality = AnnotationQuality.ACCURATE
    coverage_score: float = 0.0
    missing_annotations: int = 0
    total_spans: int = 0
    annotated_spans: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SpanAnnotationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = ""
    service_name: str = ""
    annotation_type: AnnotationType = AnnotationType.INFO
    effective_coverage: float = 0.0
    has_missing: bool = False
    quality: AnnotationQuality = AnnotationQuality.ACCURATE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SpanAnnotationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_coverage_score: float = 0.0
    by_annotation_type: dict[str, int] = Field(default_factory=dict)
    by_annotation_source: dict[str, int] = Field(default_factory=dict)
    by_annotation_quality: dict[str, int] = Field(default_factory=dict)
    low_coverage_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SpanAnnotationIntelligenceEngine:
    """Evaluate span annotation coverage,
    detect missing annotations, optimize annotation rules."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SpanAnnotationRecord] = []
        self._analyses: dict[str, SpanAnnotationAnalysis] = {}
        logger.info("span_annotation_intelligence_engine.init", max_records=max_records)

    def add_record(
        self,
        span_id: str = "",
        trace_id: str = "",
        service_name: str = "",
        annotation_type: AnnotationType = AnnotationType.INFO,
        annotation_source: AnnotationSource = AnnotationSource.AUTOMATIC,
        annotation_quality: AnnotationQuality = AnnotationQuality.ACCURATE,
        coverage_score: float = 0.0,
        missing_annotations: int = 0,
        total_spans: int = 0,
        annotated_spans: int = 0,
        description: str = "",
    ) -> SpanAnnotationRecord:
        record = SpanAnnotationRecord(
            span_id=span_id,
            trace_id=trace_id,
            service_name=service_name,
            annotation_type=annotation_type,
            annotation_source=annotation_source,
            annotation_quality=annotation_quality,
            coverage_score=coverage_score,
            missing_annotations=missing_annotations,
            total_spans=total_spans,
            annotated_spans=annotated_spans,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "span_annotation.record_added",
            record_id=record.id,
            span_id=span_id,
        )
        return record

    def process(self, key: str) -> SpanAnnotationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        qual_weights = {
            "accurate": 1.0,
            "approximate": 0.75,
            "stale": 0.5,
            "incorrect": 0.0,
        }
        w = qual_weights.get(rec.annotation_quality.value, 0.75)
        effective = round(rec.coverage_score * w, 2)
        analysis = SpanAnnotationAnalysis(
            span_id=rec.span_id,
            service_name=rec.service_name,
            annotation_type=rec.annotation_type,
            effective_coverage=effective,
            has_missing=rec.missing_annotations > 0,
            quality=rec.annotation_quality,
            description=(f"{rec.service_name} span {rec.span_id} coverage {effective}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SpanAnnotationReport:
        by_type: dict[str, int] = {}
        by_src: dict[str, int] = {}
        by_qual: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            t = r.annotation_type.value
            by_type[t] = by_type.get(t, 0) + 1
            s = r.annotation_source.value
            by_src[s] = by_src.get(s, 0) + 1
            q = r.annotation_quality.value
            by_qual[q] = by_qual.get(q, 0) + 1
            scores.append(r.coverage_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_cov = list({r.service_name for r in self._records if r.coverage_score < 60.0})[:10]
        recs: list[str] = []
        if low_cov:
            recs.append(f"{len(low_cov)} services with low annotation coverage")
        if not recs:
            recs.append("Annotation coverage is healthy across all services")
        return SpanAnnotationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_coverage_score=avg,
            by_annotation_type=by_type,
            by_annotation_source=by_src,
            by_annotation_quality=by_qual,
            low_coverage_services=low_cov,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.annotation_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "annotation_type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("span_annotation_intelligence_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def evaluate_annotation_coverage(self) -> list[dict[str, Any]]:
        """Evaluate annotation coverage per service."""
        svc_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_data.setdefault(r.service_name, []).append(
                {
                    "coverage_score": r.coverage_score,
                    "total_spans": r.total_spans,
                    "annotated_spans": r.annotated_spans,
                }
            )
        results: list[dict[str, Any]] = []
        for svc, items in svc_data.items():
            avg_cov = sum(i["coverage_score"] for i in items) / len(items)
            total_sp = sum(i["total_spans"] for i in items)
            total_ann = sum(i["annotated_spans"] for i in items)
            results.append(
                {
                    "service_name": svc,
                    "avg_coverage_score": round(avg_cov, 2),
                    "total_spans": total_sp,
                    "annotated_spans": total_ann,
                    "annotation_rate_pct": (
                        round(total_ann / total_sp * 100, 2) if total_sp > 0 else 0.0
                    ),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"], reverse=True)
        return results

    def detect_missing_annotations(self) -> list[dict[str, Any]]:
        """Detect spans with missing or incomplete annotations."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.missing_annotations > 0:
                results.append(
                    {
                        "span_id": r.span_id,
                        "service_name": r.service_name,
                        "missing_annotations": r.missing_annotations,
                        "coverage_score": r.coverage_score,
                        "annotation_quality": r.annotation_quality.value,
                    }
                )
        results.sort(key=lambda x: x["missing_annotations"], reverse=True)
        return results

    def optimize_annotation_rules(self) -> list[dict[str, Any]]:
        """Recommend annotation rule optimizations by source."""
        src_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            sv = r.annotation_source.value
            if sv not in src_data:
                src_data[sv] = {
                    "count": 0,
                    "total_coverage": 0.0,
                    "total_missing": 0,
                }
            src_data[sv]["count"] += 1
            src_data[sv]["total_coverage"] += r.coverage_score
            src_data[sv]["total_missing"] += r.missing_annotations
        results: list[dict[str, Any]] = []
        for sv, data in src_data.items():
            cnt = data["count"]
            avg_cov = round(data["total_coverage"] / cnt, 2)
            results.append(
                {
                    "annotation_source": sv,
                    "record_count": cnt,
                    "avg_coverage": avg_cov,
                    "total_missing": data["total_missing"],
                    "needs_optimization": avg_cov < 70.0,
                }
            )
        results.sort(key=lambda x: x["avg_coverage"])
        return results
