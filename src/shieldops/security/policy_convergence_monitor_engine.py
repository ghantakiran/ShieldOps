"""Policy Convergence Monitor Engine —
monitors security agent policy training convergence,
detects instability, estimates convergence ETA."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConvergencePhase(StrEnum):
    EXPLORATION = "exploration"
    LEARNING = "learning"
    STABILIZING = "stabilizing"
    CONVERGED = "converged"


class InstabilityType(StrEnum):
    ENTROPY_COLLAPSE = "entropy_collapse"
    REWARD_OSCILLATION = "reward_oscillation"
    GRADIENT_VANISHING = "gradient_vanishing"
    MODE_COLLAPSE = "mode_collapse"


class MonitoringGranularity(StrEnum):
    PER_STEP = "per_step"
    PER_EPOCH = "per_epoch"
    PER_ITERATION = "per_iteration"
    AGGREGATE = "aggregate"


# --- Models ---


class ConvergenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    convergence_phase: ConvergencePhase = ConvergencePhase.EXPLORATION
    instability_type: InstabilityType = InstabilityType.REWARD_OSCILLATION
    monitoring_granularity: MonitoringGranularity = MonitoringGranularity.PER_EPOCH
    reward: float = 0.0
    entropy: float = 0.0
    gradient_norm: float = 0.0
    step: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConvergenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    convergence_phase: ConvergencePhase = ConvergencePhase.EXPLORATION
    is_stable: bool = True
    instability_type: InstabilityType = InstabilityType.REWARD_OSCILLATION
    reward_trend: str = "flat"
    convergence_eta_steps: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConvergenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_reward: float = 0.0
    avg_entropy: float = 0.0
    by_convergence_phase: dict[str, int] = Field(default_factory=dict)
    by_instability_type: dict[str, int] = Field(default_factory=dict)
    by_monitoring_granularity: dict[str, int] = Field(default_factory=dict)
    unstable_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyConvergenceMonitorEngine:
    """Monitors security agent policy training convergence."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ConvergenceRecord] = []
        self._analyses: dict[str, ConvergenceAnalysis] = {}
        logger.info(
            "policy_convergence_monitor_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        convergence_phase: ConvergencePhase = ConvergencePhase.EXPLORATION,
        instability_type: InstabilityType = InstabilityType.REWARD_OSCILLATION,
        monitoring_granularity: MonitoringGranularity = MonitoringGranularity.PER_EPOCH,
        reward: float = 0.0,
        entropy: float = 0.0,
        gradient_norm: float = 0.0,
        step: int = 0,
        description: str = "",
    ) -> ConvergenceRecord:
        record = ConvergenceRecord(
            agent_id=agent_id,
            convergence_phase=convergence_phase,
            instability_type=instability_type,
            monitoring_granularity=monitoring_granularity,
            reward=reward,
            entropy=entropy,
            gradient_norm=gradient_norm,
            step=step,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_convergence_monitor.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> ConvergenceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        rewards = [r.reward for r in agent_recs]
        if len(rewards) >= 2:
            trend = (
                "improving"
                if rewards[-1] > rewards[0]
                else "declining"
                if rewards[-1] < rewards[0]
                else "flat"
            )
        else:
            trend = "flat"
        is_stable = rec.convergence_phase in (
            ConvergencePhase.STABILIZING,
            ConvergencePhase.CONVERGED,
        )
        eta = 0 if is_stable else max(0, 1000 - rec.step)
        analysis = ConvergenceAnalysis(
            agent_id=rec.agent_id,
            convergence_phase=rec.convergence_phase,
            is_stable=is_stable,
            instability_type=rec.instability_type,
            reward_trend=trend,
            convergence_eta_steps=eta,
            description=(
                f"Agent {rec.agent_id} phase {rec.convergence_phase.value}, ETA {eta} steps"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ConvergenceReport:
        by_cp: dict[str, int] = {}
        by_it: dict[str, int] = {}
        by_mg: dict[str, int] = {}
        rewards: list[float] = []
        entropies: list[float] = []
        for r in self._records:
            k = r.convergence_phase.value
            by_cp[k] = by_cp.get(k, 0) + 1
            k2 = r.instability_type.value
            by_it[k2] = by_it.get(k2, 0) + 1
            k3 = r.monitoring_granularity.value
            by_mg[k3] = by_mg.get(k3, 0) + 1
            rewards.append(r.reward)
            entropies.append(r.entropy)
        avg_reward = round(sum(rewards) / len(rewards), 4) if rewards else 0.0
        avg_entropy = round(sum(entropies) / len(entropies), 4) if entropies else 0.0
        unstable = list(
            {
                r.agent_id
                for r in self._records
                if r.convergence_phase in (ConvergencePhase.EXPLORATION, ConvergencePhase.LEARNING)
            }
        )[:10]
        recs_list: list[str] = []
        if unstable:
            recs_list.append(f"{len(unstable)} agents not yet converged")
        if not recs_list:
            recs_list.append("Policy convergence on track")
        return ConvergenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reward=avg_reward,
            avg_entropy=avg_entropy,
            by_convergence_phase=by_cp,
            by_instability_type=by_it,
            by_monitoring_granularity=by_mg,
            unstable_agents=unstable,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            k = r.convergence_phase.value
            phase_dist[k] = phase_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "phase_distribution": phase_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("policy_convergence_monitor_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_convergence_state(self) -> list[dict[str, Any]]:
        """Detect convergence state per agent."""
        agent_data: dict[str, list[ConvergenceRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for agent_id, recs in agent_data.items():
            latest = max(recs, key=lambda x: x.step)
            results.append(
                {
                    "agent_id": agent_id,
                    "latest_phase": latest.convergence_phase.value,
                    "latest_step": latest.step,
                    "latest_reward": latest.reward,
                    "is_converged": latest.convergence_phase == ConvergencePhase.CONVERGED,
                }
            )
        results.sort(key=lambda x: 0 if x["is_converged"] else 1)
        return results

    def alert_on_instability(self) -> list[dict[str, Any]]:
        """Alert when agents show instability signals."""
        instability_recs = [
            r
            for r in self._records
            if r.instability_type
            in (InstabilityType.ENTROPY_COLLAPSE, InstabilityType.MODE_COLLAPSE)
        ]
        alerts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in instability_recs:
            if r.agent_id not in seen:
                seen.add(r.agent_id)
                alerts.append(
                    {
                        "agent_id": r.agent_id,
                        "instability_type": r.instability_type.value,
                        "step": r.step,
                        "entropy": r.entropy,
                        "gradient_norm": r.gradient_norm,
                    }
                )
        alerts.sort(key=lambda x: x["step"], reverse=True)
        return alerts

    def estimate_convergence_eta(self) -> list[dict[str, Any]]:
        """Estimate steps to convergence per agent."""
        agent_data: dict[str, list[ConvergenceRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for agent_id, recs in agent_data.items():
            latest = max(recs, key=lambda x: x.step)
            if latest.convergence_phase == ConvergencePhase.CONVERGED:
                eta = 0
            else:
                eta = max(0, 1000 - latest.step)
            results.append(
                {
                    "agent_id": agent_id,
                    "current_step": latest.step,
                    "eta_steps": eta,
                    "phase": latest.convergence_phase.value,
                }
            )
        results.sort(key=lambda x: x["eta_steps"])
        return results
