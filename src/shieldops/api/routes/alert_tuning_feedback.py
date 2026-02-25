"""Alert tuning feedback loop API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.alert_tuning_feedback import AlertFeedback

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-tuning-feedback",
    tags=["Alert Tuning Feedback"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Alert tuning feedback service unavailable",
        )
    return _engine


class RecordFeedbackRequest(BaseModel):
    rule_name: str
    alert_id: str = ""
    feedback: AlertFeedback = AlertFeedback.ACTIONABLE
    responder_id: str = ""
    comment: str = ""


@router.post("/feedback")
async def record_feedback(
    body: RecordFeedbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_feedback(**body.model_dump())
    return result.model_dump()


@router.get("/feedback")
async def list_feedback(
    rule_name: str | None = None,
    feedback: AlertFeedback | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_feedback(rule_name=rule_name, feedback=feedback, limit=limit)
    ]


@router.get("/feedback/{record_id}")
async def get_feedback(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_feedback(record_id)
    if result is None:
        raise HTTPException(404, f"Feedback '{record_id}' not found")
    return result.model_dump()


@router.get("/effectiveness/{rule_name}")
async def evaluate_rule_effectiveness(
    rule_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.evaluate_rule_effectiveness(rule_name).model_dump()


@router.get("/noisy-rules")
async def identify_noisy_rules(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_noisy_rules()


@router.get("/blind-spots")
async def identify_blind_spots(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_blind_spots()


@router.get("/tuning-actions")
async def recommend_tuning_actions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.recommend_tuning_actions()


@router.get("/rule-health/{rule_name}")
async def calculate_rule_health(
    rule_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_rule_health(rule_name)


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


atf_route = router
