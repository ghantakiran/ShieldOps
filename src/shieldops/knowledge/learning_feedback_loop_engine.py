"""Learning Feedback Loop Engine

Process feedback signals through OODA loops with
adaptation rate tracking and staleness detection.
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


class FeedbackSignal(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"


class LoopStage(StrEnum):
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"


class AdaptationSpeed(StrEnum):
    IMMEDIATE = "immediate"
    GRADUAL = "gradual"
    DELAYED = "delayed"
    NONE = "none"


# --- Models ---


class FeedbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    signal: FeedbackSignal = FeedbackSignal.NEUTRAL
    stage: LoopStage = LoopStage.OBSERVE
    speed: AdaptationSpeed = AdaptationSpeed.GRADUAL
    signal_strength: float = 0.0
    loop_iteration: int = 0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class FeedbackAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    signal: FeedbackSignal = FeedbackSignal.NEUTRAL
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FeedbackReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    positive_count: int = 0
    negative_count: int = 0
    by_signal: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LearningFeedbackLoopEngine:
    """Process feedback signals through OODA loops
    with adaptation rate and staleness detection.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[FeedbackRecord] = []
        self._analyses: dict[str, FeedbackAnalysis] = {}
        logger.info(
            "learning_feedback_loop_engine.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        signal: FeedbackSignal = FeedbackSignal.NEUTRAL,
        stage: LoopStage = LoopStage.OBSERVE,
        speed: AdaptationSpeed = (AdaptationSpeed.GRADUAL),
        signal_strength: float = 0.0,
        loop_iteration: int = 0,
        service: str = "",
    ) -> FeedbackRecord:
        record = FeedbackRecord(
            agent_id=agent_id,
            signal=signal,
            stage=stage,
            speed=speed,
            signal_strength=signal_strength,
            loop_iteration=loop_iteration,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "learning_feedback_loop_engine.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = FeedbackAnalysis(
            agent_id=rec.agent_id,
            signal=rec.signal,
            analysis_score=rec.signal_strength,
            description=(f"Feedback {rec.agent_id} signal={rec.signal.value}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "score": analysis.analysis_score,
        }

    def generate_report(self) -> FeedbackReport:
        by_sig: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        positive = 0
        negative = 0
        for r in self._records:
            s = r.signal.value
            by_sig[s] = by_sig.get(s, 0) + 1
            st = r.stage.value
            by_stage[st] = by_stage.get(st, 0) + 1
            sp = r.speed.value
            by_speed[sp] = by_speed.get(sp, 0) + 1
            if r.signal == FeedbackSignal.POSITIVE:
                positive += 1
            elif r.signal == FeedbackSignal.NEGATIVE:
                negative += 1
        recs: list[str] = []
        total = len(self._records)
        if total > 0 and negative / total > 0.5:
            recs.append("High negative feedback — review agent performance")
        if not recs:
            recs.append("Feedback loop is healthy")
        return FeedbackReport(
            total_records=total,
            total_analyses=len(self._analyses),
            positive_count=positive,
            negative_count=negative,
            by_signal=by_sig,
            by_stage=by_stage,
            by_speed=by_speed,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sig_dist: dict[str, int] = {}
        for r in self._records:
            k = r.signal.value
            sig_dist[k] = sig_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "signal_distribution": sig_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("learning_feedback_loop_engine.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def process_feedback_signal(self, agent_id: str) -> list[dict[str, Any]]:
        """Process feedback signals for an agent."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        return [
            {
                "signal": r.signal.value,
                "stage": r.stage.value,
                "strength": r.signal_strength,
                "iteration": r.loop_iteration,
            }
            for r in matching
        ]

    def compute_adaptation_rate(self, agent_id: str) -> dict[str, Any]:
        """Compute adaptation rate for an agent."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        immediate = len([r for r in matching if r.speed == AdaptationSpeed.IMMEDIATE])
        rate = immediate / len(matching)
        return {
            "agent_id": agent_id,
            "adaptation_rate": round(rate, 4),
            "immediate_count": immediate,
            "total_signals": len(matching),
        }

    def detect_feedback_staleness(self, agent_id: str) -> dict[str, Any]:
        """Detect stale feedback signals."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        none_speed = len([r for r in matching if r.speed == AdaptationSpeed.NONE])
        staleness = none_speed / len(matching)
        return {
            "agent_id": agent_id,
            "staleness_rate": round(staleness, 4),
            "stale_count": none_speed,
            "total_signals": len(matching),
        }
