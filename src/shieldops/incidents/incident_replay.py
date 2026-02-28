"""Incident Replay Engine — replay past incidents for training and analysis."""

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
    FULL_REPLAY = "full_replay"
    ACCELERATED = "accelerated"
    STEP_BY_STEP = "step_by_step"
    SUMMARY = "summary"
    RANDOM_ACCESS = "random_access"


class ReplayFidelity(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    APPROXIMATE = "approximate"


class ReplayOutcome(StrEnum):
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


# --- Models ---


class ReplayRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    mode: ReplayMode = ReplayMode.FULL_REPLAY
    fidelity: ReplayFidelity = ReplayFidelity.EXACT
    outcome: ReplayOutcome = ReplayOutcome.COMPLETED
    effectiveness_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReplayScenario(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_name: str = ""
    mode: ReplayMode = ReplayMode.FULL_REPLAY
    fidelity: ReplayFidelity = ReplayFidelity.HIGH
    target_audience: str = ""
    max_participants: int = 10
    created_at: float = Field(default_factory=time.time)


class IncidentReplayReport(BaseModel):
    total_replays: int = 0
    total_scenarios: int = 0
    completion_rate_pct: float = 0.0
    by_mode: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    failed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentReplayEngine:
    """Replay past incidents for training and analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        min_effectiveness_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_effectiveness_pct = min_effectiveness_pct
        self._records: list[ReplayRecord] = []
        self._scenarios: list[ReplayScenario] = []
        logger.info(
            "incident_replay.initialized",
            max_records=max_records,
            min_effectiveness_pct=min_effectiveness_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_replay(
        self,
        incident_id: str,
        mode: ReplayMode = ReplayMode.FULL_REPLAY,
        fidelity: ReplayFidelity = ReplayFidelity.EXACT,
        outcome: ReplayOutcome = ReplayOutcome.COMPLETED,
        effectiveness_score: float = 0.0,
        details: str = "",
    ) -> ReplayRecord:
        record = ReplayRecord(
            incident_id=incident_id,
            mode=mode,
            fidelity=fidelity,
            outcome=outcome,
            effectiveness_score=effectiveness_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_replay.replay_recorded",
            record_id=record.id,
            incident_id=incident_id,
            mode=mode.value,
            outcome=outcome.value,
        )
        return record

    def get_replay(self, record_id: str) -> ReplayRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_replays(
        self,
        incident_id: str | None = None,
        mode: ReplayMode | None = None,
        limit: int = 50,
    ) -> list[ReplayRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if mode is not None:
            results = [r for r in results if r.mode == mode]
        return results[-limit:]

    def add_scenario(
        self,
        scenario_name: str,
        mode: ReplayMode = ReplayMode.FULL_REPLAY,
        fidelity: ReplayFidelity = ReplayFidelity.HIGH,
        target_audience: str = "",
        max_participants: int = 10,
    ) -> ReplayScenario:
        scenario = ReplayScenario(
            scenario_name=scenario_name,
            mode=mode,
            fidelity=fidelity,
            target_audience=target_audience,
            max_participants=max_participants,
        )
        self._scenarios.append(scenario)
        if len(self._scenarios) > self._max_records:
            self._scenarios = self._scenarios[-self._max_records :]
        logger.info(
            "incident_replay.scenario_added",
            scenario_name=scenario_name,
            mode=mode.value,
            fidelity=fidelity.value,
        )
        return scenario

    # -- domain operations -----------------------------------------------

    def analyze_replay_effectiveness(self, incident_id: str) -> dict[str, Any]:
        """Analyze replay effectiveness for a specific incident."""
        records = [r for r in self._records if r.incident_id == incident_id]
        if not records:
            return {"incident_id": incident_id, "status": "no_data"}
        applied = sum(1 for r in records if r.outcome == ReplayOutcome.COMPLETED)
        applied_rate = round(applied / len(records) * 100, 2)
        return {
            "incident_id": incident_id,
            "applied_rate": applied_rate,
            "record_count": len(records),
            "meets_threshold": applied_rate >= self._min_effectiveness_pct,
        }

    def identify_training_gaps(self) -> list[dict[str, Any]]:
        """Find incidents with >1 failed replay."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.outcome in (ReplayOutcome.FAILED, ReplayOutcome.TIMEOUT):
                failure_counts[r.incident_id] = failure_counts.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "incident_id": svc,
                        "failure_count": count,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_learning_value(self) -> list[dict[str, Any]]:
        """Rank incidents by avg effectiveness_score descending."""
        scores: dict[str, list[float]] = {}
        for r in self._records:
            scores.setdefault(r.incident_id, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, vals in scores.items():
            results.append(
                {
                    "incident_id": svc,
                    "avg_effectiveness_score": round(sum(vals) / len(vals), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"], reverse=True)
        return results

    def detect_replay_patterns(self) -> list[dict[str, Any]]:
        """Detect incidents with >3 replays."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.incident_id] = counts.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in counts.items():
            if count > 3:
                results.append(
                    {
                        "incident_id": svc,
                        "replay_count": count,
                        "pattern_detected": True,
                    }
                )
        results.sort(key=lambda x: x["replay_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> IncidentReplayReport:
        by_mode: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_mode[r.mode.value] = by_mode.get(r.mode.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        completed = sum(1 for r in self._records if r.outcome == ReplayOutcome.COMPLETED)
        completion_rate = round(completed / len(self._records) * 100, 2) if self._records else 0.0
        failed_count = sum(1 for d in self.identify_training_gaps())
        recs: list[str] = []
        if self._records and completion_rate < self._min_effectiveness_pct:
            recs.append(
                f"Completion rate {completion_rate}% is below"
                f" {self._min_effectiveness_pct}% threshold"
            )
        if failed_count > 0:
            recs.append(f"{failed_count} incident(s) with training gaps")
        patterns = len(self.detect_replay_patterns())
        if patterns > 0:
            recs.append(f"{patterns} incident(s) with replay patterns detected")
        if not recs:
            recs.append("Incident replay effectiveness meets targets")
        return IncidentReplayReport(
            total_replays=len(self._records),
            total_scenarios=len(self._scenarios),
            completion_rate_pct=completion_rate,
            by_mode=by_mode,
            by_outcome=by_outcome,
            failed_count=failed_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._scenarios.clear()
        logger.info("incident_replay.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        mode_dist: dict[str, int] = {}
        for r in self._records:
            key = r.mode.value
            mode_dist[key] = mode_dist.get(key, 0) + 1
        return {
            "total_replays": len(self._records),
            "total_scenarios": len(self._scenarios),
            "min_effectiveness_pct": self._min_effectiveness_pct,
            "mode_distribution": mode_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
