"""API routes for agent confidence calibration and accuracy tracking."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shieldops.agents.calibration.calibrator import ConfidenceCalibrator
from shieldops.agents.calibration.tracker import AccuracyTracker

router = APIRouter()

_tracker: AccuracyTracker | None = None
_calibrator: ConfidenceCalibrator | None = None


def set_calibration(tracker: AccuracyTracker, calibrator: ConfidenceCalibrator) -> None:
    global _tracker, _calibrator
    _tracker = tracker
    _calibrator = calibrator


def _get_tracker() -> AccuracyTracker:
    if _tracker is None:
        raise HTTPException(status_code=503, detail="Calibration tracker not initialized")
    return _tracker


def _get_calibrator() -> ConfidenceCalibrator:
    if _calibrator is None:
        raise HTTPException(status_code=503, detail="Calibrator not initialized")
    return _calibrator


class RecordPredictionRequest(BaseModel):
    confidence: float
    predicted_outcome: str
    agent_type: str = ""


class RecordFeedbackRequest(BaseModel):
    prediction_id: str
    was_correct: bool
    feedback_source: str = "human"


@router.get("/agents/{agent_id}/calibration")
async def get_calibration(agent_id: str) -> dict[str, Any]:
    """Get calibration curve for an agent."""
    calibrator = _get_calibrator()
    curve = calibrator.compute_calibration(agent_id)
    return curve.model_dump()


@router.get("/agents/{agent_id}/accuracy")
async def get_accuracy(agent_id: str) -> dict[str, Any]:
    """Get accuracy metrics for an agent."""
    tracker = _get_tracker()
    metrics = tracker.get_accuracy(agent_id)
    return metrics.model_dump()


@router.post("/agents/{agent_id}/predictions")
async def record_prediction(agent_id: str, body: RecordPredictionRequest) -> dict[str, Any]:
    """Record a new prediction from an agent."""
    tracker = _get_tracker()
    record = tracker.record_prediction(
        agent_id=agent_id,
        confidence=body.confidence,
        predicted_outcome=body.predicted_outcome,
        agent_type=body.agent_type,
    )
    return record.model_dump()


@router.post("/agents/{agent_id}/feedback")
async def record_feedback(agent_id: str, body: RecordFeedbackRequest) -> dict[str, Any]:
    """Record feedback on whether a prediction was correct."""
    tracker = _get_tracker()
    record = tracker.record_feedback(
        agent_id=agent_id,
        prediction_id=body.prediction_id,
        was_correct=body.was_correct,
        feedback_source=body.feedback_source,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return record.model_dump()


@router.get("/agents/{agent_id}/threshold-recommendation")
async def get_threshold_recommendation(
    agent_id: str,
    current_threshold: float = 0.85,
    target_accuracy: float = 0.90,
) -> dict[str, Any]:
    """Get threshold adjustment recommendation for an agent."""
    calibrator = _get_calibrator()
    rec = calibrator.calibrate_threshold(
        agent_id=agent_id,
        current_threshold=current_threshold,
        target_accuracy=target_accuracy,
    )
    return rec.model_dump()


@router.get("/calibration/all")
async def get_all_calibrations() -> dict[str, Any]:
    """Get calibration data for all tracked agents."""
    calibrator = _get_calibrator()
    curves = calibrator.get_all_calibrations()
    return {
        "agents": {k: v.model_dump() for k, v in curves.items()},
        "count": len(curves),
    }
