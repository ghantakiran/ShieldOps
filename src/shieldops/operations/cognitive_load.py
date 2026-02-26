"""Team Cognitive Load Tracker — measure and manage team cognitive load."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LoadSource(StrEnum):
    ALERT_VOLUME = "alert_volume"
    CONTEXT_SWITCHING = "context_switching"
    CONCURRENT_INCIDENTS = "concurrent_incidents"
    DEPLOYMENT_FREQUENCY = "deployment_frequency"
    TOIL = "toil"


class LoadLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class LoadTrend(StrEnum):
    WORSENING = "worsening"
    STABLE = "stable"
    IMPROVING = "improving"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class CognitiveLoadRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_name: str = ""
    source: LoadSource = LoadSource.ALERT_VOLUME
    level: LoadLevel = LoadLevel.MODERATE
    load_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LoadContributor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contributor_name: str = ""
    source: LoadSource = LoadSource.ALERT_VOLUME
    level: LoadLevel = LoadLevel.MODERATE
    impact_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CognitiveLoadReport(BaseModel):
    total_loads: int = 0
    total_contributors: int = 0
    avg_load_score_pct: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    overloaded_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamCognitiveLoadTracker:
    """Track team cognitive load, contributors, and overload detection."""

    def __init__(
        self,
        max_records: int = 200000,
        critical_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._critical_threshold = critical_threshold
        self._records: list[CognitiveLoadRecord] = []
        self._contributors: list[LoadContributor] = []
        logger.info(
            "cognitive_load.initialized",
            max_records=max_records,
            critical_threshold=critical_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_load(
        self,
        team_name: str,
        source: LoadSource = LoadSource.ALERT_VOLUME,
        level: LoadLevel = LoadLevel.MODERATE,
        load_score: float = 0.0,
        details: str = "",
    ) -> CognitiveLoadRecord:
        record = CognitiveLoadRecord(
            team_name=team_name,
            source=source,
            level=level,
            load_score=load_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cognitive_load.recorded",
            record_id=record.id,
            team_name=team_name,
            source=source.value,
            level=level.value,
        )
        return record

    def get_load(self, record_id: str) -> CognitiveLoadRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_loads(
        self,
        team_name: str | None = None,
        source: LoadSource | None = None,
        limit: int = 50,
    ) -> list[CognitiveLoadRecord]:
        results = list(self._records)
        if team_name is not None:
            results = [r for r in results if r.team_name == team_name]
        if source is not None:
            results = [r for r in results if r.source == source]
        return results[-limit:]

    def add_contributor(
        self,
        contributor_name: str,
        source: LoadSource = LoadSource.ALERT_VOLUME,
        level: LoadLevel = LoadLevel.MODERATE,
        impact_score: float = 0.0,
        description: str = "",
    ) -> LoadContributor:
        contributor = LoadContributor(
            contributor_name=contributor_name,
            source=source,
            level=level,
            impact_score=impact_score,
            description=description,
        )
        self._contributors.append(contributor)
        if len(self._contributors) > self._max_records:
            self._contributors = self._contributors[-self._max_records :]
        logger.info(
            "cognitive_load.contributor_added",
            contributor_name=contributor_name,
            source=source.value,
            level=level.value,
        )
        return contributor

    # -- domain operations -----------------------------------------------

    def analyze_team_load(self, team_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.team_name == team_name]
        if not records:
            return {"team_name": team_name, "status": "no_data"}
        avg_score = round(sum(r.load_score for r in records) / len(records), 2)
        overloaded = sum(1 for r in records if r.level in (LoadLevel.CRITICAL, LoadLevel.HIGH))
        return {
            "team_name": team_name,
            "total_records": len(records),
            "avg_load_score": avg_score,
            "overloaded_count": overloaded,
            "exceeds_threshold": avg_score >= self._critical_threshold,
        }

    def identify_overloaded_teams(self) -> list[dict[str, Any]]:
        overload_counts: dict[str, int] = {}
        for r in self._records:
            if r.level in (LoadLevel.CRITICAL, LoadLevel.HIGH):
                overload_counts[r.team_name] = overload_counts.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in overload_counts.items():
            if count > 1:
                results.append({"team_name": team, "overloaded_count": count})
        results.sort(key=lambda x: x["overloaded_count"], reverse=True)
        return results

    def rank_by_load_score(self) -> list[dict[str, Any]]:
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team_name, []).append(r.load_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team_name": team,
                    "avg_load_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_load_score"], reverse=True)
        return results

    def detect_load_trends(self) -> list[dict[str, Any]]:
        team_counts: dict[str, int] = {}
        for r in self._records:
            team_counts[r.team_name] = team_counts.get(r.team_name, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in team_counts.items():
            if count > 3:
                results.append(
                    {
                        "team_name": team,
                        "load_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["load_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CognitiveLoadReport:
        by_source: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_level[r.level.value] = by_level.get(r.level.value, 0) + 1
        avg_score = (
            round(sum(r.load_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        overloaded = sum(
            1 for r in self._records if r.level in (LoadLevel.CRITICAL, LoadLevel.HIGH)
        )
        recs: list[str] = []
        if avg_score >= self._critical_threshold:
            recs.append(
                f"Average load score {avg_score}% exceeds {self._critical_threshold}% threshold"
            )
        trends = len(self.detect_load_trends())
        if trends > 0:
            recs.append(f"{trends} team(s) with recurring load trends")
        if not recs:
            recs.append("Cognitive load levels within acceptable range")
        return CognitiveLoadReport(
            total_loads=len(self._records),
            total_contributors=len(self._contributors),
            avg_load_score_pct=avg_score,
            by_source=by_source,
            by_level=by_level,
            overloaded_count=overloaded,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._contributors.clear()
        logger.info("cognitive_load.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_loads": len(self._records),
            "total_contributors": len(self._contributors),
            "critical_threshold": self._critical_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team_name for r in self._records}),
        }
