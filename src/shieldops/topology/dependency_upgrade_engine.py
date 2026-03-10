"""DependencyUpgradeEngine

Dependency upgrade planning, version lag tracking,
breaking change detection, and upgrade path optimization.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class UpgradeUrgency(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class UpgradeType(StrEnum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    SECURITY = "security"
    TRANSITIVE = "transitive"


class UpgradeRisk(StrEnum):
    BREAKING = "breaking"
    POTENTIALLY_BREAKING = "potentially_breaking"
    SAFE = "safe"
    UNKNOWN = "unknown"
    TESTED = "tested"


# --- Models ---


class DependencyUpgradeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    upgrade_urgency: UpgradeUrgency = UpgradeUrgency.MEDIUM
    upgrade_type: UpgradeType = UpgradeType.PATCH
    upgrade_risk: UpgradeRisk = UpgradeRisk.UNKNOWN
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyUpgradeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    upgrade_urgency: UpgradeUrgency = UpgradeUrgency.MEDIUM
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyUpgradeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_upgrade_urgency: dict[str, int] = Field(default_factory=dict)
    by_upgrade_type: dict[str, int] = Field(default_factory=dict)
    by_upgrade_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyUpgradeEngine:
    """Dependency upgrade planning with version lag tracking."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DependencyUpgradeRecord] = []
        self._analyses: list[DependencyUpgradeAnalysis] = []
        logger.info(
            "dependency.upgrade.engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def record_item(
        self,
        name: str,
        upgrade_urgency: UpgradeUrgency = UpgradeUrgency.MEDIUM,
        upgrade_type: UpgradeType = UpgradeType.PATCH,
        upgrade_risk: UpgradeRisk = UpgradeRisk.UNKNOWN,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DependencyUpgradeRecord:
        record = DependencyUpgradeRecord(
            name=name,
            upgrade_urgency=upgrade_urgency,
            upgrade_type=upgrade_type,
            upgrade_risk=upgrade_risk,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency.upgrade.engine.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> DependencyUpgradeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        upgrade_urgency: UpgradeUrgency | None = None,
        upgrade_type: UpgradeType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DependencyUpgradeRecord]:
        results = list(self._records)
        if upgrade_urgency is not None:
            results = [r for r in results if r.upgrade_urgency == upgrade_urgency]
        if upgrade_type is not None:
            results = [r for r in results if r.upgrade_type == upgrade_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        upgrade_urgency: UpgradeUrgency = UpgradeUrgency.MEDIUM,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DependencyUpgradeAnalysis:
        analysis = DependencyUpgradeAnalysis(
            name=name,
            upgrade_urgency=upgrade_urgency,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "dependency.upgrade.engine.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.upgrade_urgency.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in type_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "upgrade_urgency": r.upgrade_urgency.value,
                        "score": r.score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
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

    def generate_report(self) -> DependencyUpgradeReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.upgrade_urgency.value] = by_e1.get(r.upgrade_urgency.value, 0) + 1
            by_e2[r.upgrade_type.value] = by_e2.get(r.upgrade_type.value, 0) + 1
            by_e3[r.upgrade_risk.value] = by_e3.get(r.upgrade_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Dependency Upgrade Engine is healthy")
        return DependencyUpgradeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_upgrade_urgency=by_e1,
            by_upgrade_type=by_e2,
            by_upgrade_risk=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("dependency.upgrade.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.upgrade_urgency.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "upgrade_urgency_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
