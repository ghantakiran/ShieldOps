"""Alert fatigue scoring API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-fatigue",
    tags=["Alert Fatigue"],
)

_instance: Any = None


def set_scorer(scorer: Any) -> None:
    global _instance
    _instance = scorer


def _get_scorer() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Alert fatigue service unavailable",
        )
    return _instance


# -- Request models --


class RecordAlertRequest(BaseModel):
    team: str
    service_name: str = ""
    alert_count: int = 1
    actionable_count: int = 0
    ignored_count: int = 0
    engagement_rate: float = 0.0


class CalculateScoreRequest(BaseModel):
    team: str


# -- Routes --


@router.post("/records")
async def record_alert(
    body: RecordAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    record = scorer.record_alert(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_records(
    team: str | None = None,
    service_name: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [
        r.model_dump()
        for r in scorer.list_records(
            team=team,
            service_name=service_name,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    record = scorer.get_record(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Record '{record_id}' not found",
        )
    return record.model_dump()


@router.post("/score")
async def calculate_score(
    body: CalculateScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.calculate_fatigue_score(body.team)
    return score.model_dump()


@router.get("/trends")
async def get_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return scorer.detect_fatigue_trends()


@router.get("/noisy")
async def get_noisy_alerts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return scorer.identify_noisy_alerts()


@router.get("/rankings")
async def get_rankings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.rank_teams_by_fatigue()]


@router.get("/tuning")
async def get_tuning_suggestions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return scorer.suggest_alert_tuning()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.generate_fatigue_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.get_stats()
