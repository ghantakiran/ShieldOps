"""Prediction Agent runner — entry point for prediction cycles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.agents.prediction.graph import create_prediction_graph
from shieldops.agents.prediction.models import PredictionState
from shieldops.agents.prediction.nodes import set_toolkit
from shieldops.agents.prediction.tools import PredictionToolkit

logger = structlog.get_logger()


class PredictionRunner:
    """Runs prediction agent workflows."""

    def __init__(
        self,
        anomaly_detector: Any | None = None,
        change_tracker: Any | None = None,
        topology_builder: Any | None = None,
    ) -> None:
        self._toolkit = PredictionToolkit(
            anomaly_detector=anomaly_detector,
            change_tracker=change_tracker,
            topology_builder=topology_builder,
        )
        set_toolkit(self._toolkit)

        graph = create_prediction_graph()
        self._app = graph.compile()
        self._predictions: dict[str, PredictionState] = {}

    async def predict(
        self,
        target_resources: list[str] | None = None,
        lookback_hours: int = 24,
    ) -> PredictionState:
        """Run a prediction cycle."""
        prediction_id = f"pred-{uuid4().hex[:12]}"

        logger.info(
            "prediction_cycle_started",
            prediction_id=prediction_id,
            resources=len(target_resources or []),
            lookback_hours=lookback_hours,
        )

        initial_state = PredictionState(
            prediction_id=prediction_id,
            target_resources=target_resources or [],
            lookback_hours=lookback_hours,
        )

        try:
            final_state_dict = await self._app.ainvoke(
                initial_state.model_dump(),  # type: ignore[arg-type]
                config={"metadata": {"prediction_id": prediction_id}},
            )

            final_state = PredictionState.model_validate(final_state_dict)

            if final_state.prediction_start:
                final_state.prediction_duration_ms = int(
                    (datetime.now(UTC) - final_state.prediction_start).total_seconds() * 1000
                )

            logger.info(
                "prediction_cycle_completed",
                prediction_id=prediction_id,
                predictions=len(final_state.predictions),
                risk_score=final_state.risk_score,
                duration_ms=final_state.prediction_duration_ms,
            )

            self._predictions[prediction_id] = final_state
            return final_state

        except Exception as e:
            logger.error(
                "prediction_cycle_failed",
                prediction_id=prediction_id,
                error=str(e),
            )
            error_state = PredictionState(
                prediction_id=prediction_id,
                error=str(e),
                current_step="failed",
            )
            self._predictions[prediction_id] = error_state
            return error_state

    def get_prediction(self, prediction_id: str) -> PredictionState | None:
        """Retrieve a prediction cycle by ID."""
        return self._predictions.get(prediction_id)

    def list_predictions(self) -> list[dict[str, Any]]:
        """List all prediction cycles with summary info."""
        return [
            {
                "prediction_id": pid,
                "status": state.current_step,
                "predictions_count": len(state.predictions),
                "risk_score": state.risk_score,
                "duration_ms": state.prediction_duration_ms,
                "error": state.error,
            }
            for pid, state in self._predictions.items()
        ]

    def get_active_predictions(self, min_confidence: float = 0.5) -> list[dict[str, Any]]:
        """Get active high-confidence predictions across all cycles."""
        active = []
        for state in self._predictions.values():
            for pred in state.predictions:
                if pred.confidence >= min_confidence:
                    active.append(pred.model_dump())
        return sorted(active, key=lambda p: p["confidence"], reverse=True)
