"""Sprint Health Intelligence —
compute sprint health score, detect antipatterns,
rank sprints by predictability."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SprintOutcome(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AntipatternType(StrEnum):
    SCOPE_CREEP = "scope_creep"
    CARRYOVER = "carryover"
    FRONT_LOADING = "front_loading"
    BACK_LOADING = "back_loading"


class HealthIndicator(StrEnum):
    VELOCITY = "velocity"
    SCOPE_STABILITY = "scope_stability"
    COMPLETION_RATE = "completion_rate"
    QUALITY = "quality"


# --- Models ---


class SprintHealthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sprint_id: str = ""
    team_id: str = ""
    outcome: SprintOutcome = SprintOutcome.COMPLETED
    antipattern: AntipatternType = AntipatternType.SCOPE_CREEP
    indicator: HealthIndicator = HealthIndicator.VELOCITY
    health_score: float = 0.0
    completion_pct: float = 0.0
    scope_change_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SprintHealthAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sprint_id: str = ""
    avg_health: float = 0.0
    outcome: SprintOutcome = SprintOutcome.COMPLETED
    antipattern_count: int = 0
    predictability: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SprintHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_health: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_antipattern: dict[str, int] = Field(default_factory=dict)
    by_indicator: dict[str, int] = Field(default_factory=dict)
    unhealthy_sprints: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SprintHealthIntelligence:
    """Compute sprint health score, detect antipatterns,
    rank sprints by predictability."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SprintHealthRecord] = []
        self._analyses: dict[str, SprintHealthAnalysis] = {}
        logger.info(
            "sprint_health_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        sprint_id: str = "",
        team_id: str = "",
        outcome: SprintOutcome = (SprintOutcome.COMPLETED),
        antipattern: AntipatternType = (AntipatternType.SCOPE_CREEP),
        indicator: HealthIndicator = (HealthIndicator.VELOCITY),
        health_score: float = 0.0,
        completion_pct: float = 0.0,
        scope_change_pct: float = 0.0,
        description: str = "",
    ) -> SprintHealthRecord:
        record = SprintHealthRecord(
            sprint_id=sprint_id,
            team_id=team_id,
            outcome=outcome,
            antipattern=antipattern,
            indicator=indicator,
            health_score=health_score,
            completion_pct=completion_pct,
            scope_change_pct=scope_change_pct,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sprint_health.record_added",
            record_id=record.id,
            sprint_id=sprint_id,
        )
        return record

    def process(self, key: str) -> SprintHealthAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sprint_recs = [r for r in self._records if r.sprint_id == rec.sprint_id]
        scores = [r.health_score for r in sprint_recs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        aps = sum(1 for r in sprint_recs if r.scope_change_pct > 20.0)
        completions = [r.completion_pct for r in sprint_recs]
        predict = round(sum(completions) / len(completions), 2) if completions else 0.0
        analysis = SprintHealthAnalysis(
            sprint_id=rec.sprint_id,
            avg_health=avg,
            outcome=rec.outcome,
            antipattern_count=aps,
            predictability=predict,
            description=(f"Sprint {rec.sprint_id} h={avg}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SprintHealthReport:
        by_o: dict[str, int] = {}
        by_a: dict[str, int] = {}
        by_i: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.outcome.value
            by_o[k] = by_o.get(k, 0) + 1
            k2 = r.antipattern.value
            by_a[k2] = by_a.get(k2, 0) + 1
            k3 = r.indicator.value
            by_i[k3] = by_i.get(k3, 0) + 1
            scores.append(r.health_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        unhealthy = list(
            {
                r.sprint_id
                for r in self._records
                if r.outcome
                in (
                    SprintOutcome.FAILED,
                    SprintOutcome.CANCELLED,
                )
            }
        )[:10]
        recs: list[str] = []
        if unhealthy:
            recs.append(f"{len(unhealthy)} unhealthy sprints")
        if not recs:
            recs.append("Sprint health is good")
        return SprintHealthReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_health=avg,
            by_outcome=by_o,
            by_antipattern=by_a,
            by_indicator=by_i,
            unhealthy_sprints=unhealthy,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        o_dist: dict[str, int] = {}
        for r in self._records:
            k = r.outcome.value
            o_dist[k] = o_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "outcome_distribution": o_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("sprint_health_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_sprint_health_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute health score per sprint."""
        sprint_scores: dict[str, list[float]] = {}
        sprint_comp: dict[str, list[float]] = {}
        for r in self._records:
            sprint_scores.setdefault(r.sprint_id, []).append(r.health_score)
            sprint_comp.setdefault(r.sprint_id, []).append(r.completion_pct)
        results: list[dict[str, Any]] = []
        for sid, scores in sprint_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            comps = sprint_comp.get(sid, [])
            avg_comp = round(sum(comps) / len(comps), 2) if comps else 0.0
            results.append(
                {
                    "sprint_id": sid,
                    "health_score": avg,
                    "completion_pct": avg_comp,
                    "indicators": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["health_score"],
            reverse=True,
        )
        return results

    def detect_sprint_antipatterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect sprint antipatterns."""
        ap_counts: dict[str, int] = {}
        ap_sprints: dict[str, set[str]] = {}
        for r in self._records:
            if r.scope_change_pct > 20.0:
                ap = r.antipattern.value
                ap_counts[ap] = ap_counts.get(ap, 0) + 1
                ap_sprints.setdefault(ap, set()).add(r.sprint_id)
        results: list[dict[str, Any]] = []
        for ap, count in ap_counts.items():
            results.append(
                {
                    "antipattern": ap,
                    "occurrences": count,
                    "affected_sprints": len(ap_sprints.get(ap, set())),
                }
            )
        results.sort(
            key=lambda x: x["occurrences"],
            reverse=True,
        )
        return results

    def rank_sprints_by_predictability(
        self,
    ) -> list[dict[str, Any]]:
        """Rank sprints by predictability."""
        sprint_comp: dict[str, list[float]] = {}
        for r in self._records:
            sprint_comp.setdefault(r.sprint_id, []).append(r.completion_pct)
        results: list[dict[str, Any]] = []
        for sid, comps in sprint_comp.items():
            avg = sum(comps) / len(comps)
            var = sum((c - avg) ** 2 for c in comps) / len(comps)
            predict = round(max(0.0, 100.0 - var**0.5), 2)
            results.append(
                {
                    "sprint_id": sid,
                    "predictability": predict,
                    "avg_completion": round(avg, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["predictability"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
