"""Entity Behavior Profiler — profile entity behaviors and detect anomalies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EntityType(StrEnum):
    USER = "user"
    SERVICE_ACCOUNT = "service_account"
    DEVICE = "device"
    APPLICATION = "application"
    NETWORK_SEGMENT = "network_segment"


class BehaviorCategory(StrEnum):
    AUTHENTICATION = "authentication"
    DATA_ACCESS = "data_access"
    NETWORK_ACTIVITY = "network_activity"
    PRIVILEGE_USE = "privilege_use"
    RESOURCE_CONSUMPTION = "resource_consumption"


class ProfileStatus(StrEnum):
    BASELINE = "baseline"
    NORMAL = "normal"
    ANOMALOUS = "anomalous"
    SUSPICIOUS = "suspicious"
    COMPROMISED = "compromised"


# --- Models ---


class BehaviorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    entity_type: EntityType = EntityType.USER
    behavior_category: BehaviorCategory = BehaviorCategory.AUTHENTICATION
    profile_status: ProfileStatus = ProfileStatus.BASELINE
    behavior_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BehaviorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    entity_type: EntityType = EntityType.USER
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BehaviorProfileReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_behavior_score: float = 0.0
    by_entity_type: dict[str, int] = Field(default_factory=dict)
    by_behavior_category: dict[str, int] = Field(default_factory=dict)
    by_profile_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class EntityBehaviorProfiler:
    """Profile entity behaviors, detect anomalies, and track behavioral baselines."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[BehaviorRecord] = []
        self._analyses: list[BehaviorAnalysis] = []
        logger.info(
            "entity_behavior_profiler.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_behavior(
        self,
        entity_name: str,
        entity_type: EntityType = EntityType.USER,
        behavior_category: BehaviorCategory = BehaviorCategory.AUTHENTICATION,
        profile_status: ProfileStatus = ProfileStatus.BASELINE,
        behavior_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BehaviorRecord:
        record = BehaviorRecord(
            entity_name=entity_name,
            entity_type=entity_type,
            behavior_category=behavior_category,
            profile_status=profile_status,
            behavior_score=behavior_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "entity_behavior_profiler.behavior_recorded",
            record_id=record.id,
            entity_name=entity_name,
            entity_type=entity_type.value,
            behavior_category=behavior_category.value,
        )
        return record

    def get_record(self, record_id: str) -> BehaviorRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        entity_type: EntityType | None = None,
        behavior_category: BehaviorCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BehaviorRecord]:
        results = list(self._records)
        if entity_type is not None:
            results = [r for r in results if r.entity_type == entity_type]
        if behavior_category is not None:
            results = [r for r in results if r.behavior_category == behavior_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        entity_name: str,
        entity_type: EntityType = EntityType.USER,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BehaviorAnalysis:
        analysis = BehaviorAnalysis(
            entity_name=entity_name,
            entity_type=entity_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "entity_behavior_profiler.analysis_added",
            entity_name=entity_name,
            entity_type=entity_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by entity_type; return count and avg behavior_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.entity_type.value
            type_data.setdefault(key, []).append(r.behavior_score)
        result: dict[str, Any] = {}
        for etype, scores in type_data.items():
            result[etype] = {
                "count": len(scores),
                "avg_behavior_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where behavior_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.behavior_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "entity_name": r.entity_name,
                        "entity_type": r.entity_type.value,
                        "behavior_score": r.behavior_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["behavior_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg behavior_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.behavior_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_behavior_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_behavior_score"])
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

    def generate_report(self) -> BehaviorProfileReport:
        by_entity_type: dict[str, int] = {}
        by_behavior_category: dict[str, int] = {}
        by_profile_status: dict[str, int] = {}
        for r in self._records:
            by_entity_type[r.entity_type.value] = by_entity_type.get(r.entity_type.value, 0) + 1
            by_behavior_category[r.behavior_category.value] = (
                by_behavior_category.get(r.behavior_category.value, 0) + 1
            )
            by_profile_status[r.profile_status.value] = (
                by_profile_status.get(r.profile_status.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.behavior_score < self._threshold)
        scores = [r.behavior_score for r in self._records]
        avg_behavior_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["entity_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} entity(s) below behavior threshold ({self._threshold})")
        if self._records and avg_behavior_score < self._threshold:
            recs.append(
                f"Avg behavior score {avg_behavior_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Entity behavior profiling is healthy")
        return BehaviorProfileReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_behavior_score=avg_behavior_score,
            by_entity_type=by_entity_type,
            by_behavior_category=by_behavior_category,
            by_profile_status=by_profile_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("entity_behavior_profiler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        entity_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.entity_type.value
            entity_type_dist[key] = entity_type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "entity_type_distribution": entity_type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
