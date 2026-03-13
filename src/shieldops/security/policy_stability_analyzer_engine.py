"""Policy Stability Analyzer Engine —
detects training instability (entropy collapse, mode collapse),
assesses stability, recommends stabilization actions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StabilityStatus(StrEnum):
    STABLE = "stable"
    MARGINALLY_STABLE = "marginally_stable"
    UNSTABLE = "unstable"
    CRITICAL = "critical"


class InstabilityIndicator(StrEnum):
    ENTROPY_COLLAPSE = "entropy_collapse"
    REWARD_OSCILLATION = "reward_oscillation"
    GRADIENT_VANISHING = "gradient_vanishing"
    MODE_COLLAPSE = "mode_collapse"


class RemediationAction(StrEnum):
    INCREASE_KL_PENALTY = "increase_kl_penalty"
    REDUCE_LEARNING_RATE = "reduce_learning_rate"
    RESET_TO_CHECKPOINT = "reset_to_checkpoint"
    ADJUST_GROUPING = "adjust_grouping"


# --- Models ---


class StabilityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    stability_status: StabilityStatus = StabilityStatus.STABLE
    instability_indicator: InstabilityIndicator = InstabilityIndicator.REWARD_OSCILLATION
    remediation_action: RemediationAction = RemediationAction.REDUCE_LEARNING_RATE
    entropy: float = 0.0
    reward_variance: float = 0.0
    gradient_norm: float = 0.0
    training_step: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class StabilityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    stability_status: StabilityStatus = StabilityStatus.STABLE
    instability_indicator: InstabilityIndicator = InstabilityIndicator.REWARD_OSCILLATION
    recommended_action: RemediationAction = RemediationAction.REDUCE_LEARNING_RATE
    entropy_collapsed: bool = False
    stability_score: float = 1.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class StabilityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_entropy: float = 0.0
    avg_reward_variance: float = 0.0
    by_stability_status: dict[str, int] = Field(default_factory=dict)
    by_instability_indicator: dict[str, int] = Field(default_factory=dict)
    by_remediation_action: dict[str, int] = Field(default_factory=dict)
    critical_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyStabilityAnalyzerEngine:
    """Detects training instability (entropy collapse, mode collapse)."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[StabilityRecord] = []
        self._analyses: dict[str, StabilityAnalysis] = {}
        logger.info(
            "policy_stability_analyzer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        stability_status: StabilityStatus = StabilityStatus.STABLE,
        instability_indicator: InstabilityIndicator = (InstabilityIndicator.REWARD_OSCILLATION),
        remediation_action: RemediationAction = RemediationAction.REDUCE_LEARNING_RATE,
        entropy: float = 0.0,
        reward_variance: float = 0.0,
        gradient_norm: float = 0.0,
        training_step: int = 0,
        description: str = "",
    ) -> StabilityRecord:
        record = StabilityRecord(
            agent_id=agent_id,
            stability_status=stability_status,
            instability_indicator=instability_indicator,
            remediation_action=remediation_action,
            entropy=entropy,
            reward_variance=reward_variance,
            gradient_norm=gradient_norm,
            training_step=training_step,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_stability_analyzer.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> StabilityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        entropy_collapsed = rec.entropy < 0.1
        status_scores = {
            StabilityStatus.STABLE: 1.0,
            StabilityStatus.MARGINALLY_STABLE: 0.7,
            StabilityStatus.UNSTABLE: 0.3,
            StabilityStatus.CRITICAL: 0.0,
        }
        stability_score = status_scores.get(rec.stability_status, 0.5)
        if rec.stability_status == StabilityStatus.CRITICAL:
            action = RemediationAction.RESET_TO_CHECKPOINT
        elif entropy_collapsed:
            action = RemediationAction.INCREASE_KL_PENALTY
        elif rec.stability_status == StabilityStatus.UNSTABLE:
            action = RemediationAction.REDUCE_LEARNING_RATE
        else:
            action = rec.remediation_action
        analysis = StabilityAnalysis(
            agent_id=rec.agent_id,
            stability_status=rec.stability_status,
            instability_indicator=rec.instability_indicator,
            recommended_action=action,
            entropy_collapsed=entropy_collapsed,
            stability_score=stability_score,
            description=(
                f"Agent {rec.agent_id} stability {rec.stability_status.value}, "
                f"score {stability_score:.2f}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> StabilityReport:
        by_ss: dict[str, int] = {}
        by_ii: dict[str, int] = {}
        by_ra: dict[str, int] = {}
        entropies: list[float] = []
        variances: list[float] = []
        for r in self._records:
            k = r.stability_status.value
            by_ss[k] = by_ss.get(k, 0) + 1
            k2 = r.instability_indicator.value
            by_ii[k2] = by_ii.get(k2, 0) + 1
            k3 = r.remediation_action.value
            by_ra[k3] = by_ra.get(k3, 0) + 1
            entropies.append(r.entropy)
            variances.append(r.reward_variance)
        avg_entropy = round(sum(entropies) / len(entropies), 4) if entropies else 0.0
        avg_variance = round(sum(variances) / len(variances), 4) if variances else 0.0
        critical_agents = list(
            {r.agent_id for r in self._records if r.stability_status == StabilityStatus.CRITICAL}
        )[:10]
        recs_list: list[str] = []
        if critical_agents:
            recs_list.append(f"{len(critical_agents)} agents in critical stability state")
        if not recs_list:
            recs_list.append("Policy stability within acceptable parameters")
        return StabilityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_entropy=avg_entropy,
            avg_reward_variance=avg_variance,
            by_stability_status=by_ss,
            by_instability_indicator=by_ii,
            by_remediation_action=by_ra,
            critical_agents=critical_agents,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            k = r.stability_status.value
            status_dist[k] = status_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "stability_status_distribution": status_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("policy_stability_analyzer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def assess_policy_stability(self) -> list[dict[str, Any]]:
        """Assess stability score per agent."""
        status_scores = {
            StabilityStatus.STABLE.value: 1.0,
            StabilityStatus.MARGINALLY_STABLE.value: 0.7,
            StabilityStatus.UNSTABLE.value: 0.3,
            StabilityStatus.CRITICAL.value: 0.0,
        }
        agent_data: dict[str, list[StabilityRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for agent_id, recs in agent_data.items():
            scores = [status_scores.get(r.stability_status.value, 0.5) for r in recs]
            mean_score = sum(scores) / len(scores)
            results.append(
                {
                    "agent_id": agent_id,
                    "mean_stability_score": round(mean_score, 4),
                    "sample_count": len(recs),
                    "is_stable": mean_score >= 0.7,
                }
            )
        results.sort(key=lambda x: x["mean_stability_score"])
        return results

    def detect_entropy_collapse(self) -> list[dict[str, Any]]:
        """Detect agents experiencing entropy collapse."""
        collapse_recs = [r for r in self._records if r.entropy < 0.1]
        seen: set[str] = set()
        results: list[dict[str, Any]] = []
        for r in collapse_recs:
            if r.agent_id not in seen:
                seen.add(r.agent_id)
                results.append(
                    {
                        "agent_id": r.agent_id,
                        "entropy": r.entropy,
                        "training_step": r.training_step,
                        "instability_indicator": r.instability_indicator.value,
                    }
                )
        results.sort(key=lambda x: x["entropy"])
        return results

    def recommend_stabilization(self) -> list[dict[str, Any]]:
        """Recommend stabilization actions per agent."""
        agent_data: dict[str, list[StabilityRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for agent_id, recs in agent_data.items():
            latest = max(recs, key=lambda x: x.training_step)
            entropy_collapsed = latest.entropy < 0.1
            if latest.stability_status == StabilityStatus.CRITICAL:
                action = RemediationAction.RESET_TO_CHECKPOINT.value
            elif entropy_collapsed:
                action = RemediationAction.INCREASE_KL_PENALTY.value
            elif latest.stability_status == StabilityStatus.UNSTABLE:
                action = RemediationAction.REDUCE_LEARNING_RATE.value
            else:
                action = RemediationAction.ADJUST_GROUPING.value
            results.append(
                {
                    "agent_id": agent_id,
                    "stability_status": latest.stability_status.value,
                    "recommended_action": action,
                    "entropy": latest.entropy,
                    "training_step": latest.training_step,
                }
            )
        results.sort(
            key=lambda x: (
                0
                if x["stability_status"] == StabilityStatus.CRITICAL.value
                else 1
                if x["stability_status"] == StabilityStatus.UNSTABLE.value
                else 2
            )
        )
        return results
