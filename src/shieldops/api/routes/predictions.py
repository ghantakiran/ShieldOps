"""API routes for predictive incident detection."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.prediction.runner import PredictionRunner

router = APIRouter()

_runner: PredictionRunner | None = None


def set_runner(runner: PredictionRunner) -> None:
    global _runner
    _runner = runner


def _get_runner() -> PredictionRunner:
    if _runner is None:
        raise HTTPException(status_code=503, detail="Prediction runner not initialized")
    return _runner


class PredictionRequest(BaseModel):
    target_resources: list[str] = Field(default_factory=list)
    lookback_hours: int = 24


@router.post("/predictions/run")
async def run_prediction(body: PredictionRequest) -> dict[str, Any]:
    runner = _get_runner()
    result = await runner.predict(
        target_resources=body.target_resources,
        lookback_hours=body.lookback_hours,
    )
    return result.model_dump()


@router.get("/predictions")
async def list_predictions() -> dict[str, Any]:
    runner = _get_runner()
    predictions = runner.list_predictions()
    return {"predictions": predictions, "count": len(predictions)}


@router.get("/predictions/active")
async def active_predictions(min_confidence: float = 0.5) -> dict[str, Any]:
    runner = _get_runner()
    active = runner.get_active_predictions(min_confidence=min_confidence)
    return {"predictions": active, "count": len(active)}


@router.get("/predictions/{prediction_id}")
async def get_prediction(prediction_id: str) -> dict[str, Any]:
    runner = _get_runner()
    result = runner.get_prediction(prediction_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return result.model_dump()
