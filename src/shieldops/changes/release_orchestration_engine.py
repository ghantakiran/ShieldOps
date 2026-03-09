"""ReleaseOrchestrationEngine

Multi-environment release coordination, canary analysis,
progressive rollout tracking, feature flag management.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReleaseStage(StrEnum):
    PLANNED = "planned"
    CANARY = "canary"
    PROGRESSIVE = "progressive"
    FULL_ROLLOUT = "full_rollout"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class RolloutStrategy(StrEnum):
    PERCENTAGE_BASED = "percentage_based"
    REGION_BASED = "region_based"
    USER_SEGMENT = "user_segment"
    RING_BASED = "ring_based"
    FEATURE_FLAG = "feature_flag"


class CanaryHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    ABORTED = "aborted"


# --- Models ---


class ReleaseOrchestrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = ""
    stage: ReleaseStage = ReleaseStage.PLANNED
    rollout_strategy: RolloutStrategy = RolloutStrategy.PERCENTAGE_BASED
    canary_health: CanaryHealth = CanaryHealth.UNKNOWN
    rollout_percentage: float = 0.0
    target_environments: int = 0
    completed_environments: int = 0
    error_rate_delta: float = 0.0
    latency_delta_ms: float = 0.0
    feature_flags_active: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReleaseOrchestrationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    stage: ReleaseStage = ReleaseStage.PLANNED
    analysis_score: float = 0.0
    canary_pass_rate: float = 0.0
    rollout_velocity: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReleaseOrchestrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    completed_count: int = 0
    rolled_back_count: int = 0
    avg_rollout_percentage: float = 0.0
    avg_error_rate_delta: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_canary_health: dict[str, int] = Field(default_factory=dict)
    top_slow_releases: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReleaseOrchestrationEngine:
    """Multi-environment release coordination with canary analysis and progressive rollouts."""

    def __init__(
        self,
        max_records: int = 200000,
        error_rate_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._error_rate_threshold = error_rate_threshold
        self._records: list[ReleaseOrchestrationRecord] = []
        self._analyses: list[ReleaseOrchestrationAnalysis] = []
        logger.info(
            "release.orchestration.engine.initialized",
            max_records=max_records,
            error_rate_threshold=error_rate_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        version: str = "",
        stage: ReleaseStage = ReleaseStage.PLANNED,
        rollout_strategy: RolloutStrategy = RolloutStrategy.PERCENTAGE_BASED,
        canary_health: CanaryHealth = CanaryHealth.UNKNOWN,
        rollout_percentage: float = 0.0,
        target_environments: int = 0,
        completed_environments: int = 0,
        error_rate_delta: float = 0.0,
        latency_delta_ms: float = 0.0,
        feature_flags_active: int = 0,
        service: str = "",
        team: str = "",
    ) -> ReleaseOrchestrationRecord:
        record = ReleaseOrchestrationRecord(
            name=name,
            version=version,
            stage=stage,
            rollout_strategy=rollout_strategy,
            canary_health=canary_health,
            rollout_percentage=rollout_percentage,
            target_environments=target_environments,
            completed_environments=completed_environments,
            error_rate_delta=error_rate_delta,
            latency_delta_ms=latency_delta_ms,
            feature_flags_active=feature_flags_active,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "release.orchestration.engine.item_recorded",
            record_id=record.id,
            name=name,
            stage=stage.value,
            rollout_percentage=rollout_percentage,
        )
        return record

    def get_record(self, record_id: str) -> ReleaseOrchestrationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        stage: ReleaseStage | None = None,
        canary_health: CanaryHealth | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReleaseOrchestrationRecord]:
        results = list(self._records)
        if stage is not None:
            results = [r for r in results if r.stage == stage]
        if canary_health is not None:
            results = [r for r in results if r.canary_health == canary_health]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        stage: ReleaseStage = ReleaseStage.PLANNED,
        analysis_score: float = 0.0,
        canary_pass_rate: float = 0.0,
        rollout_velocity: float = 0.0,
        description: str = "",
    ) -> ReleaseOrchestrationAnalysis:
        analysis = ReleaseOrchestrationAnalysis(
            name=name,
            stage=stage,
            analysis_score=analysis_score,
            canary_pass_rate=canary_pass_rate,
            rollout_velocity=rollout_velocity,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "release.orchestration.engine.analysis_added",
            name=name,
            stage=stage.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def evaluate_canary_health(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.stage in (ReleaseStage.CANARY, ReleaseStage.PROGRESSIVE):
                health_score = 100.0
                if r.error_rate_delta > 0:
                    health_score -= min(50.0, r.error_rate_delta * 10)
                if r.latency_delta_ms > 50:
                    health_score -= min(30.0, r.latency_delta_ms / 10)
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "version": r.version,
                        "canary_health": r.canary_health.value,
                        "health_score": round(max(0.0, health_score), 2),
                        "error_rate_delta": r.error_rate_delta,
                        "latency_delta_ms": r.latency_delta_ms,
                    }
                )
        return sorted(results, key=lambda x: x["health_score"])

    def track_rollout_progress(self) -> dict[str, Any]:
        svc_progress: dict[str, list[float]] = {}
        for r in self._records:
            svc_progress.setdefault(r.service, []).append(r.rollout_percentage)
        result: dict[str, Any] = {}
        for svc, percentages in svc_progress.items():
            result[svc] = {
                "latest_percentage": percentages[-1],
                "avg_percentage": round(sum(percentages) / len(percentages), 2),
                "rollout_count": len(percentages),
            }
        return result

    def analyze_feature_flag_usage(self) -> dict[str, Any]:
        team_flags: dict[str, int] = {}
        total_flags = 0
        for r in self._records:
            team_flags.setdefault(r.team, 0)
            team_flags[r.team] += r.feature_flags_active
            total_flags += r.feature_flags_active
        return {
            "total_active_flags": total_flags,
            "by_team": team_flags,
            "avg_flags_per_release": round(total_flags / len(self._records), 2)
            if self._records
            else 0.0,
        }

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ReleaseOrchestrationReport:
        by_stage: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_stage[r.stage.value] = by_stage.get(r.stage.value, 0) + 1
            by_strategy[r.rollout_strategy.value] = by_strategy.get(r.rollout_strategy.value, 0) + 1
            by_health[r.canary_health.value] = by_health.get(r.canary_health.value, 0) + 1
        completed = sum(1 for r in self._records if r.stage == ReleaseStage.COMPLETED)
        rolled_back = sum(1 for r in self._records if r.stage == ReleaseStage.ROLLED_BACK)
        rollout_pcts = [r.rollout_percentage for r in self._records]
        avg_pct = round(sum(rollout_pcts) / len(rollout_pcts), 2) if rollout_pcts else 0.0
        err_deltas = [r.error_rate_delta for r in self._records]
        avg_err = round(sum(err_deltas) / len(err_deltas), 2) if err_deltas else 0.0
        slow = [
            r
            for r in self._records
            if r.rollout_percentage < 50.0
            and r.stage not in (ReleaseStage.COMPLETED, ReleaseStage.ROLLED_BACK)
        ]
        top_slow = [s.name for s in slow[:5]]
        recs: list[str] = []
        if rolled_back > 0:
            recs.append(f"{rolled_back} release(s) rolled back — investigate root causes")
        if avg_err > 1.0:
            recs.append(f"Avg error rate delta {avg_err}% — tighten canary thresholds")
        unhealthy = sum(1 for r in self._records if r.canary_health == CanaryHealth.UNHEALTHY)
        if unhealthy > 0:
            recs.append(f"{unhealthy} unhealthy canary(ies) detected")
        if not recs:
            recs.append("Release orchestration is healthy — all rollouts on track")
        return ReleaseOrchestrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            completed_count=completed,
            rolled_back_count=rolled_back,
            avg_rollout_percentage=avg_pct,
            avg_error_rate_delta=avg_err,
            by_stage=by_stage,
            by_strategy=by_strategy,
            by_canary_health=by_health,
            top_slow_releases=top_slow,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("release.orchestration.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            stage_dist[r.stage.value] = stage_dist.get(r.stage.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "error_rate_threshold": self._error_rate_threshold,
            "stage_distribution": stage_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
