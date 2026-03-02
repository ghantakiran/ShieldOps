"""Strategic Threat Landscape — assess and track the evolving threat landscape."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatCategory(StrEnum):
    NATION_STATE = "nation_state"
    CYBERCRIME = "cybercrime"
    HACKTIVISM = "hacktivism"
    INSIDER_THREAT = "insider_threat"
    SUPPLY_CHAIN = "supply_chain"


class ThreatLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    ELEVATED = "elevated"
    GUARDED = "guarded"
    LOW = "low"


class LandscapeScope(StrEnum):
    GLOBAL_SCOPE = "global_scope"
    REGIONAL = "regional"
    SECTOR = "sector"
    ORGANIZATION = "organization"
    ASSET = "asset"


# --- Models ---


class LandscapeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_name: str = ""
    threat_category: ThreatCategory = ThreatCategory.CYBERCRIME
    threat_level: ThreatLevel = ThreatLevel.LOW
    landscape_scope: LandscapeScope = LandscapeScope.ORGANIZATION
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LandscapeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_name: str = ""
    threat_category: ThreatCategory = ThreatCategory.CYBERCRIME
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LandscapeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class StrategicThreatLandscape:
    """Assess and track the evolving strategic threat landscape."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[LandscapeRecord] = []
        self._analyses: list[LandscapeAnalysis] = []
        logger.info(
            "strategic_threat_landscape.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_threat(
        self,
        threat_name: str,
        threat_category: ThreatCategory = ThreatCategory.CYBERCRIME,
        threat_level: ThreatLevel = ThreatLevel.LOW,
        landscape_scope: LandscapeScope = LandscapeScope.ORGANIZATION,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LandscapeRecord:
        record = LandscapeRecord(
            threat_name=threat_name,
            threat_category=threat_category,
            threat_level=threat_level,
            landscape_scope=landscape_scope,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "strategic_threat_landscape.recorded",
            record_id=record.id,
            threat_name=threat_name,
            threat_category=threat_category.value,
        )
        return record

    def get_record(self, record_id: str) -> LandscapeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        threat_category: ThreatCategory | None = None,
        threat_level: ThreatLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LandscapeRecord]:
        results = list(self._records)
        if threat_category is not None:
            results = [r for r in results if r.threat_category == threat_category]
        if threat_level is not None:
            results = [r for r in results if r.threat_level == threat_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        threat_name: str,
        threat_category: ThreatCategory = ThreatCategory.CYBERCRIME,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LandscapeAnalysis:
        analysis = LandscapeAnalysis(
            threat_name=threat_name,
            threat_category=threat_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "strategic_threat_landscape.analysis_added",
            threat_name=threat_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_category_distribution(self) -> dict[str, Any]:
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threat_category.value
            cat_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "threat_name": r.threat_name,
                        "threat_category": r.threat_category.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
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

    def generate_report(self) -> LandscapeReport:
        by_category: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_category[r.threat_category.value] = by_category.get(r.threat_category.value, 0) + 1
            by_level[r.threat_level.value] = by_level.get(r.threat_level.value, 0) + 1
            by_scope[r.landscape_scope.value] = by_scope.get(r.landscape_scope.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score < self._quality_threshold)
        scores = [r.risk_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["threat_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} threat(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(f"Avg risk score {avg_score} below threshold ({self._quality_threshold})")
        if not recs:
            recs.append("Strategic threat landscape assessment is healthy")
        return LandscapeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_score,
            by_category=by_category,
            by_level=by_level,
            by_scope=by_scope,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("strategic_threat_landscape.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.threat_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
