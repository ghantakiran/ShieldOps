"""Smart Alert Routing Planner
plan skill based routing, optimize timezone coverage,
simulate routing scenario."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RoutingStrategy(StrEnum):
    SKILL_BASED = "skill_based"
    ROUND_ROBIN = "round_robin"
    LOAD_BALANCED = "load_balanced"
    ESCALATION = "escalation"


class CoverageGap(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class SimulationResult(StrEnum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    SUBOPTIMAL = "suboptimal"
    FAILED = "failed"


# --- Models ---


class SmartAlertRoutingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    route_id: str = ""
    routing_strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    coverage_gap: CoverageGap = CoverageGap.FULL
    simulation_result: SimulationResult = SimulationResult.OPTIMAL
    responder_id: str = ""
    skill_match_score: float = 0.0
    timezone: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SmartAlertRoutingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    route_id: str = ""
    routing_strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    routing_score: float = 0.0
    coverage_level: float = 0.0
    avg_skill_match: float = 0.0
    responder_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SmartAlertRoutingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_routing_score: float = 0.0
    by_routing_strategy: dict[str, int] = Field(default_factory=dict)
    by_coverage_gap: dict[str, int] = Field(default_factory=dict)
    by_simulation_result: dict[str, int] = Field(default_factory=dict)
    coverage_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SmartAlertRoutingPlanner:
    """Plan skill based routing, optimize timezone
    coverage, simulate routing scenario."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SmartAlertRoutingRecord] = []
        self._analyses: dict[str, SmartAlertRoutingAnalysis] = {}
        logger.info(
            "smart_alert_routing_planner.init",
            max_records=max_records,
        )

    def record_item(
        self,
        route_id: str = "",
        routing_strategy: RoutingStrategy = (RoutingStrategy.SKILL_BASED),
        coverage_gap: CoverageGap = CoverageGap.FULL,
        simulation_result: SimulationResult = (SimulationResult.OPTIMAL),
        responder_id: str = "",
        skill_match_score: float = 0.0,
        timezone: str = "",
        description: str = "",
    ) -> SmartAlertRoutingRecord:
        record = SmartAlertRoutingRecord(
            route_id=route_id,
            routing_strategy=routing_strategy,
            coverage_gap=coverage_gap,
            simulation_result=simulation_result,
            responder_id=responder_id,
            skill_match_score=skill_match_score,
            timezone=timezone,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "smart_alert_routing.record_added",
            record_id=record.id,
            route_id=route_id,
        )
        return record

    def process(self, key: str) -> SmartAlertRoutingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.route_id == rec.route_id]
        count = len(related)
        avg_skill = sum(r.skill_match_score for r in related) / count if count else 0.0
        coverage = (
            sum(1 for r in related if r.coverage_gap == CoverageGap.FULL) / count if count else 0.0
        )
        score = avg_skill * 0.6 + coverage * 40.0
        analysis = SmartAlertRoutingAnalysis(
            route_id=rec.route_id,
            routing_strategy=rec.routing_strategy,
            routing_score=round(score, 2),
            coverage_level=round(coverage, 2),
            avg_skill_match=round(avg_skill, 2),
            responder_count=count,
            description=(f"Route {rec.route_id} score {score:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> SmartAlertRoutingReport:
        by_rs: dict[str, int] = {}
        by_cg: dict[str, int] = {}
        by_sr: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.routing_strategy.value
            by_rs[k] = by_rs.get(k, 0) + 1
            k2 = r.coverage_gap.value
            by_cg[k2] = by_cg.get(k2, 0) + 1
            k3 = r.simulation_result.value
            by_sr[k3] = by_sr.get(k3, 0) + 1
            scores.append(r.skill_match_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = list(
            {
                r.timezone
                for r in self._records
                if r.coverage_gap
                in (
                    CoverageGap.MINIMAL,
                    CoverageGap.NONE,
                )
            }
        )[:10]
        recs: list[str] = []
        if gaps:
            recs.append(f"{len(gaps)} coverage gaps found")
        if not recs:
            recs.append("Routing coverage adequate")
        return SmartAlertRoutingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_routing_score=avg,
            by_routing_strategy=by_rs,
            by_coverage_gap=by_cg,
            by_simulation_result=by_sr,
            coverage_gaps=gaps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rs_dist: dict[str, int] = {}
        for r in self._records:
            k = r.routing_strategy.value
            rs_dist[k] = rs_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "strategy_distribution": rs_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("smart_alert_routing_planner.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def plan_skill_based_routing(
        self,
    ) -> list[dict[str, Any]]:
        """Plan skill based routing."""
        resp_skills: dict[str, list[float]] = {}
        resp_routes: dict[str, set[str]] = {}
        for r in self._records:
            resp_skills.setdefault(r.responder_id, []).append(r.skill_match_score)
            resp_routes.setdefault(r.responder_id, set()).add(r.route_id)
        results: list[dict[str, Any]] = []
        for rid, skills in resp_skills.items():
            avg = sum(skills) / len(skills) if skills else 0.0
            results.append(
                {
                    "responder_id": rid,
                    "avg_skill_match": round(avg, 2),
                    "route_count": len(resp_routes[rid]),
                    "assignment_count": len(skills),
                    "recommended": avg > 0.7,
                }
            )
        results.sort(
            key=lambda x: x["avg_skill_match"],
            reverse=True,
        )
        return results

    def optimize_timezone_coverage(
        self,
    ) -> list[dict[str, Any]]:
        """Optimize timezone coverage."""
        tz_data: dict[str, list[str]] = {}
        tz_gaps: dict[str, int] = {}
        for r in self._records:
            tz_data.setdefault(r.timezone, []).append(r.responder_id)
            if r.coverage_gap != CoverageGap.FULL:
                tz_gaps[r.timezone] = tz_gaps.get(r.timezone, 0) + 1
        results: list[dict[str, Any]] = []
        for tz, responders in tz_data.items():
            unique = len(set(responders))
            gap_count = tz_gaps.get(tz, 0)
            results.append(
                {
                    "timezone": tz,
                    "responder_count": unique,
                    "total_assignments": len(responders),
                    "gap_count": gap_count,
                    "coverage": "adequate" if unique >= 2 else "insufficient",
                }
            )
        results.sort(
            key=lambda x: x["responder_count"],
        )
        return results

    def simulate_routing_scenario(
        self,
    ) -> list[dict[str, Any]]:
        """Simulate routing scenario."""
        strat_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            s = r.routing_strategy.value
            if s not in strat_data:
                strat_data[s] = {}
            res = r.simulation_result.value
            strat_data[s][res] = strat_data[s].get(res, 0) + 1
        results: list[dict[str, Any]] = []
        for strat, outcomes in strat_data.items():
            total = sum(outcomes.values())
            optimal = outcomes.get("optimal", 0)
            success_rate = optimal / total if total else 0.0
            results.append(
                {
                    "strategy": strat,
                    "total_simulations": total,
                    "optimal_count": optimal,
                    "success_rate": round(success_rate, 2),
                    "outcomes": outcomes,
                }
            )
        results.sort(
            key=lambda x: x["success_rate"],
            reverse=True,
        )
        return results
