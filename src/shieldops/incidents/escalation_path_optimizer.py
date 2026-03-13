"""Escalation Path Optimizer
analyze escalation efficiency, detect antipatterns,
recommend path restructuring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationOutcome(StrEnum):
    RESOLVED = "resolved"
    REROUTED = "rerouted"
    TIMED_OUT = "timed_out"
    ABANDONED = "abandoned"


class PathType(StrEnum):
    LINEAR = "linear"
    SKIP_LEVEL = "skip_level"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


class AntipatternType(StrEnum):
    PINGPONG = "pingpong"
    DEAD_END = "dead_end"
    BOTTLENECK = "bottleneck"
    SKIP_ABUSE = "skip_abuse"


# --- Models ---


class EscalationPathRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    escalation_outcome: EscalationOutcome = EscalationOutcome.RESOLVED
    path_type: PathType = PathType.LINEAR
    antipattern_type: AntipatternType = AntipatternType.PINGPONG
    hops: int = 0
    total_time_min: float = 0.0
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationPathAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    path_type: PathType = PathType.LINEAR
    efficiency_score: float = 0.0
    hop_count: int = 0
    antipattern_detected: bool = False
    resolution_time_min: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationPathReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_hops: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_path_type: dict[str, int] = Field(default_factory=dict)
    by_antipattern: dict[str, int] = Field(default_factory=dict)
    problematic_paths: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EscalationPathOptimizer:
    """Analyze escalation efficiency, detect
    antipatterns, recommend path restructuring."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EscalationPathRecord] = []
        self._analyses: dict[str, EscalationPathAnalysis] = {}
        logger.info(
            "escalation_path_optimizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        escalation_outcome: EscalationOutcome = (EscalationOutcome.RESOLVED),
        path_type: PathType = PathType.LINEAR,
        antipattern_type: AntipatternType = (AntipatternType.PINGPONG),
        hops: int = 0,
        total_time_min: float = 0.0,
        team: str = "",
        description: str = "",
    ) -> EscalationPathRecord:
        record = EscalationPathRecord(
            incident_id=incident_id,
            escalation_outcome=escalation_outcome,
            path_type=path_type,
            antipattern_type=antipattern_type,
            hops=hops,
            total_time_min=total_time_min,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "escalation_path.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> EscalationPathAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        efficiency = max(
            0.0,
            100.0 - (rec.hops * 15) - (rec.total_time_min / 10.0),
        )
        has_anti = rec.antipattern_type in (
            AntipatternType.PINGPONG,
            AntipatternType.DEAD_END,
        )
        analysis = EscalationPathAnalysis(
            incident_id=rec.incident_id,
            path_type=rec.path_type,
            efficiency_score=round(efficiency, 2),
            hop_count=rec.hops,
            antipattern_detected=has_anti,
            resolution_time_min=rec.total_time_min,
            description=(f"Incident {rec.incident_id} efficiency {efficiency:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EscalationPathReport:
        by_eo: dict[str, int] = {}
        by_pt: dict[str, int] = {}
        by_ap: dict[str, int] = {}
        hops: list[int] = []
        for r in self._records:
            k = r.escalation_outcome.value
            by_eo[k] = by_eo.get(k, 0) + 1
            k2 = r.path_type.value
            by_pt[k2] = by_pt.get(k2, 0) + 1
            k3 = r.antipattern_type.value
            by_ap[k3] = by_ap.get(k3, 0) + 1
            hops.append(r.hops)
        avg_h = round(sum(hops) / len(hops), 2) if hops else 0.0
        prob = list(
            {
                r.incident_id
                for r in self._records
                if r.escalation_outcome
                in (
                    EscalationOutcome.TIMED_OUT,
                    EscalationOutcome.ABANDONED,
                )
            }
        )[:10]
        recs: list[str] = []
        if prob:
            recs.append(f"{len(prob)} problematic escalations")
        if not recs:
            recs.append("Escalation paths within norms")
        return EscalationPathReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_hops=avg_h,
            by_outcome=by_eo,
            by_path_type=by_pt,
            by_antipattern=by_ap,
            problematic_paths=prob,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        eo_dist: dict[str, int] = {}
        for r in self._records:
            k = r.escalation_outcome.value
            eo_dist[k] = eo_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "outcome_distribution": eo_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("escalation_path_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def analyze_escalation_efficiency(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze escalation efficiency per team."""
        team_data: dict[str, list[float]] = {}
        team_hops: dict[str, list[int]] = {}
        for r in self._records:
            team_data.setdefault(r.team, []).append(r.total_time_min)
            team_hops.setdefault(r.team, []).append(r.hops)
        results: list[dict[str, Any]] = []
        for team, times in team_data.items():
            avg_time = sum(times) / len(times) if times else 0.0
            h = team_hops[team]
            avg_h = sum(h) / len(h) if h else 0.0
            results.append(
                {
                    "team": team,
                    "avg_resolution_min": round(avg_time, 2),
                    "avg_hops": round(avg_h, 2),
                    "escalation_count": len(times),
                    "efficiency": "high" if avg_h <= 2 else "low",
                }
            )
        results.sort(
            key=lambda x: x["avg_hops"],
        )
        return results

    def detect_escalation_antipatterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect antipatterns in escalations."""
        pattern_counts: dict[str, int] = {}
        pattern_incidents: dict[str, list[str]] = {}
        for r in self._records:
            p = r.antipattern_type.value
            pattern_counts[p] = pattern_counts.get(p, 0) + 1
            pattern_incidents.setdefault(p, []).append(r.incident_id)
        results: list[dict[str, Any]] = []
        for pat, count in pattern_counts.items():
            results.append(
                {
                    "antipattern": pat,
                    "occurrence_count": count,
                    "affected_incidents": (pattern_incidents[pat][:10]),
                    "severity": "high" if count > 5 else "low",
                }
            )
        results.sort(
            key=lambda x: x["occurrence_count"],
            reverse=True,
        )
        return results

    def recommend_path_restructuring(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend path restructuring."""
        team_outcomes: dict[str, dict[str, int]] = {}
        for r in self._records:
            if r.team not in team_outcomes:
                team_outcomes[r.team] = {}
            o = r.escalation_outcome.value
            team_outcomes[r.team][o] = team_outcomes[r.team].get(o, 0) + 1
        results: list[dict[str, Any]] = []
        for team, outcomes in team_outcomes.items():
            total = sum(outcomes.values())
            resolved = outcomes.get("resolved", 0)
            rate = resolved / total if total else 0.0
            results.append(
                {
                    "team": team,
                    "total_escalations": total,
                    "resolution_rate": round(rate, 2),
                    "outcomes": outcomes,
                    "recommendation": "restructure" if rate < 0.5 else "maintain",
                }
            )
        results.sort(
            key=lambda x: x["resolution_rate"],
        )
        return results
