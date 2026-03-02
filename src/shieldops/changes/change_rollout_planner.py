"""Change Rollout Planner — plan change rollouts, assess risk tolerance across strategies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RolloutStrategy(StrEnum):
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    FEATURE_FLAG = "feature_flag"
    BIG_BANG = "big_bang"


class RolloutStage(StrEnum):
    PLANNING = "planning"
    STAGED = "staged"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"


class RolloutRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class RolloutRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    rollout_strategy: RolloutStrategy = RolloutStrategy.CANARY
    rollout_stage: RolloutStage = RolloutStage.PLANNING
    rollout_risk: RolloutRisk = RolloutRisk.CRITICAL
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RolloutAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    rollout_strategy: RolloutStrategy = RolloutStrategy.CANARY
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeRolloutReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_risk_count: int = 0
    avg_risk_score: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_high_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeRolloutPlanner:
    """Plan change rollouts, assess risk tolerance across strategies."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_tolerance_threshold: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._risk_tolerance_threshold = risk_tolerance_threshold
        self._records: list[RolloutRecord] = []
        self._assessments: list[RolloutAssessment] = []
        logger.info(
            "change_rollout_planner.initialized",
            max_records=max_records,
            risk_tolerance_threshold=risk_tolerance_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_rollout(
        self,
        change_id: str,
        rollout_strategy: RolloutStrategy = RolloutStrategy.CANARY,
        rollout_stage: RolloutStage = RolloutStage.PLANNING,
        rollout_risk: RolloutRisk = RolloutRisk.CRITICAL,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RolloutRecord:
        record = RolloutRecord(
            change_id=change_id,
            rollout_strategy=rollout_strategy,
            rollout_stage=rollout_stage,
            rollout_risk=rollout_risk,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_rollout_planner.rollout_recorded",
            record_id=record.id,
            change_id=change_id,
            rollout_strategy=rollout_strategy.value,
            rollout_stage=rollout_stage.value,
        )
        return record

    def get_rollout(self, record_id: str) -> RolloutRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rollouts(
        self,
        rollout_strategy: RolloutStrategy | None = None,
        rollout_stage: RolloutStage | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RolloutRecord]:
        results = list(self._records)
        if rollout_strategy is not None:
            results = [r for r in results if r.rollout_strategy == rollout_strategy]
        if rollout_stage is not None:
            results = [r for r in results if r.rollout_stage == rollout_stage]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        change_id: str,
        rollout_strategy: RolloutStrategy = RolloutStrategy.CANARY,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RolloutAssessment:
        assessment = RolloutAssessment(
            change_id=change_id,
            rollout_strategy=rollout_strategy,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "change_rollout_planner.assessment_added",
            change_id=change_id,
            rollout_strategy=rollout_strategy.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_rollout_distribution(self) -> dict[str, Any]:
        """Group by rollout_strategy; return count and avg risk_score."""
        strat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.rollout_strategy.value
            strat_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for strat, scores in strat_data.items():
            result[strat] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risk_rollouts(self) -> list[dict[str, Any]]:
        """Return records where risk_score > risk_tolerance_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score > self._risk_tolerance_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "change_id": r.change_id,
                        "rollout_strategy": r.rollout_strategy.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort descending (highest risk first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_rollout_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ChangeRolloutReport:
        by_strategy: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.rollout_strategy.value] = by_strategy.get(r.rollout_strategy.value, 0) + 1
            by_stage[r.rollout_stage.value] = by_stage.get(r.rollout_stage.value, 0) + 1
            by_risk[r.rollout_risk.value] = by_risk.get(r.rollout_risk.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk_score > self._risk_tolerance_threshold
        )
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_risk_rollouts()
        top_high_risk = [o["change_id"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_risk_count > 0:
            recs.append(
                f"{high_risk_count} rollout(s) exceed risk tolerance "
                f"({self._risk_tolerance_threshold})"
            )
        if self._records and avg_risk_score > self._risk_tolerance_threshold:
            recs.append(
                f"Avg risk score {avg_risk_score} above threshold "
                f"({self._risk_tolerance_threshold})"
            )
        if not recs:
            recs.append("Change rollout risk levels are healthy")
        return ChangeRolloutReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_risk_count=high_risk_count,
            avg_risk_score=avg_risk_score,
            by_strategy=by_strategy,
            by_stage=by_stage,
            by_risk=by_risk,
            top_high_risk=top_high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("change_rollout_planner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.rollout_strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "risk_tolerance_threshold": self._risk_tolerance_threshold,
            "strategy_distribution": strategy_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
