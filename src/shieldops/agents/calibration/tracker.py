"""Accuracy tracker — records predictions vs outcomes per agent."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class PredictionRecord(BaseModel):
    """A record of an agent prediction and its outcome."""

    id: str = Field(default_factory=lambda: f"prec-{uuid4().hex[:12]}")
    agent_id: str
    agent_type: str = ""
    predicted_confidence: float = 0.0
    predicted_outcome: str = ""
    actual_outcome: str | None = None
    was_correct: bool | None = None
    feedback_source: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class AccuracyMetrics(BaseModel):
    """Aggregated accuracy metrics for an agent."""

    agent_id: str
    total_predictions: int = 0
    resolved_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    avg_confidence: float = 0.0
    overconfidence_rate: float = 0.0  # % of times confidence > accuracy
    underconfidence_rate: float = 0.0  # % of times confidence < accuracy


class AccuracyTracker:
    """Tracks agent prediction accuracy over time.

    Records predictions and their outcomes, enabling accuracy analysis
    and confidence calibration.
    """

    def __init__(self) -> None:
        self._records: dict[str, list[PredictionRecord]] = {}  # agent_id -> records

    def record_prediction(
        self,
        agent_id: str,
        confidence: float,
        predicted_outcome: str,
        agent_type: str = "",
    ) -> PredictionRecord:
        """Record a new prediction from an agent."""
        record = PredictionRecord(
            agent_id=agent_id,
            agent_type=agent_type,
            predicted_confidence=confidence,
            predicted_outcome=predicted_outcome,
        )

        if agent_id not in self._records:
            self._records[agent_id] = []
        self._records[agent_id].append(record)

        logger.info(
            "prediction_recorded",
            agent_id=agent_id,
            record_id=record.id,
            confidence=confidence,
        )
        return record

    def record_outcome(
        self,
        record_id: str,
        actual_outcome: str,
        feedback_source: str = "human",
    ) -> PredictionRecord | None:
        """Record the actual outcome for a prediction."""
        for records in self._records.values():
            for record in records:
                if record.id == record_id:
                    record.actual_outcome = actual_outcome
                    record.was_correct = record.predicted_outcome == actual_outcome
                    record.feedback_source = feedback_source
                    record.resolved_at = datetime.now(UTC)

                    logger.info(
                        "outcome_recorded",
                        record_id=record_id,
                        was_correct=record.was_correct,
                    )
                    return record
        return None

    def record_feedback(
        self,
        agent_id: str,
        prediction_id: str,
        was_correct: bool,
        feedback_source: str = "human",
    ) -> PredictionRecord | None:
        """Record direct feedback on whether a prediction was correct."""
        records = self._records.get(agent_id, [])
        for record in records:
            if record.id == prediction_id:
                record.was_correct = was_correct
                record.feedback_source = feedback_source
                record.resolved_at = datetime.now(UTC)
                return record
        return None

    def get_accuracy(self, agent_id: str) -> AccuracyMetrics:
        """Get accuracy metrics for an agent."""
        records = self._records.get(agent_id, [])

        total = len(records)
        resolved = [r for r in records if r.was_correct is not None]
        correct = [r for r in resolved if r.was_correct]

        accuracy = len(correct) / len(resolved) if resolved else 0.0
        avg_confidence = sum(r.predicted_confidence for r in records) / total if total else 0.0

        # Overconfidence: predictions where confidence > actual accuracy
        overconfident = sum(
            1 for r in resolved if r.predicted_confidence > accuracy and not r.was_correct
        )
        underconfident = sum(
            1 for r in resolved if r.predicted_confidence < accuracy and r.was_correct
        )

        return AccuracyMetrics(
            agent_id=agent_id,
            total_predictions=total,
            resolved_predictions=len(resolved),
            correct_predictions=len(correct),
            accuracy=round(accuracy, 4),
            avg_confidence=round(avg_confidence, 4),
            overconfidence_rate=round(overconfident / len(resolved), 4) if resolved else 0.0,
            underconfidence_rate=round(underconfident / len(resolved), 4) if resolved else 0.0,
        )

    def get_records(self, agent_id: str) -> list[PredictionRecord]:
        """Get all prediction records for an agent."""
        return self._records.get(agent_id, [])

    def list_agents(self) -> list[str]:
        """List all tracked agent IDs."""
        return list(self._records.keys())
