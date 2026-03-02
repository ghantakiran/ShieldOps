"""Attack Path Analyzer — analyze and visualize attack paths across infrastructure."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PathType(StrEnum):
    NETWORK = "network"
    IDENTITY = "identity"
    APPLICATION = "application"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class PathComplexity(StrEnum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


class PathRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    THEORETICAL = "theoretical"


# --- Models ---


class AttackPathRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path_name: str = ""
    path_type: PathType = PathType.NETWORK
    path_complexity: PathComplexity = PathComplexity.MODERATE
    path_risk: PathRisk = PathRisk.MEDIUM
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AttackPathAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path_name: str = ""
    path_type: PathType = PathType.NETWORK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AttackPathReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_path_type: dict[str, int] = Field(default_factory=dict)
    by_complexity: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AttackPathAnalyzer:
    """Analyze and visualize attack paths across infrastructure."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[AttackPathRecord] = []
        self._analyses: list[AttackPathAnalysis] = []
        logger.info(
            "attack_path_analyzer.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_path(
        self,
        path_name: str,
        path_type: PathType = PathType.NETWORK,
        path_complexity: PathComplexity = PathComplexity.MODERATE,
        path_risk: PathRisk = PathRisk.MEDIUM,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AttackPathRecord:
        record = AttackPathRecord(
            path_name=path_name,
            path_type=path_type,
            path_complexity=path_complexity,
            path_risk=path_risk,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "attack_path_analyzer.path_recorded",
            record_id=record.id,
            path_name=path_name,
            path_type=path_type.value,
            path_complexity=path_complexity.value,
        )
        return record

    def get_path(self, record_id: str) -> AttackPathRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_paths(
        self,
        path_type: PathType | None = None,
        path_complexity: PathComplexity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AttackPathRecord]:
        results = list(self._records)
        if path_type is not None:
            results = [r for r in results if r.path_type == path_type]
        if path_complexity is not None:
            results = [r for r in results if r.path_complexity == path_complexity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        path_name: str,
        path_type: PathType = PathType.NETWORK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AttackPathAnalysis:
        analysis = AttackPathAnalysis(
            path_name=path_name,
            path_type=path_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "attack_path_analyzer.analysis_added",
            path_name=path_name,
            path_type=path_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by path_type; return count and avg risk_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.path_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for path_type, scores in type_data.items():
            result[path_type] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "path_name": r.path_name,
                        "path_type": r.path_type.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
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
        results.sort(key=lambda x: x["avg_risk_score"])
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

    def generate_report(self) -> AttackPathReport:
        by_path_type: dict[str, int] = {}
        by_complexity: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_path_type[r.path_type.value] = by_path_type.get(r.path_type.value, 0) + 1
            by_complexity[r.path_complexity.value] = (
                by_complexity.get(r.path_complexity.value, 0) + 1
            )
            by_risk[r.path_risk.value] = by_risk.get(r.path_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["path_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} attack path(s) below risk threshold ({self._risk_threshold})")
        if self._records and avg_risk_score < self._risk_threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._risk_threshold})")
        if not recs:
            recs.append("Attack path analysis is healthy")
        return AttackPathReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_path_type=by_path_type,
            by_complexity=by_complexity,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("attack_path_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.path_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "path_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
