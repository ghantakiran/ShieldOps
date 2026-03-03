"""Dependency Freshness Enforcer — enforce up-to-date package policies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FreshnessLevel(StrEnum):
    CURRENT = "current"
    OUTDATED = "outdated"
    STALE = "stale"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class UpdateUrgency(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class PackageEcosystem(StrEnum):
    NPM = "npm"
    PYPI = "pypi"
    MAVEN = "maven"
    NUGET = "nuget"
    CARGO = "cargo"


# --- Models ---


class FreshnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    update_urgency: UpdateUrgency = UpdateUrgency.NONE
    package_ecosystem: PackageEcosystem = PackageEcosystem.PYPI
    freshness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FreshnessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyFreshnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_freshness_score: float = 0.0
    by_freshness: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    by_ecosystem: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyFreshnessEnforcer:
    """Enforce dependency freshness policies across package ecosystems."""

    def __init__(
        self,
        max_records: int = 200000,
        freshness_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._freshness_gap_threshold = freshness_gap_threshold
        self._records: list[FreshnessRecord] = []
        self._analyses: list[FreshnessAnalysis] = []
        logger.info(
            "dependency_freshness_enforcer.initialized",
            max_records=max_records,
            freshness_gap_threshold=freshness_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_freshness(
        self,
        package_name: str,
        freshness_level: FreshnessLevel = FreshnessLevel.CURRENT,
        update_urgency: UpdateUrgency = UpdateUrgency.NONE,
        package_ecosystem: PackageEcosystem = PackageEcosystem.PYPI,
        freshness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FreshnessRecord:
        record = FreshnessRecord(
            package_name=package_name,
            freshness_level=freshness_level,
            update_urgency=update_urgency,
            package_ecosystem=package_ecosystem,
            freshness_score=freshness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_freshness_enforcer.freshness_recorded",
            record_id=record.id,
            package_name=package_name,
            freshness_level=freshness_level.value,
            update_urgency=update_urgency.value,
        )
        return record

    def get_freshness(self, record_id: str) -> FreshnessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_freshness_records(
        self,
        freshness_level: FreshnessLevel | None = None,
        package_ecosystem: PackageEcosystem | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FreshnessRecord]:
        results = list(self._records)
        if freshness_level is not None:
            results = [r for r in results if r.freshness_level == freshness_level]
        if package_ecosystem is not None:
            results = [r for r in results if r.package_ecosystem == package_ecosystem]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        package_name: str,
        freshness_level: FreshnessLevel = FreshnessLevel.CURRENT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FreshnessAnalysis:
        analysis = FreshnessAnalysis(
            package_name=package_name,
            freshness_level=freshness_level,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "dependency_freshness_enforcer.analysis_added",
            package_name=package_name,
            freshness_level=freshness_level.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_freshness_distribution(self) -> dict[str, Any]:
        """Group by freshness_level; return count and avg freshness_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.freshness_level.value
            level_data.setdefault(key, []).append(r.freshness_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_freshness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_freshness_gaps(self) -> list[dict[str, Any]]:
        """Return records where freshness_score < freshness_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.freshness_score < self._freshness_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "package_name": r.package_name,
                        "freshness_level": r.freshness_level.value,
                        "freshness_score": r.freshness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["freshness_score"])

    def rank_by_freshness(self) -> list[dict[str, Any]]:
        """Group by service, avg freshness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.freshness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_freshness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_freshness_score"])
        return results

    def detect_freshness_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DependencyFreshnessReport:
        by_freshness: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        by_ecosystem: dict[str, int] = {}
        for r in self._records:
            by_freshness[r.freshness_level.value] = by_freshness.get(r.freshness_level.value, 0) + 1
            by_urgency[r.update_urgency.value] = by_urgency.get(r.update_urgency.value, 0) + 1
            by_ecosystem[r.package_ecosystem.value] = (
                by_ecosystem.get(r.package_ecosystem.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.freshness_score < self._freshness_gap_threshold
        )
        scores = [r.freshness_score for r in self._records]
        avg_freshness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_freshness_gaps()
        top_gaps = [o["package_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} package(s) below freshness threshold "
                f"({self._freshness_gap_threshold})"
            )
        if self._records and avg_freshness_score < self._freshness_gap_threshold:
            recs.append(
                f"Avg freshness score {avg_freshness_score} below threshold "
                f"({self._freshness_gap_threshold})"
            )
        if not recs:
            recs.append("Dependency freshness is healthy")
        return DependencyFreshnessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_freshness_score=avg_freshness_score,
            by_freshness=by_freshness,
            by_urgency=by_urgency,
            by_ecosystem=by_ecosystem,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("dependency_freshness_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.freshness_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "freshness_gap_threshold": self._freshness_gap_threshold,
            "freshness_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
