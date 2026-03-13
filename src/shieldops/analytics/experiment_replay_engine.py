"""Experiment Replay Engine

Replay past experiments with perturbation support
to validate reproducibility and detect nondeterminism.
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


class ReplayMode(StrEnum):
    EXACT = "exact"
    PERTURBED = "perturbed"
    ACCELERATED = "accelerated"
    SUMMARIZED = "summarized"


class ReplayOutcome(StrEnum):
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


class ComparisonMetric(StrEnum):
    ACCURACY = "accuracy"
    LATENCY = "latency"
    COST = "cost"
    RELIABILITY = "reliability"


# --- Models ---


class ReplayRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    replay_mode: ReplayMode = ReplayMode.EXACT
    outcome: ReplayOutcome = ReplayOutcome.AMBIGUOUS
    comparison_metric: ComparisonMetric = ComparisonMetric.ACCURACY
    original_value: float = 0.0
    replay_value: float = 0.0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class ReplayAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    replay_mode: ReplayMode = ReplayMode.EXACT
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReplayReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    confirmed_count: int = 0
    contradicted_count: int = 0
    by_mode: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ExperimentReplayEngine:
    """Replay past experiments to validate
    reproducibility and detect nondeterminism.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ReplayRecord] = []
        self._analyses: dict[str, ReplayAnalysis] = {}
        logger.info(
            "experiment_replay_engine.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        experiment_id: str = "",
        replay_mode: ReplayMode = ReplayMode.EXACT,
        outcome: ReplayOutcome = ReplayOutcome.AMBIGUOUS,
        comparison_metric: ComparisonMetric = (ComparisonMetric.ACCURACY),
        original_value: float = 0.0,
        replay_value: float = 0.0,
        service: str = "",
    ) -> ReplayRecord:
        record = ReplayRecord(
            experiment_id=experiment_id,
            replay_mode=replay_mode,
            outcome=outcome,
            comparison_metric=comparison_metric,
            original_value=original_value,
            replay_value=replay_value,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "experiment_replay_engine.record_added",
            record_id=record.id,
            experiment_id=experiment_id,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        delta = abs(rec.replay_value - rec.original_value)
        analysis = ReplayAnalysis(
            experiment_id=rec.experiment_id,
            replay_mode=rec.replay_mode,
            analysis_score=round(delta, 4),
            description=(f"Replay {rec.experiment_id} delta={delta:.4f}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "delta": analysis.analysis_score,
        }

    def generate_report(self) -> ReplayReport:
        by_mode: dict[str, int] = {}
        by_out: dict[str, int] = {}
        by_met: dict[str, int] = {}
        confirmed = 0
        contradicted = 0
        for r in self._records:
            m = r.replay_mode.value
            by_mode[m] = by_mode.get(m, 0) + 1
            o = r.outcome.value
            by_out[o] = by_out.get(o, 0) + 1
            c = r.comparison_metric.value
            by_met[c] = by_met.get(c, 0) + 1
            if r.outcome == ReplayOutcome.CONFIRMED:
                confirmed += 1
            elif r.outcome == ReplayOutcome.CONTRADICTED:
                contradicted += 1
        recs: list[str] = []
        total = len(self._records)
        if total > 0 and contradicted / total > 0.3:
            recs.append("High contradiction rate — investigate nondeterminism")
        if not recs:
            recs.append("Replay pipeline is reproducible")
        return ReplayReport(
            total_records=total,
            total_analyses=len(self._analyses),
            confirmed_count=confirmed,
            contradicted_count=contradicted,
            by_mode=by_mode,
            by_outcome=by_out,
            by_metric=by_met,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        mode_dist: dict[str, int] = {}
        for r in self._records:
            k = r.replay_mode.value
            mode_dist[k] = mode_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "mode_distribution": mode_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("experiment_replay_engine.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def replay_experiment(self, experiment_id: str) -> list[dict[str, Any]]:
        """Get all replays for an experiment."""
        matching = [r for r in self._records if r.experiment_id == experiment_id]
        if not matching:
            return []
        return [
            {
                "replay_mode": r.replay_mode.value,
                "outcome": r.outcome.value,
                "original_value": r.original_value,
                "replay_value": r.replay_value,
            }
            for r in matching
        ]

    def compare_outcomes(self, experiment_id: str) -> dict[str, Any]:
        """Compare outcomes across replays."""
        matching = [r for r in self._records if r.experiment_id == experiment_id]
        if not matching:
            return {
                "experiment_id": experiment_id,
                "status": "no_data",
            }
        deltas = [abs(r.replay_value - r.original_value) for r in matching]
        return {
            "experiment_id": experiment_id,
            "avg_delta": round(sum(deltas) / len(deltas), 4),
            "max_delta": round(max(deltas), 4),
            "replay_count": len(matching),
        }

    def detect_nondeterminism(self, experiment_id: str) -> dict[str, Any]:
        """Detect nondeterministic behavior."""
        matching = [r for r in self._records if r.experiment_id == experiment_id]
        if not matching:
            return {
                "experiment_id": experiment_id,
                "status": "no_data",
            }
        contradicted = [r for r in matching if r.outcome == ReplayOutcome.CONTRADICTED]
        rate = len(contradicted) / len(matching)
        return {
            "experiment_id": experiment_id,
            "nondeterminism_rate": round(rate, 4),
            "contradicted_count": len(contradicted),
            "total_replays": len(matching),
        }
