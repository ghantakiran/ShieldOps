"""SLO Alignment Validator — validate SLO alignment across services and dependencies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AlignmentStatus(StrEnum):
    ALIGNED = "aligned"
    PARTIALLY_ALIGNED = "partially_aligned"
    MISALIGNED = "misaligned"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


class AlignmentDimension(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    DURABILITY = "durability"


class AlignmentSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFO = "info"


# --- Models ---


class AlignmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    dependency: str = ""
    status: AlignmentStatus = AlignmentStatus.UNKNOWN
    dimension: AlignmentDimension = AlignmentDimension.AVAILABILITY
    alignment_score: float = 0.0
    severity: AlignmentSeverity = AlignmentSeverity.INFO
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AlignmentGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    service: str = ""
    gap_description: str = ""
    severity: AlignmentSeverity = AlignmentSeverity.INFO
    created_at: float = Field(default_factory=time.time)


class SLOAlignmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_gaps: int = 0
    aligned_count: int = 0
    misaligned_count: int = 0
    avg_alignment_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_misalignments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOAlignmentValidator:
    """Validate SLO alignment across services, dependencies, and dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        min_alignment_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_alignment_score = min_alignment_score
        self._records: list[AlignmentRecord] = []
        self._gaps: list[AlignmentGap] = []
        logger.info(
            "slo_alignment.initialized",
            max_records=max_records,
            min_alignment_score=min_alignment_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_alignment(
        self,
        service: str,
        dependency: str = "",
        status: AlignmentStatus = AlignmentStatus.UNKNOWN,
        dimension: AlignmentDimension = AlignmentDimension.AVAILABILITY,
        alignment_score: float = 0.0,
        severity: AlignmentSeverity = AlignmentSeverity.INFO,
        details: str = "",
    ) -> AlignmentRecord:
        record = AlignmentRecord(
            service=service,
            dependency=dependency,
            status=status,
            dimension=dimension,
            alignment_score=alignment_score,
            severity=severity,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_alignment.recorded",
            record_id=record.id,
            service=service,
            status=status.value,
            alignment_score=alignment_score,
        )
        return record

    def get_alignment(self, record_id: str) -> AlignmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_alignments(
        self,
        status: AlignmentStatus | None = None,
        dimension: AlignmentDimension | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[AlignmentRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.status == status]
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_gap(
        self,
        record_id: str,
        service: str = "",
        gap_description: str = "",
        severity: AlignmentSeverity = AlignmentSeverity.INFO,
    ) -> AlignmentGap:
        gap = AlignmentGap(
            record_id=record_id,
            service=service,
            gap_description=gap_description,
            severity=severity,
        )
        self._gaps.append(gap)
        if len(self._gaps) > self._max_records:
            self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "slo_alignment.gap_added",
            gap_id=gap.id,
            record_id=record_id,
            service=service,
            severity=severity.value,
        )
        return gap

    # -- domain operations -----------------------------------------------

    def analyze_alignment_by_service(self) -> list[dict[str, Any]]:
        """Group by service, compute avg alignment_score and count."""
        svc_map: dict[str, list[float]] = {}
        for r in self._records:
            svc_map.setdefault(r.service, []).append(r.alignment_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_map.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"service": svc, "count": len(scores), "avg_alignment_score": avg})
        results.sort(key=lambda x: x["avg_alignment_score"], reverse=True)
        return results

    def identify_misaligned_services(self) -> list[dict[str, Any]]:
        """Find services with status MISALIGNED or CONFLICTING."""
        svc_map: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.status in (AlignmentStatus.MISALIGNED, AlignmentStatus.CONFLICTING):
                entry = svc_map.setdefault(
                    r.service,
                    {"service": r.service, "misaligned_count": 0, "statuses": []},
                )
                entry["misaligned_count"] += 1
                if r.status.value not in entry["statuses"]:
                    entry["statuses"].append(r.status.value)
        results = list(svc_map.values())
        results.sort(key=lambda x: x["misaligned_count"], reverse=True)
        return results

    def rank_by_alignment_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.alignment_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"service": svc, "avg_alignment_score": avg, "count": len(scores)})
        results.sort(key=lambda x: x["avg_alignment_score"])
        return results

    def detect_alignment_trends(self) -> list[dict[str, Any]]:
        """Split-half on alignment_score; flag services with delta > 5.0."""
        if len(self._records) < 2:
            return []
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def avg_score(recs: list[AlignmentRecord], svc: str) -> float:
            subset = [r.alignment_score for r in recs if r.service == svc]
            return sum(subset) / len(subset) if subset else 0.0

        services = {r.service for r in self._records}
        results: list[dict[str, Any]] = []
        for svc in services:
            early = avg_score(first_half, svc)
            late = avg_score(second_half, svc)
            delta = round(late - early, 2)
            if abs(delta) > 5.0:
                results.append(
                    {
                        "service": svc,
                        "early_avg": round(early, 2),
                        "late_avg": round(late, 2),
                        "delta": delta,
                        "trend": "improving" if delta > 0 else "degrading",
                    }
                )
        results.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SLOAlignmentReport:
        by_status: dict[str, int] = {}
        by_dimension: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        avg_score = (
            round(sum(r.alignment_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        aligned = sum(1 for r in self._records if r.status == AlignmentStatus.ALIGNED)
        misaligned = sum(
            1
            for r in self._records
            if r.status in (AlignmentStatus.MISALIGNED, AlignmentStatus.CONFLICTING)
        )
        critical_svcs = list(
            {r.service for r in self._records if r.severity == AlignmentSeverity.CRITICAL}
        )
        recs: list[str] = []
        if misaligned > 0:
            recs.append(f"{misaligned} misaligned/conflicting alignment(s) detected")
        below_min = sum(1 for r in self._records if r.alignment_score < self._min_alignment_score)
        if below_min > 0:
            recs.append(
                f"{below_min} alignment(s) below minimum score of {self._min_alignment_score}"
            )
        if not recs:
            recs.append("All SLO alignments within acceptable thresholds")
        return SLOAlignmentReport(
            total_records=len(self._records),
            total_gaps=len(self._gaps),
            aligned_count=aligned,
            misaligned_count=misaligned,
            avg_alignment_score=avg_score,
            by_status=by_status,
            by_dimension=by_dimension,
            by_severity=by_severity,
            critical_misalignments=critical_svcs,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("slo_alignment.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "min_alignment_score": self._min_alignment_score,
            "status_distribution": status_dist,
            "unique_services": len({r.service for r in self._records}),
        }
