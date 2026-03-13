"""Risk Score Decay Refresh Engine —
manage risk score decay and refresh cycles,
evaluate score freshness, detect stale scores, optimize refresh schedules."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DecayModel(StrEnum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    STEP = "step"
    CUSTOM = "custom"


class RefreshTrigger(StrEnum):
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    THRESHOLD = "threshold"
    MANUAL = "manual"


class ScoreStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    EXPIRED = "expired"
    REFRESHING = "refreshing"


# --- Models ---


class RiskScoreDecayRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    decay_model: DecayModel = DecayModel.EXPONENTIAL
    refresh_trigger: RefreshTrigger = RefreshTrigger.TIME_BASED
    score_status: ScoreStatus = ScoreStatus.CURRENT
    original_score: float = 0.0
    current_score: float = 0.0
    decay_rate: float = 0.0
    age_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskScoreDecayAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    score_status: ScoreStatus = ScoreStatus.CURRENT
    decayed_score: float = 0.0
    needs_refresh: bool = False
    staleness_ratio: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskScoreDecayReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_current_score: float = 0.0
    by_decay_model: dict[str, int] = Field(default_factory=dict)
    by_refresh_trigger: dict[str, int] = Field(default_factory=dict)
    by_score_status: dict[str, int] = Field(default_factory=dict)
    stale_entities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskScoreDecayRefreshEngine:
    """Manage risk score decay and refresh cycles, evaluate score freshness,
    detect stale risk scores, and optimize refresh schedules."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RiskScoreDecayRecord] = []
        self._analyses: dict[str, RiskScoreDecayAnalysis] = {}
        logger.info(
            "risk_score_decay_refresh_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        entity_id: str = "",
        decay_model: DecayModel = DecayModel.EXPONENTIAL,
        refresh_trigger: RefreshTrigger = RefreshTrigger.TIME_BASED,
        score_status: ScoreStatus = ScoreStatus.CURRENT,
        original_score: float = 0.0,
        current_score: float = 0.0,
        decay_rate: float = 0.0,
        age_hours: float = 0.0,
        description: str = "",
    ) -> RiskScoreDecayRecord:
        record = RiskScoreDecayRecord(
            entity_id=entity_id,
            decay_model=decay_model,
            refresh_trigger=refresh_trigger,
            score_status=score_status,
            original_score=original_score,
            current_score=current_score,
            decay_rate=decay_rate,
            age_hours=age_hours,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_score_decay.record_added",
            record_id=record.id,
            entity_id=entity_id,
        )
        return record

    def process(self, key: str) -> RiskScoreDecayAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        # Apply decay based on model
        if rec.decay_model == DecayModel.EXPONENTIAL:
            import math

            decayed = rec.original_score * math.exp(-rec.decay_rate * rec.age_hours)
        elif rec.decay_model == DecayModel.LINEAR:
            decayed = max(0.0, rec.original_score - rec.decay_rate * rec.age_hours)
        else:
            decayed = rec.current_score
        decayed = round(decayed, 4)
        staleness = (
            round((rec.original_score - decayed) / rec.original_score, 4)
            if rec.original_score > 0
            else 0.0
        )
        needs_refresh = rec.score_status in (ScoreStatus.STALE, ScoreStatus.EXPIRED)
        analysis = RiskScoreDecayAnalysis(
            entity_id=rec.entity_id,
            score_status=rec.score_status,
            decayed_score=decayed,
            needs_refresh=needs_refresh,
            staleness_ratio=staleness,
            description=(
                f"Entity {rec.entity_id} score decayed from {rec.original_score} to {decayed}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RiskScoreDecayReport:
        by_dm: dict[str, int] = {}
        by_rt: dict[str, int] = {}
        by_ss: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.decay_model.value
            by_dm[k] = by_dm.get(k, 0) + 1
            k2 = r.refresh_trigger.value
            by_rt[k2] = by_rt.get(k2, 0) + 1
            k3 = r.score_status.value
            by_ss[k3] = by_ss.get(k3, 0) + 1
            scores.append(r.current_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        stale_entities = list(
            {
                r.entity_id
                for r in self._records
                if r.score_status in (ScoreStatus.STALE, ScoreStatus.EXPIRED)
            }
        )[:10]
        recs: list[str] = []
        if stale_entities:
            recs.append(f"{len(stale_entities)} entities with stale/expired risk scores")
        if not recs:
            recs.append("All risk scores are current")
        return RiskScoreDecayReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_current_score=avg,
            by_decay_model=by_dm,
            by_refresh_trigger=by_rt,
            by_score_status=by_ss,
            stale_entities=stale_entities,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ss_dist: dict[str, int] = {}
        for r in self._records:
            k = r.score_status.value
            ss_dist[k] = ss_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "score_status_distribution": ss_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_score_decay_refresh_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def evaluate_score_freshness(self) -> list[dict[str, Any]]:
        """Evaluate freshness of risk scores per entity."""
        entity_data: dict[str, list[RiskScoreDecayRecord]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r)
        results: list[dict[str, Any]] = []
        for eid, recs in entity_data.items():
            latest = max(recs, key=lambda x: x.created_at)
            avg_age = sum(rec.age_hours for rec in recs) / len(recs)
            statuses = list({rec.score_status.value for rec in recs})
            staleness = (
                round(
                    (latest.original_score - latest.current_score) / latest.original_score,
                    4,
                )
                if latest.original_score > 0
                else 0.0
            )
            results.append(
                {
                    "entity_id": eid,
                    "latest_status": latest.score_status.value,
                    "current_score": latest.current_score,
                    "staleness_ratio": staleness,
                    "avg_age_hours": round(avg_age, 2),
                    "statuses_seen": statuses,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["staleness_ratio"], reverse=True)
        return results

    def detect_stale_risk_scores(self) -> list[dict[str, Any]]:
        """Detect entities with stale or expired risk scores."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.score_status in (ScoreStatus.STALE, ScoreStatus.EXPIRED)
                and r.entity_id not in seen
            ):
                seen.add(r.entity_id)
                results.append(
                    {
                        "entity_id": r.entity_id,
                        "score_status": r.score_status.value,
                        "decay_model": r.decay_model.value,
                        "age_hours": r.age_hours,
                        "original_score": r.original_score,
                        "current_score": r.current_score,
                        "refresh_trigger": r.refresh_trigger.value,
                    }
                )
        results.sort(key=lambda x: x["age_hours"], reverse=True)
        return results

    def optimize_refresh_schedules(self) -> list[dict[str, Any]]:
        """Optimize refresh schedules per entity based on decay rates."""
        entity_data: dict[str, list[RiskScoreDecayRecord]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r)
        results: list[dict[str, Any]] = []
        for eid, recs in entity_data.items():
            avg_decay = sum(rec.decay_rate for rec in recs) / len(recs)
            max_score = max(rec.original_score for rec in recs)
            triggers = list({rec.refresh_trigger.value for rec in recs})
            # Higher decay rate -> shorter refresh interval
            if avg_decay > 0.1:
                recommended_interval_h = 1.0
            elif avg_decay > 0.05:
                recommended_interval_h = 6.0
            elif avg_decay > 0.01:
                recommended_interval_h = 24.0
            else:
                recommended_interval_h = 168.0  # weekly
            results.append(
                {
                    "entity_id": eid,
                    "avg_decay_rate": round(avg_decay, 4),
                    "max_original_score": round(max_score, 2),
                    "current_triggers": triggers,
                    "recommended_refresh_interval_h": recommended_interval_h,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["recommended_refresh_interval_h"])
        return results
