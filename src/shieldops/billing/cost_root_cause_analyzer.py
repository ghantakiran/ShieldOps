"""Cost Root Cause Analyzer — identify root causes of cost increases."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RootCause(StrEnum):
    CONFIG_CHANGE = "config_change"
    TRAFFIC_SPIKE = "traffic_spike"
    RESOURCE_LEAK = "resource_leak"
    PRICING_CHANGE = "pricing_change"
    MISCONFIGURATION = "misconfiguration"


class AnalysisDepth(StrEnum):
    SURFACE = "surface"
    MODERATE = "moderate"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"
    TARGETED = "targeted"


class ImpactCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATA_TRANSFER = "data_transfer"
    LICENSING = "licensing"


# --- Models ---


class RootCauseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    root_cause: RootCause = RootCause.MISCONFIGURATION
    analysis_depth: AnalysisDepth = AnalysisDepth.MODERATE
    impact_category: ImpactCategory = ImpactCategory.COMPUTE
    cost_impact: float = 0.0
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CauseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    root_cause: RootCause = RootCause.MISCONFIGURATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RootCauseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_confidence_count: int = 0
    avg_cost_impact: float = 0.0
    by_root_cause: dict[str, int] = Field(default_factory=dict)
    by_analysis_depth: dict[str, int] = Field(default_factory=dict)
    by_impact_category: dict[str, int] = Field(default_factory=dict)
    top_causes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostRootCauseAnalyzer:
    """Identify and attribute root causes of cloud cost increases."""

    def __init__(
        self,
        max_records: int = 200000,
        confidence_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._confidence_threshold = confidence_threshold
        self._records: list[RootCauseRecord] = []
        self._analyses: list[CauseAnalysis] = []
        logger.info(
            "cost_root_cause_analyzer.initialized",
            max_records=max_records,
            confidence_threshold=confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_root_cause(
        self,
        root_cause: RootCause = RootCause.MISCONFIGURATION,
        analysis_depth: AnalysisDepth = AnalysisDepth.MODERATE,
        impact_category: ImpactCategory = ImpactCategory.COMPUTE,
        cost_impact: float = 0.0,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RootCauseRecord:
        record = RootCauseRecord(
            root_cause=root_cause,
            analysis_depth=analysis_depth,
            impact_category=impact_category,
            cost_impact=cost_impact,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_root_cause_analyzer.cause_recorded",
            record_id=record.id,
            root_cause=root_cause.value,
            confidence_score=confidence_score,
        )
        return record

    def get_root_cause(self, record_id: str) -> RootCauseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_root_causes(
        self,
        root_cause: RootCause | None = None,
        impact_category: ImpactCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RootCauseRecord]:
        results = list(self._records)
        if root_cause is not None:
            results = [r for r in results if r.root_cause == root_cause]
        if impact_category is not None:
            results = [r for r in results if r.impact_category == impact_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        root_cause: RootCause = RootCause.MISCONFIGURATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CauseAnalysis:
        analysis = CauseAnalysis(
            root_cause=root_cause,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cost_root_cause_analyzer.analysis_added",
            root_cause=root_cause.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_cause_distribution(self) -> dict[str, Any]:
        """Group by root_cause; return count and avg cost_impact."""
        cause_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.root_cause.value
            cause_data.setdefault(key, []).append(r.cost_impact)
        result: dict[str, Any] = {}
        for cause, impacts in cause_data.items():
            result[cause] = {
                "count": len(impacts),
                "avg_cost_impact": round(sum(impacts) / len(impacts), 2),
            }
        return result

    def identify_high_confidence_causes(self) -> list[dict[str, Any]]:
        """Return records where confidence_score >= confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score >= self._confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "root_cause": r.root_cause.value,
                        "impact_category": r.impact_category.value,
                        "cost_impact": r.cost_impact,
                        "confidence_score": r.confidence_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["cost_impact"], reverse=True)

    def rank_by_cost_impact(self) -> list[dict[str, Any]]:
        """Group by service, total cost_impact, sort descending."""
        svc_impacts: dict[str, float] = {}
        for r in self._records:
            svc_impacts[r.service] = svc_impacts.get(r.service, 0.0) + r.cost_impact
        results: list[dict[str, Any]] = [
            {"service": svc, "total_cost_impact": round(imp, 2)} for svc, imp in svc_impacts.items()
        ]
        results.sort(key=lambda x: x["total_cost_impact"], reverse=True)
        return results

    def detect_confidence_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RootCauseReport:
        by_cause: dict[str, int] = {}
        by_depth: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_cause[r.root_cause.value] = by_cause.get(r.root_cause.value, 0) + 1
            by_depth[r.analysis_depth.value] = by_depth.get(r.analysis_depth.value, 0) + 1
            by_category[r.impact_category.value] = by_category.get(r.impact_category.value, 0) + 1
        high_confidence_count = sum(
            1 for r in self._records if r.confidence_score >= self._confidence_threshold
        )
        impacts = [r.cost_impact for r in self._records]
        avg_cost_impact = round(sum(impacts) / len(impacts), 2) if impacts else 0.0
        high_list = self.identify_high_confidence_causes()
        top_causes = [o["record_id"] for o in high_list[:5]]
        recs: list[str] = []
        if high_confidence_count > 0:
            recs.append(f"{high_confidence_count} high-confidence root cause(s) identified")
        if avg_cost_impact > 0:
            recs.append(f"Avg cost impact ${avg_cost_impact:.2f} per root cause event")
        if not recs:
            recs.append("Cost root cause analysis is healthy")
        return RootCauseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_confidence_count=high_confidence_count,
            avg_cost_impact=avg_cost_impact,
            by_root_cause=by_cause,
            by_analysis_depth=by_depth,
            by_impact_category=by_category,
            top_causes=top_causes,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cost_root_cause_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cause_dist: dict[str, int] = {}
        for r in self._records:
            key = r.root_cause.value
            cause_dist[key] = cause_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "confidence_threshold": self._confidence_threshold,
            "root_cause_distribution": cause_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
