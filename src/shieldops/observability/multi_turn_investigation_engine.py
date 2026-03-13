"""Multi-Turn Investigation Engine —
orchestrate multi-turn investigation flows,
determine turn continuation, compute turn information gain."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TurnPhase(StrEnum):
    HYPOTHESIS = "hypothesis"
    DATA_GATHERING = "data_gathering"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"


class InvestigationState(StrEnum):
    OPEN = "open"
    NARROWING = "narrowing"
    VALIDATING = "validating"
    RESOLVED = "resolved"


class TurnOutcome(StrEnum):
    PROGRESS = "progress"
    DEAD_END = "dead_end"
    BREAKTHROUGH = "breakthrough"
    NEEDS_ESCALATION = "needs_escalation"


# --- Models ---


class MultiTurnInvestigationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    turn_phase: TurnPhase = TurnPhase.HYPOTHESIS
    investigation_state: InvestigationState = InvestigationState.OPEN
    turn_outcome: TurnOutcome = TurnOutcome.PROGRESS
    information_gain: float = 0.0
    turn_index: int = 0
    hypothesis: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MultiTurnInvestigationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    turn_phase: TurnPhase = TurnPhase.HYPOTHESIS
    investigation_state: InvestigationState = InvestigationState.OPEN
    turn_outcome: TurnOutcome = TurnOutcome.PROGRESS
    should_continue: bool = True
    information_gain: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MultiTurnInvestigationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_information_gain: float = 0.0
    by_turn_phase: dict[str, int] = Field(default_factory=dict)
    by_investigation_state: dict[str, int] = Field(default_factory=dict)
    by_turn_outcome: dict[str, int] = Field(default_factory=dict)
    resolved_investigations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MultiTurnInvestigationEngine:
    """Orchestrate multi-turn investigation flows,
    determine turn continuation, compute turn information gain."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MultiTurnInvestigationRecord] = []
        self._analyses: dict[str, MultiTurnInvestigationAnalysis] = {}
        logger.info("multi_turn_investigation_engine.init", max_records=max_records)

    def add_record(
        self,
        investigation_id: str = "",
        turn_phase: TurnPhase = TurnPhase.HYPOTHESIS,
        investigation_state: InvestigationState = InvestigationState.OPEN,
        turn_outcome: TurnOutcome = TurnOutcome.PROGRESS,
        information_gain: float = 0.0,
        turn_index: int = 0,
        hypothesis: str = "",
        description: str = "",
    ) -> MultiTurnInvestigationRecord:
        record = MultiTurnInvestigationRecord(
            investigation_id=investigation_id,
            turn_phase=turn_phase,
            investigation_state=investigation_state,
            turn_outcome=turn_outcome,
            information_gain=information_gain,
            turn_index=turn_index,
            hypothesis=hypothesis,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "multi_turn_investigation.record_added",
            record_id=record.id,
            investigation_id=investigation_id,
        )
        return record

    def process(self, key: str) -> MultiTurnInvestigationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        should_cont = (
            rec.investigation_state not in (InvestigationState.RESOLVED,)
            and rec.turn_outcome != TurnOutcome.DEAD_END
        )
        analysis = MultiTurnInvestigationAnalysis(
            investigation_id=rec.investigation_id,
            turn_phase=rec.turn_phase,
            investigation_state=rec.investigation_state,
            turn_outcome=rec.turn_outcome,
            should_continue=should_cont,
            information_gain=round(rec.information_gain, 4),
            description=(
                f"Investigation {rec.investigation_id} turn={rec.turn_index} "
                f"phase={rec.turn_phase.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MultiTurnInvestigationReport:
        by_tp: dict[str, int] = {}
        by_is: dict[str, int] = {}
        by_to: dict[str, int] = {}
        gains: list[float] = []
        for r in self._records:
            k = r.turn_phase.value
            by_tp[k] = by_tp.get(k, 0) + 1
            k2 = r.investigation_state.value
            by_is[k2] = by_is.get(k2, 0) + 1
            k3 = r.turn_outcome.value
            by_to[k3] = by_to.get(k3, 0) + 1
            gains.append(r.information_gain)
        avg_gain = round(sum(gains) / len(gains), 4) if gains else 0.0
        resolved: list[str] = list(
            {
                r.investigation_id
                for r in self._records
                if r.investigation_state == InvestigationState.RESOLVED
            }
        )[:10]
        recs: list[str] = []
        dead_ends = by_to.get("dead_end", 0)
        if dead_ends:
            recs.append(f"{dead_ends} turns hit dead ends — review hypotheses")
        escalations = by_to.get("needs_escalation", 0)
        if escalations:
            recs.append(f"{escalations} turns need escalation")
        if not recs:
            recs.append("Multi-turn investigations are progressing well")
        return MultiTurnInvestigationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_information_gain=avg_gain,
            by_turn_phase=by_tp,
            by_investigation_state=by_is,
            by_turn_outcome=by_to,
            resolved_investigations=resolved,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.turn_phase.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "turn_phase_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("multi_turn_investigation_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def execute_investigation_turn(self) -> list[dict[str, Any]]:
        """Summarize the latest turn per investigation."""
        inv_map: dict[str, list[MultiTurnInvestigationRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            latest = max(inv_recs, key=lambda r: r.turn_index)
            total_gain = sum(r.information_gain for r in inv_recs)
            results.append(
                {
                    "investigation_id": inv_id,
                    "current_turn": latest.turn_index,
                    "current_phase": latest.turn_phase.value,
                    "current_state": latest.investigation_state.value,
                    "latest_outcome": latest.turn_outcome.value,
                    "total_information_gain": round(total_gain, 4),
                }
            )
        results.sort(key=lambda x: x["total_information_gain"], reverse=True)
        return results

    def determine_turn_continuation(self) -> list[dict[str, Any]]:
        """Determine whether each investigation should continue."""
        inv_map: dict[str, list[MultiTurnInvestigationRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            latest = max(inv_recs, key=lambda r: r.turn_index)
            should_cont = (
                latest.investigation_state not in (InvestigationState.RESOLVED,)
                and latest.turn_outcome != TurnOutcome.DEAD_END
            )
            rationale = (
                "Investigation resolved"
                if not should_cont
                else "Active investigation — continue next turn"
            )
            results.append(
                {
                    "investigation_id": inv_id,
                    "should_continue": should_cont,
                    "latest_state": latest.investigation_state.value,
                    "latest_outcome": latest.turn_outcome.value,
                    "rationale": rationale,
                }
            )
        return results

    def compute_turn_information_gain(self) -> list[dict[str, Any]]:
        """Compute cumulative and per-turn information gain per investigation."""
        inv_map: dict[str, list[MultiTurnInvestigationRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            sorted_recs = sorted(inv_recs, key=lambda r: r.turn_index)
            gains = [r.information_gain for r in sorted_recs]
            cumulative = sum(gains)
            avg_gain = cumulative / len(gains)
            breakthrough_turns = [
                r.turn_index for r in sorted_recs if r.turn_outcome == TurnOutcome.BREAKTHROUGH
            ]
            results.append(
                {
                    "investigation_id": inv_id,
                    "cumulative_gain": round(cumulative, 4),
                    "avg_per_turn_gain": round(avg_gain, 4),
                    "turn_count": len(gains),
                    "breakthrough_turns": breakthrough_turns,
                }
            )
        results.sort(key=lambda x: x["cumulative_gain"], reverse=True)
        return results
