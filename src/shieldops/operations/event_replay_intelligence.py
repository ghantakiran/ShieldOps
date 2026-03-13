"""Event Replay Intelligence —
compute replay impact, detect idempotency violations,
rank replay candidates by safety."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReplayScope(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    SELECTIVE = "selective"
    POINT_IN_TIME = "point_in_time"


class SafetyLevel(StrEnum):
    SAFE = "safe"
    CAUTION = "caution"
    RISKY = "risky"
    BLOCKED = "blocked"


class IdempotencyStatus(StrEnum):
    GUARANTEED = "guaranteed"
    LIKELY = "likely"
    UNCERTAIN = "uncertain"
    VIOLATED = "violated"


# --- Models ---


class EventReplayRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    replay_id: str = ""
    replay_scope: ReplayScope = ReplayScope.PARTIAL
    safety_level: SafetyLevel = SafetyLevel.SAFE
    idempotency_status: IdempotencyStatus = IdempotencyStatus.GUARANTEED
    event_count: int = 0
    impact_score: float = 0.0
    target_service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EventReplayAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    replay_id: str = ""
    replay_scope: ReplayScope = ReplayScope.PARTIAL
    estimated_impact: float = 0.0
    safety_score: float = 0.0
    idempotency_risk: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EventReplayReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_impact_score: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_safety: dict[str, int] = Field(default_factory=dict)
    by_idempotency: dict[str, int] = Field(default_factory=dict)
    risky_replays: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventReplayIntelligence:
    """Compute replay impact, detect idempotency
    violations, rank replay candidates by safety."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EventReplayRecord] = []
        self._analyses: dict[str, EventReplayAnalysis] = {}
        logger.info(
            "event_replay_intelligence.init",
            max_records=max_records,
        )

    def record_item(
        self,
        replay_id: str = "",
        replay_scope: ReplayScope = ReplayScope.PARTIAL,
        safety_level: SafetyLevel = SafetyLevel.SAFE,
        idempotency_status: IdempotencyStatus = (IdempotencyStatus.GUARANTEED),
        event_count: int = 0,
        impact_score: float = 0.0,
        target_service: str = "",
        description: str = "",
    ) -> EventReplayRecord:
        record = EventReplayRecord(
            replay_id=replay_id,
            replay_scope=replay_scope,
            safety_level=safety_level,
            idempotency_status=idempotency_status,
            event_count=event_count,
            impact_score=impact_score,
            target_service=target_service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "event_replay.item_recorded",
            record_id=record.id,
            replay_id=replay_id,
        )
        return record

    def process(self, key: str) -> EventReplayAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        safety_weights = {
            "safe": 1.0,
            "caution": 0.7,
            "risky": 0.3,
            "blocked": 0.0,
        }
        safety_score = round(
            safety_weights.get(rec.safety_level.value, 0.5) * 100,
            2,
        )
        idemp_risk = round(
            0.0
            if rec.idempotency_status == IdempotencyStatus.GUARANTEED
            else rec.impact_score * 0.5,
            2,
        )
        analysis = EventReplayAnalysis(
            replay_id=rec.replay_id,
            replay_scope=rec.replay_scope,
            estimated_impact=round(rec.impact_score, 2),
            safety_score=safety_score,
            idempotency_risk=idemp_risk,
            description=(f"Replay {rec.replay_id} safety {safety_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EventReplayReport:
        by_sc: dict[str, int] = {}
        by_sf: dict[str, int] = {}
        by_id: dict[str, int] = {}
        impacts: list[float] = []
        for r in self._records:
            k = r.replay_scope.value
            by_sc[k] = by_sc.get(k, 0) + 1
            k2 = r.safety_level.value
            by_sf[k2] = by_sf.get(k2, 0) + 1
            k3 = r.idempotency_status.value
            by_id[k3] = by_id.get(k3, 0) + 1
            impacts.append(r.impact_score)
        avg = round(sum(impacts) / len(impacts), 2) if impacts else 0.0
        risky = list(
            {
                r.replay_id
                for r in self._records
                if r.safety_level in (SafetyLevel.RISKY, SafetyLevel.BLOCKED)
            }
        )[:10]
        recs: list[str] = []
        if risky:
            recs.append(f"{len(risky)} risky replays detected")
        if not recs:
            recs.append("All replays safe")
        return EventReplayReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_impact_score=avg,
            by_scope=by_sc,
            by_safety=by_sf,
            by_idempotency=by_id,
            risky_replays=risky,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sc_dist: dict[str, int] = {}
        for r in self._records:
            k = r.replay_scope.value
            sc_dist[k] = sc_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "scope_distribution": sc_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("event_replay_intelligence.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_replay_impact_estimate(
        self,
    ) -> list[dict[str, Any]]:
        """Compute replay impact estimate per replay."""
        replay_data: dict[str, list[float]] = {}
        replay_svc: dict[str, str] = {}
        for r in self._records:
            replay_data.setdefault(r.replay_id, []).append(r.impact_score)
            replay_svc[r.replay_id] = r.target_service
        results: list[dict[str, Any]] = []
        for rid, impacts in replay_data.items():
            total = round(sum(impacts), 2)
            avg = round(total / len(impacts), 2)
            results.append(
                {
                    "replay_id": rid,
                    "target_service": replay_svc[rid],
                    "total_impact": total,
                    "avg_impact": avg,
                    "event_count": len(impacts),
                }
            )
        results.sort(
            key=lambda x: x["total_impact"],
            reverse=True,
        )
        return results

    def detect_idempotency_violations(
        self,
    ) -> list[dict[str, Any]]:
        """Detect replays with idempotency issues."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.idempotency_status
                in (
                    IdempotencyStatus.UNCERTAIN,
                    IdempotencyStatus.VIOLATED,
                )
                and r.replay_id not in seen
            ):
                seen.add(r.replay_id)
                results.append(
                    {
                        "replay_id": r.replay_id,
                        "status": (r.idempotency_status.value),
                        "impact_score": (r.impact_score),
                        "target_service": (r.target_service),
                    }
                )
        results.sort(
            key=lambda x: x["impact_score"],
            reverse=True,
        )
        return results

    def rank_replay_candidates_by_safety(
        self,
    ) -> list[dict[str, Any]]:
        """Rank replay candidates by safety."""
        safety_weights = {
            "safe": 4,
            "caution": 3,
            "risky": 2,
            "blocked": 1,
        }
        replay_scores: dict[str, float] = {}
        for r in self._records:
            w = safety_weights.get(r.safety_level.value, 1)
            replay_scores[r.replay_id] = replay_scores.get(r.replay_id, 0.0) + w
        results: list[dict[str, Any]] = []
        for rid, score in replay_scores.items():
            results.append(
                {
                    "replay_id": rid,
                    "safety_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["safety_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
