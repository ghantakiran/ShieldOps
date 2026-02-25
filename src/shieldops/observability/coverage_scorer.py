"""Observability Coverage Scorer — evaluate per-service observability maturity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ObservabilityPillar(StrEnum):
    LOGGING = "logging"
    METRICS = "metrics"
    TRACING = "tracing"
    ALERTING = "alerting"
    DASHBOARDS = "dashboards"


class MaturityLevel(StrEnum):
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXEMPLARY = "exemplary"


class GapPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class ServiceCoverageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    pillar: ObservabilityPillar = ObservabilityPillar.LOGGING
    maturity: MaturityLevel = MaturityLevel.NONE
    coverage_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    pillar: ObservabilityPillar = ObservabilityPillar.LOGGING
    priority: GapPriority = GapPriority.MEDIUM
    description: str = ""
    remediation: str = ""
    created_at: float = Field(default_factory=time.time)


class ObservabilityCoverageReport(BaseModel):
    total_records: int = 0
    total_gaps: int = 0
    avg_coverage_pct: float = 0.0
    by_pillar: dict[str, float] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    services_below_threshold: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityCoverageScorer:
    """Evaluate per-service observability maturity."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._records: list[ServiceCoverageRecord] = []
        self._gaps: list[CoverageGap] = []
        logger.info(
            "coverage_scorer.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _pct_to_maturity(self, pct: float) -> MaturityLevel:
        if pct >= 90:
            return MaturityLevel.EXEMPLARY
        if pct >= 75:
            return MaturityLevel.ADVANCED
        if pct >= 50:
            return MaturityLevel.INTERMEDIATE
        if pct >= 25:
            return MaturityLevel.BASIC
        return MaturityLevel.NONE

    def _maturity_to_pct(self, maturity: MaturityLevel) -> float:
        return {
            MaturityLevel.NONE: 0.0,
            MaturityLevel.BASIC: 25.0,
            MaturityLevel.INTERMEDIATE: 50.0,
            MaturityLevel.ADVANCED: 75.0,
            MaturityLevel.EXEMPLARY: 95.0,
        }.get(maturity, 0.0)

    # -- record / get / list ---------------------------------------------

    def record_coverage(
        self,
        service: str,
        pillar: ObservabilityPillar,
        coverage_pct: float = 0.0,
        maturity: MaturityLevel | None = None,
        details: str = "",
    ) -> ServiceCoverageRecord:
        if maturity is None:
            maturity = self._pct_to_maturity(coverage_pct)
        record = ServiceCoverageRecord(
            service=service,
            pillar=pillar,
            maturity=maturity,
            coverage_pct=coverage_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "coverage_scorer.coverage_recorded",
            record_id=record.id,
            service=service,
            pillar=pillar.value,
            coverage_pct=coverage_pct,
        )
        return record

    def get_coverage(self, record_id: str) -> ServiceCoverageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_coverage(
        self,
        service: str | None = None,
        pillar: ObservabilityPillar | None = None,
        limit: int = 50,
    ) -> list[ServiceCoverageRecord]:
        results = list(self._records)
        if service is not None:
            results = [r for r in results if r.service == service]
        if pillar is not None:
            results = [r for r in results if r.pillar == pillar]
        return results[-limit:]

    def record_gap(
        self,
        service: str,
        pillar: ObservabilityPillar,
        priority: GapPriority = GapPriority.MEDIUM,
        description: str = "",
        remediation: str = "",
    ) -> CoverageGap:
        gap = CoverageGap(
            service=service,
            pillar=pillar,
            priority=priority,
            description=description,
            remediation=remediation,
        )
        self._gaps.append(gap)
        if len(self._gaps) > self._max_records:
            self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "coverage_scorer.gap_recorded",
            gap_id=gap.id,
            service=service,
            pillar=pillar.value,
            priority=priority.value,
        )
        return gap

    # -- domain operations -----------------------------------------------

    def calculate_service_score(self, service: str) -> dict[str, Any]:
        """Calculate overall observability score for a service."""
        svc_records = [r for r in self._records if r.service == service]
        if not svc_records:
            return {"service": service, "score": 0.0, "maturity": "none", "pillar_count": 0}
        total_pct = sum(r.coverage_pct for r in svc_records)
        avg_pct = round(total_pct / len(svc_records), 2)
        maturity = self._pct_to_maturity(avg_pct)
        pillar_scores = {}
        for r in svc_records:
            pillar_scores[r.pillar.value] = r.coverage_pct
        return {
            "service": service,
            "score": avg_pct,
            "maturity": maturity.value,
            "pillar_count": len(svc_records),
            "pillar_scores": pillar_scores,
        }

    def identify_instrumentation_gaps(self) -> list[dict[str, Any]]:
        """Find services missing key observability pillars."""
        # Group by service
        service_pillars: dict[str, set[str]] = {}
        for r in self._records:
            service_pillars.setdefault(r.service, set()).add(r.pillar.value)
        all_pillars = {p.value for p in ObservabilityPillar}
        results: list[dict[str, Any]] = []
        for svc, pillars in service_pillars.items():
            missing = all_pillars - pillars
            if missing:
                results.append(
                    {
                        "service": svc,
                        "missing_pillars": sorted(missing),
                        "covered_pillars": sorted(pillars),
                        "coverage_ratio": f"{len(pillars)}/{len(all_pillars)}",
                    }
                )
        results.sort(key=lambda x: len(x["missing_pillars"]), reverse=True)
        return results

    def rank_services_by_coverage(self) -> list[dict[str, Any]]:
        """Rank all services by their overall observability coverage."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.coverage_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_coverage_pct": avg,
                    "maturity": self._pct_to_maturity(avg).value,
                    "pillar_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_pct"], reverse=True)
        return results

    def get_pillar_breakdown(self) -> dict[str, Any]:
        """Get coverage breakdown by pillar across all services."""
        pillar_scores: dict[str, list[float]] = {}
        for r in self._records:
            pillar_scores.setdefault(r.pillar.value, []).append(r.coverage_pct)
        breakdown: dict[str, float] = {}
        for pillar, scores in pillar_scores.items():
            breakdown[pillar] = round(sum(scores) / len(scores), 2)
        return {
            "pillar_averages": breakdown,
            "total_services": len({r.service for r in self._records}),
            "total_records": len(self._records),
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ObservabilityCoverageReport:
        by_pillar: dict[str, float] = {}
        pillar_counts: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        for r in self._records:
            by_pillar[r.pillar.value] = by_pillar.get(r.pillar.value, 0) + r.coverage_pct
            pillar_counts[r.pillar.value] = pillar_counts.get(r.pillar.value, 0) + 1
            by_maturity[r.maturity.value] = by_maturity.get(r.maturity.value, 0) + 1
        # Average per pillar
        pillar_avg: dict[str, float] = {}
        for p, total in by_pillar.items():
            pillar_avg[p] = round(total / pillar_counts[p], 2)
        avg_coverage = (
            round(sum(r.coverage_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        # Count services below threshold
        service_scores = self.rank_services_by_coverage()
        below = sum(1 for s in service_scores if s["avg_coverage_pct"] < self._min_coverage_pct)
        recs: list[str] = []
        if below > 0:
            recs.append(f"{below} service(s) below {self._min_coverage_pct}% coverage threshold")
        gaps = self.identify_instrumentation_gaps()
        if gaps:
            recs.append(f"{len(gaps)} service(s) missing observability pillars")
        critical_gaps = sum(1 for g in self._gaps if g.priority == GapPriority.CRITICAL)
        if critical_gaps > 0:
            recs.append(f"{critical_gaps} critical coverage gap(s) identified")
        if not recs:
            recs.append("Observability coverage meets targets")
        return ObservabilityCoverageReport(
            total_records=len(self._records),
            total_gaps=len(self._gaps),
            avg_coverage_pct=avg_coverage,
            by_pillar=pillar_avg,
            by_maturity=by_maturity,
            services_below_threshold=below,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("coverage_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pillar_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pillar.value
            pillar_dist[key] = pillar_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "min_coverage_pct": self._min_coverage_pct,
            "pillar_distribution": pillar_dist,
            "unique_services": len({r.service for r in self._records}),
        }
