"""Trace Completeness Verification Engine —
verify trace completeness and integrity,
detect missing spans, rank traces by completeness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CompletenessType(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    FRAGMENTED = "fragmented"
    ORPHANED = "orphaned"


class VerificationMethod(StrEnum):
    SPAN_COUNT = "span_count"
    PARENT_CHECK = "parent_check"
    DURATION_CHECK = "duration_check"
    SEMANTIC = "semantic"


class IntegrityStatus(StrEnum):
    VALID = "valid"
    CORRUPTED = "corrupted"
    INCOMPLETE = "incomplete"
    SUSPICIOUS = "suspicious"


# --- Models ---


class TraceCompletenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    completeness_type: CompletenessType = CompletenessType.FULL
    verification_method: VerificationMethod = VerificationMethod.SPAN_COUNT
    integrity_status: IntegrityStatus = IntegrityStatus.VALID
    completeness_score: float = 0.0
    expected_spans: int = 0
    actual_spans: int = 0
    missing_spans: int = 0
    orphaned_spans: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceCompletenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    service_name: str = ""
    completeness_type: CompletenessType = CompletenessType.FULL
    effective_score: float = 0.0
    is_complete: bool = False
    integrity_status: IntegrityStatus = IntegrityStatus.VALID
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceCompletenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_completeness_score: float = 0.0
    by_completeness_type: dict[str, int] = Field(default_factory=dict)
    by_verification_method: dict[str, int] = Field(default_factory=dict)
    by_integrity_status: dict[str, int] = Field(default_factory=dict)
    incomplete_traces: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceCompletenessVerificationEngine:
    """Verify trace completeness and integrity,
    detect missing spans, rank traces by completeness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TraceCompletenessRecord] = []
        self._analyses: dict[str, TraceCompletenessAnalysis] = {}
        logger.info("trace_completeness_verification_engine.init", max_records=max_records)

    def add_record(
        self,
        trace_id: str = "",
        service_name: str = "",
        completeness_type: CompletenessType = CompletenessType.FULL,
        verification_method: VerificationMethod = VerificationMethod.SPAN_COUNT,
        integrity_status: IntegrityStatus = IntegrityStatus.VALID,
        completeness_score: float = 0.0,
        expected_spans: int = 0,
        actual_spans: int = 0,
        missing_spans: int = 0,
        orphaned_spans: int = 0,
        description: str = "",
    ) -> TraceCompletenessRecord:
        record = TraceCompletenessRecord(
            trace_id=trace_id,
            service_name=service_name,
            completeness_type=completeness_type,
            verification_method=verification_method,
            integrity_status=integrity_status,
            completeness_score=completeness_score,
            expected_spans=expected_spans,
            actual_spans=actual_spans,
            missing_spans=missing_spans,
            orphaned_spans=orphaned_spans,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_completeness.record_added",
            record_id=record.id,
            trace_id=trace_id,
        )
        return record

    def process(self, key: str) -> TraceCompletenessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        integ_penalty = {"valid": 0, "incomplete": 10, "suspicious": 20, "corrupted": 50}
        penalty = integ_penalty.get(rec.integrity_status.value, 10)
        effective = max(0.0, round(rec.completeness_score - penalty, 2))
        analysis = TraceCompletenessAnalysis(
            trace_id=rec.trace_id,
            service_name=rec.service_name,
            completeness_type=rec.completeness_type,
            effective_score=effective,
            is_complete=rec.completeness_type == CompletenessType.FULL and effective > 90.0,
            integrity_status=rec.integrity_status,
            description=(
                f"Trace {rec.trace_id} completeness {effective}% "
                f"integrity {rec.integrity_status.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TraceCompletenessReport:
        by_ctype: dict[str, int] = {}
        by_vmethod: dict[str, int] = {}
        by_integrity: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            ct = r.completeness_type.value
            by_ctype[ct] = by_ctype.get(ct, 0) + 1
            vm = r.verification_method.value
            by_vmethod[vm] = by_vmethod.get(vm, 0) + 1
            ig = r.integrity_status.value
            by_integrity[ig] = by_integrity.get(ig, 0) + 1
            scores.append(r.completeness_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        incomplete = list(
            {
                r.trace_id
                for r in self._records
                if r.completeness_type
                in (
                    CompletenessType.PARTIAL,
                    CompletenessType.FRAGMENTED,
                    CompletenessType.ORPHANED,
                )
            }
        )[:10]
        recs: list[str] = []
        if incomplete:
            recs.append(f"{len(incomplete)} traces with incomplete span data")
        if not recs:
            recs.append("All traces verified as complete and valid")
        return TraceCompletenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_completeness_score=avg,
            by_completeness_type=by_ctype,
            by_verification_method=by_vmethod,
            by_integrity_status=by_integrity,
            incomplete_traces=incomplete,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ctype_dist: dict[str, int] = {}
        for r in self._records:
            k = r.completeness_type.value
            ctype_dist[k] = ctype_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "completeness_type_distribution": ctype_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("trace_completeness_verification_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def verify_trace_completeness(self) -> list[dict[str, Any]]:
        """Verify completeness for all traces grouped by trace_id."""
        trace_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            trace_data.setdefault(r.trace_id, []).append(
                {
                    "score": r.completeness_score,
                    "expected": r.expected_spans,
                    "actual": r.actual_spans,
                    "missing": r.missing_spans,
                    "integrity": r.integrity_status.value,
                }
            )
        results: list[dict[str, Any]] = []
        for tid, items in trace_data.items():
            avg_score = sum(i["score"] for i in items) / len(items)
            total_missing = sum(i["missing"] for i in items)
            results.append(
                {
                    "trace_id": tid,
                    "avg_completeness_score": round(avg_score, 2),
                    "total_missing_spans": total_missing,
                    "verification_count": len(items),
                    "is_complete": avg_score > 90.0 and total_missing == 0,
                }
            )
        results.sort(key=lambda x: x["avg_completeness_score"], reverse=True)
        return results

    def detect_missing_spans(self) -> list[dict[str, Any]]:
        """Detect traces with missing or orphaned spans."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.missing_spans > 0 or r.orphaned_spans > 0:
                results.append(
                    {
                        "trace_id": r.trace_id,
                        "service_name": r.service_name,
                        "missing_spans": r.missing_spans,
                        "orphaned_spans": r.orphaned_spans,
                        "expected_spans": r.expected_spans,
                        "actual_spans": r.actual_spans,
                        "completeness_type": r.completeness_type.value,
                    }
                )
        results.sort(key=lambda x: x["missing_spans"], reverse=True)
        return results

    def rank_traces_by_completeness(self) -> list[dict[str, Any]]:
        """Rank traces by completeness score with integrity adjustment."""
        integ_penalty = {"valid": 0, "incomplete": 10, "suspicious": 20, "corrupted": 50}
        results: list[dict[str, Any]] = []
        for r in self._records:
            penalty = integ_penalty.get(r.integrity_status.value, 10)
            effective = max(0.0, round(r.completeness_score - penalty, 2))
            results.append(
                {
                    "trace_id": r.trace_id,
                    "service_name": r.service_name,
                    "completeness_score": r.completeness_score,
                    "integrity_status": r.integrity_status.value,
                    "effective_score": effective,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["effective_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
