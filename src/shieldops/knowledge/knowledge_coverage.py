"""Knowledge Coverage Analyzer — analyze coverage gaps, identify undocumented areas."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CoverageArea(StrEnum):
    RUNBOOKS = "runbooks"
    PLAYBOOKS = "playbooks"
    DOCUMENTATION = "documentation"
    TRAINING = "training"
    TROUBLESHOOTING = "troubleshooting"


class CoverageLevel(StrEnum):
    COMPREHENSIVE = "comprehensive"
    ADEQUATE = "adequate"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class CoverageGapType(StrEnum):
    MISSING_RUNBOOK = "missing_runbook"
    OUTDATED_DOCS = "outdated_docs"
    NO_TRAINING = "no_training"
    INCOMPLETE_PLAYBOOK = "incomplete_playbook"
    UNDOCUMENTED_SERVICE = "undocumented_service"


# --- Models ---


class CoverageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    coverage_area: CoverageArea = CoverageArea.RUNBOOKS
    coverage_level: CoverageLevel = CoverageLevel.NONE
    coverage_gap_type: CoverageGapType = CoverageGapType.MISSING_RUNBOOK
    coverage_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageGapDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_pattern: str = ""
    coverage_area: CoverageArea = CoverageArea.RUNBOOKS
    severity_score: float = 0.0
    affected_services: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_gaps: int = 0
    covered_services: int = 0
    avg_coverage_pct: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_gap_type: dict[str, int] = Field(default_factory=dict)
    uncovered: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeCoverageAnalyzer:
    """Analyze knowledge coverage, identify gaps, track documentation completeness."""

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
            "knowledge_coverage.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_coverage(
        self,
        service_id: str,
        coverage_area: CoverageArea = CoverageArea.RUNBOOKS,
        coverage_level: CoverageLevel = CoverageLevel.NONE,
        coverage_gap_type: CoverageGapType = CoverageGapType.MISSING_RUNBOOK,
        coverage_pct: float = 0.0,
        team: str = "",
    ) -> CoverageRecord:
        record = CoverageRecord(
            service_id=service_id,
            coverage_area=coverage_area,
            coverage_level=coverage_level,
            coverage_gap_type=coverage_gap_type,
            coverage_pct=coverage_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_coverage.coverage_recorded",
            record_id=record.id,
            service_id=service_id,
            coverage_area=coverage_area.value,
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
        coverage_area: CoverageArea | None = None,
        coverage_level: CoverageLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CoverageRecord]:
        results = list(self._records)
        if coverage_area is not None:
            results = [r for r in results if r.coverage_area == coverage_area]
        if coverage_level is not None:
            results = [r for r in results if r.coverage_level == coverage_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_gap(
        self,
        gap_pattern: str,
        coverage_area: CoverageArea = CoverageArea.RUNBOOKS,
        severity_score: float = 0.0,
        affected_services: int = 0,
        description: str = "",
    ) -> CoverageGapDetail:
        gap = CoverageGapDetail(
            gap_pattern=gap_pattern,
            coverage_area=coverage_area,
            severity_score=severity_score,
            affected_services=affected_services,
            description=description,
        )
        self._gaps.append(gap)
        if len(self._gaps) > self._max_records:
            self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "knowledge_coverage.gap_added",
            gap_pattern=gap_pattern,
            coverage_area=coverage_area.value,
            severity_score=severity_score,
        )
        return gap

    # -- domain operations --------------------------------------------------

    def analyze_coverage_patterns(self) -> dict[str, Any]:
        """Group by coverage_area; return count and avg coverage_pct per area."""
        area_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.coverage_area.value
            area_data.setdefault(key, []).append(r.coverage_pct)
        result: dict[str, Any] = {}
        for area, pcts in area_data.items():
            result[area] = {
                "count": len(pcts),
                "avg_coverage_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_coverage_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_pct < min_coverage_pct."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_pct < self._min_coverage_pct:
                results.append(
                    {
                        "record_id": r.id,
                        "service_id": r.service_id,
                        "coverage_pct": r.coverage_pct,
                        "coverage_area": r.coverage_area.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_coverage_score(self) -> list[dict[str, Any]]:
        """Group by team, total coverage_pct, sort descending."""
        team_scores: dict[str, float] = {}
        for r in self._records:
            team_scores[r.team] = team_scores.get(r.team, 0) + r.coverage_pct
        results: list[dict[str, Any]] = []
        for team, total in team_scores.items():
            results.append(
                {
                    "team": team,
                    "total_coverage": total,
                }
            )
        results.sort(key=lambda x: x["total_coverage"], reverse=True)
        return results

    def detect_coverage_trends(self) -> dict[str, Any]:
        """Split-half on coverage_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.coverage_pct for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> KnowledgeCoverageReport:
        by_area: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_gap_type: dict[str, int] = {}
        for r in self._records:
            by_area[r.coverage_area.value] = by_area.get(r.coverage_area.value, 0) + 1
            by_level[r.coverage_level.value] = by_level.get(r.coverage_level.value, 0) + 1
            by_gap_type[r.coverage_gap_type.value] = (
                by_gap_type.get(r.coverage_gap_type.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.coverage_pct < self._min_coverage_pct)
        covered_services = len({r.service_id for r in self._records if r.coverage_pct > 0})
        avg_cov = (
            round(sum(r.coverage_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        uncovered_ids = [
            r.service_id for r in self._records if r.coverage_pct < self._min_coverage_pct
        ][:5]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(
                f"{gap_count} service(s) below minimum coverage ({self._min_coverage_pct}%)"
            )
        if self._records and avg_cov < self._min_coverage_pct:
            recs.append(
                f"Average coverage {avg_cov}% is below threshold ({self._min_coverage_pct}%)"
            )
        if not recs:
            recs.append("Knowledge coverage levels are healthy")
        return KnowledgeCoverageReport(
            total_records=len(self._records),
            total_gaps=len(self._gaps),
            covered_services=covered_services,
            avg_coverage_pct=avg_cov,
            by_area=by_area,
            by_level=by_level,
            by_gap_type=by_gap_type,
            uncovered=uncovered_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("knowledge_coverage.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.coverage_area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "min_coverage_pct": self._min_coverage_pct,
            "area_distribution": area_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_id for r in self._records}),
        }
