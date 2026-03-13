"""Cross Team Dependency Tracker —
map team dependency graph, detect blocking deps,
rank dependencies by delivery impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyType(StrEnum):
    API = "api"
    DATA = "data"
    DEPLOYMENT = "deployment"
    KNOWLEDGE = "knowledge"


class BlockingStatus(StrEnum):
    BLOCKED = "blocked"
    AT_RISK = "at_risk"
    MANAGED = "managed"
    INDEPENDENT = "independent"


class ImpactScope(StrEnum):
    CRITICAL_PATH = "critical_path"
    PARALLEL = "parallel"
    OPTIONAL = "optional"
    INFORMATIONAL = "informational"


# --- Models ---


class TeamDependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_team: str = ""
    target_team: str = ""
    dep_type: DependencyType = DependencyType.API
    status: BlockingStatus = BlockingStatus.MANAGED
    scope: ImpactScope = ImpactScope.PARALLEL
    impact_score: float = 0.0
    wait_time_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TeamDependencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_team: str = ""
    dependency_count: int = 0
    blocked_count: int = 0
    avg_impact: float = 0.0
    total_wait_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TeamDependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_impact: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    blocked_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossTeamDependencyTracker:
    """Map team dependency graph, detect blocking deps,
    rank dependencies by delivery impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TeamDependencyRecord] = []
        self._analyses: dict[str, TeamDependencyAnalysis] = {}
        logger.info(
            "cross_team_dependency_tracker.init",
            max_records=max_records,
        )

    def record_item(
        self,
        source_team: str = "",
        target_team: str = "",
        dep_type: DependencyType = DependencyType.API,
        status: BlockingStatus = (BlockingStatus.MANAGED),
        scope: ImpactScope = ImpactScope.PARALLEL,
        impact_score: float = 0.0,
        wait_time_hours: float = 0.0,
        description: str = "",
    ) -> TeamDependencyRecord:
        record = TeamDependencyRecord(
            source_team=source_team,
            target_team=target_team,
            dep_type=dep_type,
            status=status,
            scope=scope,
            impact_score=impact_score,
            wait_time_hours=wait_time_hours,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cross_team_dependency.item_recorded",
            record_id=record.id,
            source_team=source_team,
        )
        return record

    def process(self, key: str) -> TeamDependencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        team_recs = [r for r in self._records if r.source_team == rec.source_team]
        blocked = sum(
            1
            for r in team_recs
            if r.status
            in (
                BlockingStatus.BLOCKED,
                BlockingStatus.AT_RISK,
            )
        )
        impacts = [r.impact_score for r in team_recs]
        avg = round(sum(impacts) / len(impacts), 2) if impacts else 0.0
        total_wait = round(
            sum(r.wait_time_hours for r in team_recs),
            2,
        )
        analysis = TeamDependencyAnalysis(
            source_team=rec.source_team,
            dependency_count=len(team_recs),
            blocked_count=blocked,
            avg_impact=avg,
            total_wait_hours=total_wait,
            description=(f"Team {rec.source_team} deps={len(team_recs)}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TeamDependencyReport:
        by_t: dict[str, int] = {}
        by_s: dict[str, int] = {}
        by_sc: dict[str, int] = {}
        impacts: list[float] = []
        for r in self._records:
            k = r.dep_type.value
            by_t[k] = by_t.get(k, 0) + 1
            k2 = r.status.value
            by_s[k2] = by_s.get(k2, 0) + 1
            k3 = r.scope.value
            by_sc[k3] = by_sc.get(k3, 0) + 1
            impacts.append(r.impact_score)
        avg = round(sum(impacts) / len(impacts), 2) if impacts else 0.0
        blocked = list(
            {r.source_team for r in self._records if r.status == BlockingStatus.BLOCKED}
        )[:10]
        recs: list[str] = []
        if blocked:
            recs.append(f"{len(blocked)} blocked teams found")
        if not recs:
            recs.append("No critical blocking dependencies")
        return TeamDependencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_impact=avg,
            by_type=by_t,
            by_status=by_s,
            by_scope=by_sc,
            blocked_teams=blocked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        t_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dep_type.value
            t_dist[k] = t_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "type_distribution": t_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cross_team_dependency_tracker.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def map_team_dependency_graph(
        self,
    ) -> list[dict[str, Any]]:
        """Map dependency graph between teams."""
        edges: dict[str, set[str]] = {}
        for r in self._records:
            edges.setdefault(r.source_team, set()).add(r.target_team)
        results: list[dict[str, Any]] = []
        for src, targets in edges.items():
            results.append(
                {
                    "source_team": src,
                    "target_teams": sorted(targets),
                    "dependency_count": len(targets),
                }
            )
        results.sort(
            key=lambda x: x["dependency_count"],
            reverse=True,
        )
        return results

    def detect_blocking_dependencies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect blocking dependencies."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in (
                BlockingStatus.BLOCKED,
                BlockingStatus.AT_RISK,
            ):
                results.append(
                    {
                        "source_team": r.source_team,
                        "target_team": r.target_team,
                        "status": r.status.value,
                        "impact_score": (r.impact_score),
                        "wait_hours": (r.wait_time_hours),
                    }
                )
        results.sort(
            key=lambda x: x["impact_score"],
            reverse=True,
        )
        return results

    def rank_dependencies_by_delivery_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Rank dependencies by delivery impact."""
        pair_impact: dict[str, float] = {}
        pair_wait: dict[str, float] = {}
        for r in self._records:
            k = f"{r.source_team}->{r.target_team}"
            pair_impact[k] = pair_impact.get(k, 0.0) + r.impact_score
            pair_wait[k] = pair_wait.get(k, 0.0) + r.wait_time_hours
        results: list[dict[str, Any]] = []
        for pair, impact in pair_impact.items():
            results.append(
                {
                    "dependency": pair,
                    "total_impact": round(impact, 2),
                    "total_wait_hours": round(pair_wait.get(pair, 0.0), 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["total_impact"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
