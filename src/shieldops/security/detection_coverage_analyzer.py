"""Detection Coverage Analyzer — analyze detection coverage across security domains."""

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
    NETWORK = "network"
    ENDPOINT = "endpoint"
    CLOUD = "cloud"
    IDENTITY = "identity"
    APPLICATION = "application"


class CoverageLevel(StrEnum):
    COMPREHENSIVE = "comprehensive"
    SUBSTANTIAL = "substantial"
    MODERATE = "moderate"
    BASIC = "basic"
    NONE = "none"


class DetectionFramework(StrEnum):
    MITRE_ATTACK = "mitre_attack"
    KILL_CHAIN = "kill_chain"
    DIAMOND_MODEL = "diamond_model"
    NIST = "nist"
    CUSTOM = "custom"


# --- Models ---


class CoverageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    area_name: str = ""
    coverage_area: CoverageArea = CoverageArea.NETWORK
    coverage_level: CoverageLevel = CoverageLevel.MODERATE
    detection_framework: DetectionFramework = DetectionFramework.MITRE_ATTACK
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    area_name: str = ""
    coverage_area: CoverageArea = CoverageArea.NETWORK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_framework: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DetectionCoverageAnalyzer:
    """Analyze detection coverage across security domains and frameworks."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CoverageRecord] = []
        self._analyses: list[CoverageAnalysis] = []
        logger.info(
            "detection_coverage_analyzer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_coverage(
        self,
        area_name: str,
        coverage_area: CoverageArea = CoverageArea.NETWORK,
        coverage_level: CoverageLevel = CoverageLevel.MODERATE,
        detection_framework: DetectionFramework = DetectionFramework.MITRE_ATTACK,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CoverageRecord:
        record = CoverageRecord(
            area_name=area_name,
            coverage_area=coverage_area,
            coverage_level=coverage_level,
            detection_framework=detection_framework,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "detection_coverage_analyzer.coverage_recorded",
            record_id=record.id,
            area_name=area_name,
            coverage_area=coverage_area.value,
            coverage_level=coverage_level.value,
        )
        return record

    def get_record(self, record_id: str) -> CoverageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
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

    def add_analysis(
        self,
        area_name: str,
        coverage_area: CoverageArea = CoverageArea.NETWORK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CoverageAnalysis:
        analysis = CoverageAnalysis(
            area_name=area_name,
            coverage_area=coverage_area,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "detection_coverage_analyzer.analysis_added",
            area_name=area_name,
            coverage_area=coverage_area.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by coverage_area; return count and avg coverage_score."""
        area_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.coverage_area.value
            area_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for area, scores in area_data.items():
            result[area] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "area_name": r.area_name,
                        "coverage_area": r.coverage_area.value,
                        "coverage_score": r.coverage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["coverage_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> CoverageReport:
        by_area: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_framework: dict[str, int] = {}
        for r in self._records:
            by_area[r.coverage_area.value] = by_area.get(r.coverage_area.value, 0) + 1
            by_level[r.coverage_level.value] = by_level.get(r.coverage_level.value, 0) + 1
            by_framework[r.detection_framework.value] = (
                by_framework.get(r.detection_framework.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.coverage_score < self._threshold)
        scores = [r.coverage_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["area_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} area(s) below coverage threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg coverage score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Detection coverage is healthy")
        return CoverageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_area=by_area,
            by_level=by_level,
            by_framework=by_framework,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("detection_coverage_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.coverage_area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "area_distribution": area_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
