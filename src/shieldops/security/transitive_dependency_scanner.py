"""Transitive Dependency Scanner — scan and risk-score transitive dependencies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyDepth(StrEnum):
    DIRECT = "direct"
    FIRST_LEVEL = "first_level"
    SECOND_LEVEL = "second_level"
    DEEP = "deep"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ScanScope(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TEST = "test"
    BUILD = "build"
    ALL = "all"


# --- Models ---


class DependencyScan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    dependency_depth: DependencyDepth = DependencyDepth.DIRECT
    risk_level: RiskLevel = RiskLevel.NONE
    scan_scope: ScanScope = ScanScope.ALL
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ScanAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    dependency_depth: DependencyDepth = DependencyDepth.DIRECT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyScanReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_depth: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TransitiveDependencyScanner:
    """Scan transitive dependencies for risk, depth, and policy compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_gap_threshold = risk_gap_threshold
        self._records: list[DependencyScan] = []
        self._analyses: list[ScanAnalysis] = []
        logger.info(
            "transitive_dependency_scanner.initialized",
            max_records=max_records,
            risk_gap_threshold=risk_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_scan(
        self,
        package_name: str,
        dependency_depth: DependencyDepth = DependencyDepth.DIRECT,
        risk_level: RiskLevel = RiskLevel.NONE,
        scan_scope: ScanScope = ScanScope.ALL,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DependencyScan:
        record = DependencyScan(
            package_name=package_name,
            dependency_depth=dependency_depth,
            risk_level=risk_level,
            scan_scope=scan_scope,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "transitive_dependency_scanner.scan_recorded",
            record_id=record.id,
            package_name=package_name,
            dependency_depth=dependency_depth.value,
            risk_level=risk_level.value,
        )
        return record

    def get_scan(self, record_id: str) -> DependencyScan | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scans(
        self,
        dependency_depth: DependencyDepth | None = None,
        risk_level: RiskLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DependencyScan]:
        results = list(self._records)
        if dependency_depth is not None:
            results = [r for r in results if r.dependency_depth == dependency_depth]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        package_name: str,
        dependency_depth: DependencyDepth = DependencyDepth.DIRECT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ScanAnalysis:
        analysis = ScanAnalysis(
            package_name=package_name,
            dependency_depth=dependency_depth,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "transitive_dependency_scanner.analysis_added",
            package_name=package_name,
            dependency_depth=dependency_depth.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_depth_distribution(self) -> dict[str, Any]:
        """Group by dependency_depth; return count and avg risk_score."""
        depth_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dependency_depth.value
            depth_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for depth, scores in depth_data.items():
            result[depth] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_risk_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score >= risk_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score >= self._risk_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "package_name": r.package_name,
                        "dependency_depth": r.dependency_depth.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DependencyScanReport:
        by_depth: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_depth[r.dependency_depth.value] = by_depth.get(r.dependency_depth.value, 0) + 1
            by_risk[r.risk_level.value] = by_risk.get(r.risk_level.value, 0) + 1
            by_scope[r.scan_scope.value] = by_scope.get(r.scan_scope.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score >= self._risk_gap_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_risk_gaps()
        top_gaps = [o["package_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} package(s) above risk threshold ({self._risk_gap_threshold})")
        if self._records and avg_risk_score >= self._risk_gap_threshold:
            recs.append(
                f"Avg risk score {avg_risk_score} above threshold ({self._risk_gap_threshold})"
            )
        if not recs:
            recs.append("Transitive dependency risk is healthy")
        return DependencyScanReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_depth=by_depth,
            by_risk=by_risk,
            by_scope=by_scope,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("transitive_dependency_scanner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        depth_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dependency_depth.value
            depth_dist[key] = depth_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_gap_threshold": self._risk_gap_threshold,
            "depth_distribution": depth_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
