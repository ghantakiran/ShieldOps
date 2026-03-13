"""Policy Effectiveness Scorer
compute policy effectiveness score, detect ineffective
policies, rank policies by violation trend."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EffectivenessRating(StrEnum):
    HIGHLY_EFFECTIVE = "highly_effective"
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"


class PolicyType(StrEnum):
    ACCESS = "access"
    DATA = "data"
    NETWORK = "network"
    OPERATIONAL = "operational"


class ViolationTrend(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    ZERO = "zero"


# --- Models ---


class PolicyEffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    effectiveness_rating: EffectivenessRating = EffectivenessRating.EFFECTIVE
    policy_type: PolicyType = PolicyType.ACCESS
    violation_trend: ViolationTrend = ViolationTrend.STABLE
    effectiveness_score: float = 0.0
    violation_count: int = 0
    compliance_rate: float = 100.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyEffectivenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    effectiveness_rating: EffectivenessRating = EffectivenessRating.EFFECTIVE
    computed_score: float = 0.0
    is_ineffective: bool = False
    trend_direction: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_effectiveness_score: float = 0.0
    by_effectiveness_rating: dict[str, int] = Field(default_factory=dict)
    by_policy_type: dict[str, int] = Field(default_factory=dict)
    by_violation_trend: dict[str, int] = Field(default_factory=dict)
    ineffective_policies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyEffectivenessScorer:
    """Compute policy effectiveness score, detect
    ineffective policies, rank by violation trend."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PolicyEffectivenessRecord] = []
        self._analyses: dict[str, PolicyEffectivenessAnalysis] = {}
        logger.info(
            "policy_effectiveness_scorer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        policy_id: str = "",
        effectiveness_rating: EffectivenessRating = EffectivenessRating.EFFECTIVE,
        policy_type: PolicyType = PolicyType.ACCESS,
        violation_trend: ViolationTrend = ViolationTrend.STABLE,
        effectiveness_score: float = 0.0,
        violation_count: int = 0,
        compliance_rate: float = 100.0,
        description: str = "",
    ) -> PolicyEffectivenessRecord:
        record = PolicyEffectivenessRecord(
            policy_id=policy_id,
            effectiveness_rating=effectiveness_rating,
            policy_type=policy_type,
            violation_trend=violation_trend,
            effectiveness_score=effectiveness_score,
            violation_count=violation_count,
            compliance_rate=compliance_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_effectiveness.record_added",
            record_id=record.id,
            policy_id=policy_id,
        )
        return record

    def process(self, key: str) -> PolicyEffectivenessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_ineffective = rec.effectiveness_rating in (
            EffectivenessRating.INEFFECTIVE,
            EffectivenessRating.PARTIALLY_EFFECTIVE,
        )
        analysis = PolicyEffectivenessAnalysis(
            policy_id=rec.policy_id,
            effectiveness_rating=rec.effectiveness_rating,
            computed_score=round(rec.effectiveness_score, 2),
            is_ineffective=is_ineffective,
            trend_direction=rec.violation_trend.value,
            description=f"Policy {rec.policy_id} effectiveness {rec.effectiveness_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PolicyEffectivenessReport:
        by_er: dict[str, int] = {}
        by_pt: dict[str, int] = {}
        by_vt: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.effectiveness_rating.value
            by_er[k] = by_er.get(k, 0) + 1
            k2 = r.policy_type.value
            by_pt[k2] = by_pt.get(k2, 0) + 1
            k3 = r.violation_trend.value
            by_vt[k3] = by_vt.get(k3, 0) + 1
            scores.append(r.effectiveness_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        ineffective = list(
            {
                r.policy_id
                for r in self._records
                if r.effectiveness_rating
                in (
                    EffectivenessRating.INEFFECTIVE,
                    EffectivenessRating.PARTIALLY_EFFECTIVE,
                )
            }
        )[:10]
        recs: list[str] = []
        if ineffective:
            recs.append(f"{len(ineffective)} ineffective policies detected")
        if not recs:
            recs.append("All policies are effective")
        return PolicyEffectivenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_effectiveness_score=avg,
            by_effectiveness_rating=by_er,
            by_policy_type=by_pt,
            by_violation_trend=by_vt,
            ineffective_policies=ineffective,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        er_dist: dict[str, int] = {}
        for r in self._records:
            k = r.effectiveness_rating.value
            er_dist[k] = er_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "effectiveness_rating_distribution": er_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("policy_effectiveness_scorer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_policy_effectiveness_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute effectiveness score per policy."""
        policy_scores: dict[str, list[float]] = {}
        policy_types: dict[str, str] = {}
        for r in self._records:
            policy_scores.setdefault(r.policy_id, []).append(r.effectiveness_score)
            policy_types[r.policy_id] = r.policy_type.value
        results: list[dict[str, Any]] = []
        for pid, scores in policy_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "policy_id": pid,
                    "policy_type": policy_types[pid],
                    "avg_effectiveness_score": avg,
                    "measurement_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_ineffective_policies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect policies that are ineffective."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.effectiveness_rating
                in (
                    EffectivenessRating.INEFFECTIVE,
                    EffectivenessRating.PARTIALLY_EFFECTIVE,
                )
                and r.policy_id not in seen
            ):
                seen.add(r.policy_id)
                results.append(
                    {
                        "policy_id": r.policy_id,
                        "effectiveness_rating": r.effectiveness_rating.value,
                        "violation_count": r.violation_count,
                        "compliance_rate": r.compliance_rate,
                    }
                )
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def rank_policies_by_violation_trend(
        self,
    ) -> list[dict[str, Any]]:
        """Rank policies by violation trend severity."""
        policy_violations: dict[str, int] = {}
        policy_trends: dict[str, str] = {}
        for r in self._records:
            policy_violations[r.policy_id] = (
                policy_violations.get(r.policy_id, 0) + r.violation_count
            )
            policy_trends[r.policy_id] = r.violation_trend.value
        results: list[dict[str, Any]] = []
        for pid, total in policy_violations.items():
            results.append(
                {
                    "policy_id": pid,
                    "violation_trend": policy_trends[pid],
                    "total_violations": total,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_violations"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
