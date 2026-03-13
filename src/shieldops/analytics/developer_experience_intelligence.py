"""Developer Experience Intelligence —
compute devex score, detect friction points,
rank tools by developer satisfaction."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DevexDimension(StrEnum):
    TOOLING = "tooling"
    DOCUMENTATION = "documentation"
    ONBOARDING = "onboarding"
    WORKFLOW = "workflow"


class FrictionType(StrEnum):
    SETUP = "setup"
    BUILD = "build"
    TEST = "test"
    DEPLOY = "deploy"


class SatisfactionLevel(StrEnum):
    DELIGHTED = "delighted"
    SATISFIED = "satisfied"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"


# --- Models ---


class DevexRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_id: str = ""
    developer_id: str = ""
    dimension: DevexDimension = DevexDimension.TOOLING
    friction: FrictionType = FrictionType.SETUP
    satisfaction: SatisfactionLevel = SatisfactionLevel.NEUTRAL
    score: float = 0.0
    time_lost_minutes: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DevexAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_id: str = ""
    avg_score: float = 0.0
    satisfaction: SatisfactionLevel = SatisfactionLevel.NEUTRAL
    friction_count: int = 0
    respondent_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DevexReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_friction: dict[str, int] = Field(default_factory=dict)
    by_satisfaction: dict[str, int] = Field(default_factory=dict)
    worst_tools: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeveloperExperienceIntelligence:
    """Compute devex score, detect friction points,
    rank tools by developer satisfaction."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DevexRecord] = []
        self._analyses: dict[str, DevexAnalysis] = {}
        logger.info(
            "developer_experience_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        tool_id: str = "",
        developer_id: str = "",
        dimension: DevexDimension = (DevexDimension.TOOLING),
        friction: FrictionType = FrictionType.SETUP,
        satisfaction: SatisfactionLevel = (SatisfactionLevel.NEUTRAL),
        score: float = 0.0,
        time_lost_minutes: float = 0.0,
        description: str = "",
    ) -> DevexRecord:
        record = DevexRecord(
            tool_id=tool_id,
            developer_id=developer_id,
            dimension=dimension,
            friction=friction,
            satisfaction=satisfaction,
            score=score,
            time_lost_minutes=time_lost_minutes,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "developer_experience.record_added",
            record_id=record.id,
            tool_id=tool_id,
        )
        return record

    def process(self, key: str) -> DevexAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        tool_recs = [r for r in self._records if r.tool_id == rec.tool_id]
        scores = [r.score for r in tool_recs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        devs = {r.developer_id for r in tool_recs}
        frictions = sum(
            1
            for r in tool_recs
            if r.satisfaction
            in (
                SatisfactionLevel.NEUTRAL,
                SatisfactionLevel.FRUSTRATED,
            )
        )
        analysis = DevexAnalysis(
            tool_id=rec.tool_id,
            avg_score=avg,
            satisfaction=rec.satisfaction,
            friction_count=frictions,
            respondent_count=len(devs),
            description=(f"Tool {rec.tool_id} avg={avg}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> DevexReport:
        by_d: dict[str, int] = {}
        by_f: dict[str, int] = {}
        by_s: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.dimension.value
            by_d[k] = by_d.get(k, 0) + 1
            k2 = r.friction.value
            by_f[k2] = by_f.get(k2, 0) + 1
            k3 = r.satisfaction.value
            by_s[k3] = by_s.get(k3, 0) + 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        tool_scores: dict[str, list[float]] = {}
        for r in self._records:
            tool_scores.setdefault(r.tool_id, []).append(r.score)
        tool_avgs = {t: sum(s) / len(s) for t, s in tool_scores.items()}
        worst = sorted(
            tool_avgs,
            key=lambda x: tool_avgs[x],
        )[:10]
        recs: list[str] = []
        frustrated = by_s.get("frustrated", 0)
        if frustrated > 0:
            recs.append(f"{frustrated} frustrated responses")
        if not recs:
            recs.append("Developer experience is positive")
        return DevexReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg,
            by_dimension=by_d,
            by_friction=by_f,
            by_satisfaction=by_s,
            worst_tools=worst,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        d_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dimension.value
            d_dist[k] = d_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dimension_distribution": d_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("developer_experience_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_devex_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute devex score per tool."""
        tool_scores: dict[str, list[float]] = {}
        tool_time: dict[str, float] = {}
        for r in self._records:
            tool_scores.setdefault(r.tool_id, []).append(r.score)
            tool_time[r.tool_id] = tool_time.get(r.tool_id, 0.0) + r.time_lost_minutes
        results: list[dict[str, Any]] = []
        for tid, scores in tool_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "tool_id": tid,
                    "devex_score": avg,
                    "time_lost_min": round(tool_time.get(tid, 0.0), 2),
                    "responses": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["devex_score"],
            reverse=True,
        )
        return results

    def detect_friction_points(
        self,
    ) -> list[dict[str, Any]]:
        """Detect developer friction points."""
        friction_time: dict[str, float] = {}
        friction_counts: dict[str, int] = {}
        for r in self._records:
            if r.satisfaction in (
                SatisfactionLevel.NEUTRAL,
                SatisfactionLevel.FRUSTRATED,
            ):
                ft = r.friction.value
                friction_time[ft] = friction_time.get(ft, 0.0) + r.time_lost_minutes
                friction_counts[ft] = friction_counts.get(ft, 0) + 1
        results: list[dict[str, Any]] = []
        for ft, t_min in friction_time.items():
            results.append(
                {
                    "friction_type": ft,
                    "total_time_lost": round(t_min, 2),
                    "occurrences": (friction_counts.get(ft, 0)),
                }
            )
        results.sort(
            key=lambda x: x["total_time_lost"],
            reverse=True,
        )
        return results

    def rank_tools_by_developer_satisfaction(
        self,
    ) -> list[dict[str, Any]]:
        """Rank tools by developer satisfaction."""
        tool_scores: dict[str, list[float]] = {}
        for r in self._records:
            tool_scores.setdefault(r.tool_id, []).append(r.score)
        results: list[dict[str, Any]] = []
        for tid, scores in tool_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "tool_id": tid,
                    "satisfaction_score": avg,
                    "responses": len(scores),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["satisfaction_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
