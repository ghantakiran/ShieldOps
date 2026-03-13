"""Capability Frontier Mapper Engine —
maps expanding capability boundary of SRE agents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FrontierZone(StrEnum):
    MASTERED = "mastered"
    REACHABLE = "reachable"
    FRONTIER = "frontier"
    BEYOND = "beyond"


class ExpansionDirection(StrEnum):
    COMPLEXITY = "complexity"
    BREADTH = "breadth"
    DEPTH = "depth"
    SPECIALIZATION = "specialization"


class FrontierStability(StrEnum):
    STABLE = "stable"
    EXPANDING = "expanding"
    CONTRACTING = "contracting"
    VOLATILE = "volatile"


# --- Models ---


class FrontierRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    capability_name: str = ""
    zone: FrontierZone = FrontierZone.FRONTIER
    direction: ExpansionDirection = ExpansionDirection.COMPLEXITY
    stability: FrontierStability = FrontierStability.STABLE
    frontier_score: float = 0.0
    expansion_rate: float = 0.0
    iteration: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FrontierAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    frontier_boundary: float = 0.0
    dominant_zone: FrontierZone = FrontierZone.FRONTIER
    stability: FrontierStability = FrontierStability.STABLE
    capability_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FrontierReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_frontier_score: float = 0.0
    by_zone: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_stability: dict[str, int] = Field(default_factory=dict)
    leading_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapabilityFrontierMapperEngine:
    """Maps expanding capability boundary of SRE agents."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[FrontierRecord] = []
        self._analyses: dict[str, FrontierAnalysis] = {}
        logger.info(
            "capability_frontier_mapper_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        capability_name: str = "",
        zone: FrontierZone = FrontierZone.FRONTIER,
        direction: ExpansionDirection = ExpansionDirection.COMPLEXITY,
        stability: FrontierStability = FrontierStability.STABLE,
        frontier_score: float = 0.0,
        expansion_rate: float = 0.0,
        iteration: int = 0,
        description: str = "",
    ) -> FrontierRecord:
        record = FrontierRecord(
            agent_id=agent_id,
            capability_name=capability_name,
            zone=zone,
            direction=direction,
            stability=stability,
            frontier_score=frontier_score,
            expansion_rate=expansion_rate,
            iteration=iteration,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capability_frontier_mapper.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> FrontierAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        scores = [r.frontier_score for r in agent_recs]
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        zone_counts: dict[str, int] = {}
        for ar in agent_recs:
            zk = ar.zone.value
            zone_counts[zk] = zone_counts.get(zk, 0) + 1
        dom_zone_str = max(zone_counts, key=lambda x: zone_counts[x]) if zone_counts else ""
        dom_zone = FrontierZone(dom_zone_str) if dom_zone_str else rec.zone
        capability_set: set[str] = {r.capability_name for r in agent_recs}
        analysis = FrontierAnalysis(
            agent_id=rec.agent_id,
            frontier_boundary=avg_score,
            dominant_zone=dom_zone,
            stability=rec.stability,
            capability_count=len(capability_set),
            description=f"Agent {rec.agent_id} frontier boundary {avg_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> FrontierReport:
        by_z: dict[str, int] = {}
        by_dir: dict[str, int] = {}
        by_st: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k1 = r.zone.value
            by_z[k1] = by_z.get(k1, 0) + 1
            k2 = r.direction.value
            by_dir[k2] = by_dir.get(k2, 0) + 1
            k3 = r.stability.value
            by_st[k3] = by_st.get(k3, 0) + 1
            scores.append(r.frontier_score)
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        agent_scores: dict[str, float] = {}
        for r in self._records:
            if r.frontier_score > agent_scores.get(r.agent_id, -1.0):
                agent_scores[r.agent_id] = r.frontier_score
        leading_agents = sorted(
            agent_scores,
            key=lambda x: agent_scores[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        contracting = by_st.get("contracting", 0)
        beyond = by_z.get("beyond", 0)
        if contracting > 0:
            recs_list.append(f"{contracting} contracting frontiers — investigate regressions")
        if beyond > 0:
            recs_list.append(f"{beyond} beyond-frontier capabilities — expand training data")
        if not recs_list:
            recs_list.append("Capability frontier is expanding normally")
        return FrontierReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_frontier_score=avg_score,
            by_zone=by_z,
            by_direction=by_dir,
            by_stability=by_st,
            leading_agents=leading_agents,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        zone_dist: dict[str, int] = {}
        for r in self._records:
            k = r.zone.value
            zone_dist[k] = zone_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "zone_distribution": zone_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("capability_frontier_mapper_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_frontier_boundary(self, agent_id: str) -> dict[str, Any]:
        """Compute the current capability frontier boundary for an agent."""
        agent_recs = [r for r in self._records if r.agent_id == agent_id]
        if not agent_recs:
            return {"agent_id": agent_id, "frontier_boundary": 0.0, "zones": {}}
        zone_scores: dict[str, list[float]] = {}
        for r in agent_recs:
            zk = r.zone.value
            zone_scores.setdefault(zk, []).append(r.frontier_score)
        zone_avgs: dict[str, float] = {}
        for zone, sc in zone_scores.items():
            zone_avgs[zone] = round(sum(sc) / len(sc), 4)
        frontier_scores = zone_scores.get("frontier", [])
        frontier_boundary = round(max(frontier_scores), 4) if frontier_scores else 0.0
        return {
            "agent_id": agent_id,
            "frontier_boundary": frontier_boundary,
            "zone_avg_scores": zone_avgs,
            "capability_count": len({r.capability_name for r in agent_recs}),
        }

    def measure_frontier_expansion_rate(self) -> list[dict[str, Any]]:
        """Measure the rate at which each agent expands its capability frontier."""
        agent_iters: dict[str, list[FrontierRecord]] = {}
        for r in self._records:
            agent_iters.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_iters.items():
            if len(recs) < 2:
                continue
            recs_sorted = sorted(recs, key=lambda x: x.iteration)
            rates = [r.expansion_rate for r in recs_sorted]
            avg_rate = round(sum(rates) / len(rates), 4) if rates else 0.0
            first_score = recs_sorted[0].frontier_score
            last_score = recs_sorted[-1].frontier_score
            iter_span = recs_sorted[-1].iteration - recs_sorted[0].iteration
            computed_rate = (
                round((last_score - first_score) / iter_span, 6) if iter_span > 0 else 0.0
            )
            results.append(
                {
                    "agent_id": aid,
                    "avg_expansion_rate": avg_rate,
                    "computed_rate": computed_rate,
                    "frontier_gain": round(last_score - first_score, 4),
                    "iterations": len(recs_sorted),
                }
            )
        results.sort(key=lambda x: x["avg_expansion_rate"], reverse=True)
        return results

    def identify_frontier_bottlenecks(self) -> list[dict[str, Any]]:
        """Identify capabilities stuck at the frontier zone for many iterations."""
        cap_iters: dict[str, list[FrontierRecord]] = {}
        for r in self._records:
            key = f"{r.agent_id}::{r.capability_name}"
            cap_iters.setdefault(key, []).append(r)
        bottlenecks: list[dict[str, Any]] = []
        for cap_key, recs in cap_iters.items():
            if len(recs) < 3:
                continue
            recs_sorted = sorted(recs, key=lambda x: x.iteration)
            frontier_count = sum(1 for r in recs_sorted if r.zone == FrontierZone.FRONTIER)
            if frontier_count >= 3:
                agent_id, cap_name = cap_key.split("::", 1)
                bottlenecks.append(
                    {
                        "agent_id": agent_id,
                        "capability_name": cap_name,
                        "frontier_iteration_count": frontier_count,
                        "total_iterations": len(recs_sorted),
                        "latest_score": recs_sorted[-1].frontier_score,
                        "is_bottleneck": True,
                    }
                )
        bottlenecks.sort(key=lambda x: x["frontier_iteration_count"], reverse=True)
        return bottlenecks
