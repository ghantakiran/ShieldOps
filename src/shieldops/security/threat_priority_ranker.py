"""Threat Priority Ranker — rank and prioritize threats by risk and impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatType(StrEnum):
    MALWARE = "malware"
    RANSOMWARE = "ransomware"
    PHISHING = "phishing"
    APT = "apt"
    INSIDER = "insider"


class PriorityLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RankingMethod(StrEnum):
    RISK_BASED = "risk_based"
    IMPACT_BASED = "impact_based"
    LIKELIHOOD_BASED = "likelihood_based"
    COMPOSITE = "composite"
    CUSTOM = "custom"


# --- Models ---


class PriorityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_name: str = ""
    threat_type: ThreatType = ThreatType.MALWARE
    priority_level: PriorityLevel = PriorityLevel.MEDIUM
    ranking_method: RankingMethod = RankingMethod.RISK_BASED
    priority_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PriorityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threat_name: str = ""
    threat_type: ThreatType = ThreatType.MALWARE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PriorityRankingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_priority_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatPriorityRanker:
    """Rank and prioritize threats by risk, impact, and likelihood."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[PriorityRecord] = []
        self._analyses: list[PriorityAnalysis] = []
        logger.info(
            "threat_priority_ranker.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_priority(
        self,
        threat_name: str,
        threat_type: ThreatType = ThreatType.MALWARE,
        priority_level: PriorityLevel = PriorityLevel.MEDIUM,
        ranking_method: RankingMethod = RankingMethod.RISK_BASED,
        priority_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PriorityRecord:
        record = PriorityRecord(
            threat_name=threat_name,
            threat_type=threat_type,
            priority_level=priority_level,
            ranking_method=ranking_method,
            priority_score=priority_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_priority_ranker.recorded",
            record_id=record.id,
            threat_name=threat_name,
            threat_type=threat_type.value,
        )
        return record

    def get_record(self, record_id: str) -> PriorityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        threat_type: ThreatType | None = None,
        priority_level: PriorityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PriorityRecord]:
        results = list(self._records)
        if threat_type is not None:
            results = [r for r in results if r.threat_type == threat_type]
        if priority_level is not None:
            results = [r for r in results if r.priority_level == priority_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        threat_name: str,
        threat_type: ThreatType = ThreatType.MALWARE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PriorityAnalysis:
        analysis = PriorityAnalysis(
            threat_name=threat_name,
            threat_type=threat_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "threat_priority_ranker.analysis_added",
            threat_name=threat_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_type_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threat_type.value
            type_data.setdefault(key, []).append(r.priority_score)
        result: dict[str, Any] = {}
        for ttype, scores in type_data.items():
            result[ttype] = {
                "count": len(scores),
                "avg_priority_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.priority_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "threat_name": r.threat_name,
                        "threat_type": r.threat_type.value,
                        "priority_score": r.priority_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["priority_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.priority_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_priority_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_priority_score"])
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

    def generate_report(self) -> PriorityRankingReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_type[r.threat_type.value] = by_type.get(r.threat_type.value, 0) + 1
            by_level[r.priority_level.value] = by_level.get(r.priority_level.value, 0) + 1
            by_method[r.ranking_method.value] = by_method.get(r.ranking_method.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.priority_score < self._quality_threshold)
        scores = [r.priority_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["threat_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} threat(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg priority score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Threat priority ranking is healthy")
        return PriorityRankingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_priority_score=avg_score,
            by_type=by_type,
            by_level=by_level,
            by_method=by_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_priority_ranker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.threat_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
