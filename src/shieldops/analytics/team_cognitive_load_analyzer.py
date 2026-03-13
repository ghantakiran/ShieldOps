"""Team Cognitive Load Analyzer —
compute cognitive load index, detect overload patterns,
rank teams by load sustainability."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LoadType(StrEnum):
    INTRINSIC = "intrinsic"
    EXTRANEOUS = "extraneous"
    GERMANE = "germane"
    OPERATIONAL = "operational"


class LoadLevel(StrEnum):
    SUSTAINABLE = "sustainable"
    ELEVATED = "elevated"
    HIGH = "high"
    OVERLOADED = "overloaded"


class LoadSource(StrEnum):
    SYSTEM_COMPLEXITY = "system_complexity"
    PROCESS_OVERHEAD = "process_overhead"
    CONTEXT_SWITCHING = "context_switching"
    INCIDENT_BURDEN = "incident_burden"


# --- Models ---


class CognitiveLoadRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    load_type: LoadType = LoadType.INTRINSIC
    level: LoadLevel = LoadLevel.SUSTAINABLE
    source: LoadSource = LoadSource.SYSTEM_COMPLEXITY
    load_score: float = 0.0
    services_owned: int = 0
    context_switches: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CognitiveLoadAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    avg_load: float = 0.0
    level: LoadLevel = LoadLevel.SUSTAINABLE
    dominant_source: str = ""
    sample_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CognitiveLoadReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_load: float = 0.0
    by_load_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    overloaded_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamCognitiveLoadAnalyzer:
    """Compute cognitive load index, detect overload,
    rank teams by load sustainability."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CognitiveLoadRecord] = []
        self._analyses: dict[str, CognitiveLoadAnalysis] = {}
        logger.info(
            "team_cognitive_load_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        team_id: str = "",
        load_type: LoadType = LoadType.INTRINSIC,
        level: LoadLevel = LoadLevel.SUSTAINABLE,
        source: LoadSource = (LoadSource.SYSTEM_COMPLEXITY),
        load_score: float = 0.0,
        services_owned: int = 0,
        context_switches: int = 0,
        description: str = "",
    ) -> CognitiveLoadRecord:
        record = CognitiveLoadRecord(
            team_id=team_id,
            load_type=load_type,
            level=level,
            source=source,
            load_score=load_score,
            services_owned=services_owned,
            context_switches=context_switches,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cognitive_load.record_added",
            record_id=record.id,
            team_id=team_id,
        )
        return record

    def process(self, key: str) -> CognitiveLoadAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        team_recs = [r for r in self._records if r.team_id == rec.team_id]
        scores = [r.load_score for r in team_recs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        src_counts: dict[str, int] = {}
        for r in team_recs:
            s = r.source.value
            src_counts[s] = src_counts.get(s, 0) + 1
        dominant = (
            max(
                src_counts,
                key=lambda x: src_counts[x],
            )
            if src_counts
            else ""
        )
        analysis = CognitiveLoadAnalysis(
            team_id=rec.team_id,
            avg_load=avg,
            level=rec.level,
            dominant_source=dominant,
            sample_count=len(team_recs),
            description=(f"Team {rec.team_id} load={avg}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CognitiveLoadReport:
        by_lt: dict[str, int] = {}
        by_lv: dict[str, int] = {}
        by_s: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.load_type.value
            by_lt[k] = by_lt.get(k, 0) + 1
            k2 = r.level.value
            by_lv[k2] = by_lv.get(k2, 0) + 1
            k3 = r.source.value
            by_s[k3] = by_s.get(k3, 0) + 1
            scores.append(r.load_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        overloaded = list(
            {r.team_id for r in self._records if r.level in (LoadLevel.HIGH, LoadLevel.OVERLOADED)}
        )[:10]
        recs: list[str] = []
        if overloaded:
            recs.append(f"{len(overloaded)} overloaded teams")
        if not recs:
            recs.append("Cognitive load levels sustainable")
        return CognitiveLoadReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_load=avg,
            by_load_type=by_lt,
            by_level=by_lv,
            by_source=by_s,
            overloaded_teams=overloaded,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        lt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.load_type.value
            lt_dist[k] = lt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "load_type_distribution": lt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("team_cognitive_load_analyzer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_cognitive_load_index(
        self,
    ) -> list[dict[str, Any]]:
        """Compute cognitive load index per team."""
        team_scores: dict[str, list[float]] = {}
        team_svcs: dict[str, int] = {}
        for r in self._records:
            team_scores.setdefault(r.team_id, []).append(r.load_score)
            team_svcs[r.team_id] = max(
                team_svcs.get(r.team_id, 0),
                r.services_owned,
            )
        results: list[dict[str, Any]] = []
        for tid, scores in team_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "team_id": tid,
                    "load_index": avg,
                    "services_owned": (team_svcs.get(tid, 0)),
                    "samples": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["load_index"],
            reverse=True,
        )
        return results

    def detect_overload_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect teams with overload patterns."""
        team_levels: dict[str, list[str]] = {}
        for r in self._records:
            team_levels.setdefault(r.team_id, []).append(r.level.value)
        results: list[dict[str, Any]] = []
        for tid, levels in team_levels.items():
            high_count = sum(1 for lv in levels if lv in ("high", "overloaded"))
            ratio = round(high_count / len(levels), 2)
            if ratio > 0.3:
                results.append(
                    {
                        "team_id": tid,
                        "overload_ratio": ratio,
                        "high_count": high_count,
                        "total": len(levels),
                    }
                )
        results.sort(
            key=lambda x: x["overload_ratio"],
            reverse=True,
        )
        return results

    def rank_teams_by_load_sustainability(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by load sustainability."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team_id, []).append(r.load_score)
        results: list[dict[str, Any]] = []
        for tid, scores in team_scores.items():
            avg = sum(scores) / len(scores)
            sustainability = round(max(0.0, 100.0 - avg), 2)
            results.append(
                {
                    "team_id": tid,
                    "sustainability_score": (sustainability),
                    "avg_load": round(avg, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["sustainability_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
