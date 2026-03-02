"""Threat Actor TTP Profiler — profile threat actor tactics, techniques, and procedures."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TTPCategory(StrEnum):
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    LATERAL_MOVEMENT = "lateral_movement"
    EXFILTRATION = "exfiltration"


class ActorSophistication(StrEnum):
    ADVANCED = "advanced"
    INTERMEDIATE = "intermediate"
    BASIC = "basic"
    SCRIPT_KIDDIE = "script_kiddie"
    UNKNOWN = "unknown"


class ProfileConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"
    UNVERIFIED = "unverified"


# --- Models ---


class TTPRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor_name: str = ""
    ttp_category: TTPCategory = TTPCategory.INITIAL_ACCESS
    actor_sophistication: ActorSophistication = ActorSophistication.UNKNOWN
    profile_confidence: ProfileConfidence = ProfileConfidence.LOW
    technique_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TTPAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor_name: str = ""
    ttp_category: TTPCategory = TTPCategory.INITIAL_ACCESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TTPProfileReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_technique_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_sophistication: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatActorTTPProfiler:
    """Profile threat actor tactics, techniques, and procedures."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[TTPRecord] = []
        self._analyses: list[TTPAnalysis] = []
        logger.info(
            "threat_actor_ttp_profiler.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_ttp(
        self,
        actor_name: str,
        ttp_category: TTPCategory = TTPCategory.INITIAL_ACCESS,
        actor_sophistication: ActorSophistication = ActorSophistication.UNKNOWN,
        profile_confidence: ProfileConfidence = ProfileConfidence.LOW,
        technique_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TTPRecord:
        record = TTPRecord(
            actor_name=actor_name,
            ttp_category=ttp_category,
            actor_sophistication=actor_sophistication,
            profile_confidence=profile_confidence,
            technique_score=technique_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_actor_ttp_profiler.recorded",
            record_id=record.id,
            actor_name=actor_name,
            ttp_category=ttp_category.value,
        )
        return record

    def get_record(self, record_id: str) -> TTPRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        ttp_category: TTPCategory | None = None,
        actor_sophistication: ActorSophistication | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TTPRecord]:
        results = list(self._records)
        if ttp_category is not None:
            results = [r for r in results if r.ttp_category == ttp_category]
        if actor_sophistication is not None:
            results = [r for r in results if r.actor_sophistication == actor_sophistication]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        actor_name: str,
        ttp_category: TTPCategory = TTPCategory.INITIAL_ACCESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TTPAnalysis:
        analysis = TTPAnalysis(
            actor_name=actor_name,
            ttp_category=ttp_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "threat_actor_ttp_profiler.analysis_added",
            actor_name=actor_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_category_distribution(self) -> dict[str, Any]:
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.ttp_category.value
            cat_data.setdefault(key, []).append(r.technique_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_technique_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.technique_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "actor_name": r.actor_name,
                        "ttp_category": r.ttp_category.value,
                        "technique_score": r.technique_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["technique_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.technique_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_technique_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_technique_score"])
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

    def generate_report(self) -> TTPProfileReport:
        by_category: dict[str, int] = {}
        by_sophistication: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_category[r.ttp_category.value] = by_category.get(r.ttp_category.value, 0) + 1
            by_sophistication[r.actor_sophistication.value] = (
                by_sophistication.get(r.actor_sophistication.value, 0) + 1
            )
            by_confidence[r.profile_confidence.value] = (
                by_confidence.get(r.profile_confidence.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.technique_score < self._quality_threshold)
        scores = [r.technique_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["actor_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} TTP profile(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg technique score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Threat actor TTP profiling is healthy")
        return TTPProfileReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_technique_score=avg_score,
            by_category=by_category,
            by_sophistication=by_sophistication,
            by_confidence=by_confidence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_actor_ttp_profiler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.ttp_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
