"""Runbook Coverage Analyzer — track and analyze runbook coverage across incident scenarios."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CoverageLevel(StrEnum):
    FULL = "full"
    HIGH = "high"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class IncidentType(StrEnum):
    OUTAGE = "outage"
    DEGRADATION = "degradation"
    SECURITY_BREACH = "security_breach"
    DATA_LOSS = "data_loss"
    CAPACITY = "capacity"


class CoverageGap(StrEnum):
    MISSING_RUNBOOK = "missing_runbook"
    OUTDATED_RUNBOOK = "outdated_runbook"
    INCOMPLETE_STEPS = "incomplete_steps"
    NO_AUTOMATION = "no_automation"
    UNTESTED = "untested"


# --- Models ---


class CoverageRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service: str = ""
    incident_type: IncidentType = IncidentType.OUTAGE
    coverage_level: CoverageLevel = CoverageLevel.NONE
    coverage_score: float = 0.0
    gap: CoverageGap | None = None
    runbook_count: int = 0
    automated: bool = False
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageGapDetail(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service: str = ""
    incident_type: IncidentType = IncidentType.OUTAGE
    gap: CoverageGap = CoverageGap.MISSING_RUNBOOK
    priority: str = ""
    recommended_action: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_gaps: int = 0
    fully_covered: int = 0
    uncovered: int = 0
    avg_coverage_score: float = 0.0
    by_coverage_level: dict[str, int] = Field(default_factory=dict)
    by_incident_type: dict[str, int] = Field(default_factory=dict)
    by_gap_type: dict[str, int] = Field(default_factory=dict)
    top_uncovered_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookCoverageAnalyzer:
    """Analyze runbook coverage gaps across services and incident scenarios."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._records: list[CoverageRecord] = []
        self._gaps: list[CoverageGapDetail] = []
        logger.info(
            "runbook_coverage.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- CRUD --

    def record_coverage(
        self,
        service: str,
        incident_type: IncidentType = IncidentType.OUTAGE,
        coverage_level: CoverageLevel = CoverageLevel.NONE,
        coverage_score: float = 0.0,
        gap: CoverageGap | None = None,
        runbook_count: int = 0,
        automated: bool = False,
        details: str = "",
    ) -> CoverageRecord:
        record = CoverageRecord(
            service=service,
            incident_type=incident_type,
            coverage_level=coverage_level,
            coverage_score=coverage_score,
            gap=gap,
            runbook_count=runbook_count,
            automated=automated,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_coverage.recorded",
            record_id=record.id,
            service=service,
            coverage_level=coverage_level.value,
        )
        return record

    def get_coverage(self, record_id: str) -> CoverageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_coverages(
        self,
        coverage_level: CoverageLevel | None = None,
        incident_type: IncidentType | None = None,
        gap: CoverageGap | None = None,
        limit: int = 50,
    ) -> list[CoverageRecord]:
        results = list(self._records)
        if coverage_level is not None:
            results = [r for r in results if r.coverage_level == coverage_level]
        if incident_type is not None:
            results = [r for r in results if r.incident_type == incident_type]
        if gap is not None:
            results = [r for r in results if r.gap == gap]
        return results[-limit:]

    def add_gap(
        self,
        service: str,
        incident_type: IncidentType = IncidentType.OUTAGE,
        gap: CoverageGap = CoverageGap.MISSING_RUNBOOK,
        priority: str = "",
        recommended_action: str = "",
        description: str = "",
    ) -> CoverageGapDetail:
        gap_detail = CoverageGapDetail(
            service=service,
            incident_type=incident_type,
            gap=gap,
            priority=priority,
            recommended_action=recommended_action,
            description=description,
        )
        self._gaps.append(gap_detail)
        if len(self._gaps) > self._max_records:
            self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "runbook_coverage.gap_added",
            gap_id=gap_detail.id,
            service=service,
            gap=gap.value,
        )
        return gap_detail

    # -- Domain operations --

    def analyze_coverage_by_service(self) -> dict[str, Any]:
        """Compute coverage metrics grouped by service."""
        service_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if not r.service:
                continue
            if r.service not in service_data:
                service_data[r.service] = {"total": 0, "scores": [], "uncovered": 0}
            service_data[r.service]["total"] += 1
            service_data[r.service]["scores"].append(r.coverage_score)
            if r.coverage_level == CoverageLevel.NONE:
                service_data[r.service]["uncovered"] += 1
        breakdown: list[dict[str, Any]] = []
        for service, data in service_data.items():
            scores = data["scores"]
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            covered_ratio = (1 - data["uncovered"] / data["total"]) if data["total"] else 0.0
            coverage_pct = round(covered_ratio * 100, 2)
            breakdown.append(
                {
                    "service": service,
                    "total_scenarios": data["total"],
                    "uncovered_count": data["uncovered"],
                    "coverage_pct": coverage_pct,
                    "avg_coverage_score": avg_score,
                }
            )
        breakdown.sort(key=lambda x: x["avg_coverage_score"], reverse=True)
        return {
            "total_services": len(service_data),
            "breakdown": breakdown,
        }

    def identify_uncovered_scenarios(self) -> list[dict[str, Any]]:
        """Return all scenarios with no runbook coverage."""
        uncovered = [r for r in self._records if r.coverage_level == CoverageLevel.NONE]
        return [
            {
                "record_id": r.id,
                "service": r.service,
                "incident_type": r.incident_type.value,
                "coverage_score": r.coverage_score,
                "gap": r.gap.value if r.gap else None,
            }
            for r in uncovered
        ]

    def rank_by_coverage_score(self) -> list[dict[str, Any]]:
        """Rank services by average coverage score (ascending — lowest first = most at risk)."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            if not r.service:
                continue
            service_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            results.append(
                {
                    "service": service,
                    "avg_coverage_score": avg_score,
                    "scenario_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"])
        return results

    def detect_coverage_trends(self) -> dict[str, Any]:
        """Detect whether coverage is improving or worsening over time."""
        if len(self._records) < 4:
            return {"trend": "insufficient_data", "sample_count": len(self._records)}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _avg_score(records: list[CoverageRecord]) -> float:
            if not records:
                return 0.0
            return round(sum(r.coverage_score for r in records) / len(records), 2)

        first_score = _avg_score(first_half)
        second_score = _avg_score(second_half)
        delta = round(second_score - first_score, 2)
        if delta > 5.0:
            trend = "improving"
        elif delta < -5.0:
            trend = "worsening"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_avg_score": first_score,
            "second_half_avg_score": second_score,
            "delta": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> RunbookCoverageReport:
        by_coverage_level: dict[str, int] = {}
        by_incident_type: dict[str, int] = {}
        by_gap_type: dict[str, int] = {}
        for r in self._records:
            by_coverage_level[r.coverage_level.value] = (
                by_coverage_level.get(r.coverage_level.value, 0) + 1
            )
            by_incident_type[r.incident_type.value] = (
                by_incident_type.get(r.incident_type.value, 0) + 1
            )
            if r.gap is not None:
                by_gap_type[r.gap.value] = by_gap_type.get(r.gap.value, 0) + 1
        total = len(self._records)
        fully_covered = by_coverage_level.get(CoverageLevel.FULL.value, 0)
        uncovered = by_coverage_level.get(CoverageLevel.NONE.value, 0)
        avg_score = round(sum(r.coverage_score for r in self._records) / total, 4) if total else 0.0
        service_data = self.analyze_coverage_by_service()
        low_coverage = sorted(
            service_data.get("breakdown", []), key=lambda x: x["avg_coverage_score"]
        )
        top_uncovered = [b["service"] for b in low_coverage[:5]]
        recs: list[str] = []
        if avg_score * 100 < self._min_coverage_pct:
            recs.append(
                f"Avg coverage score {round(avg_score * 100, 1)}% below minimum"
                f" {self._min_coverage_pct}% — create missing runbooks"
            )
        if uncovered > 0:
            recs.append(f"{uncovered} scenarios have no runbook — prioritize coverage creation")
        if not self._gaps:
            recs.append("No gap details registered — run gap analysis to identify coverage holes")
        if not recs:
            recs.append("Runbook coverage meets target thresholds")
        return RunbookCoverageReport(
            total_records=total,
            total_gaps=len(self._gaps),
            fully_covered=fully_covered,
            uncovered=uncovered,
            avg_coverage_score=avg_score,
            by_coverage_level=by_coverage_level,
            by_incident_type=by_incident_type,
            by_gap_type=by_gap_type,
            top_uncovered_services=top_uncovered,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("runbook_coverage.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            level_dist[r.coverage_level.value] = level_dist.get(r.coverage_level.value, 0) + 1
        automated_count = sum(1 for r in self._records if r.automated)
        avg_score = (
            round(sum(r.coverage_score for r in self._records) / len(self._records), 4)
            if self._records
            else 0.0
        )
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "automated_count": automated_count,
            "min_coverage_pct": self._min_coverage_pct,
            "avg_coverage_score": avg_score,
            "level_distribution": level_dist,
            "unique_services": len({r.service for r in self._records if r.service}),
        }
