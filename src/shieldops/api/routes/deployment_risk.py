"""Deployment risk prediction API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/deployment-risk", tags=["Deployment Risk"])

_predictor: Any = None


def set_predictor(predictor: Any) -> None:
    global _predictor
    _predictor = predictor


def _get_predictor() -> Any:
    if _predictor is None:
        raise HTTPException(503, "Deployment risk service unavailable")
    return _predictor


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordDeploymentRequest(BaseModel):
    service: str
    version: str = ""
    change_size: int = 0
    files_changed: int = 0
    has_db_migration: bool = False
    is_rollback: bool = False
    failed: bool = False


class PredictRiskRequest(BaseModel):
    change_size: int = 0
    files_changed: int = 0
    has_db_migration: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/deployments")
async def record_deployment(
    body: RecordDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    rec = predictor.record_deployment(
        service=body.service,
        version=body.version,
        change_size=body.change_size,
        success=not body.failed,
        rollback_needed=body.is_rollback,
    )
    return rec.model_dump()


@router.post("/predict/{service}")
async def predict_risk(
    service: str,
    body: PredictRiskRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    assessment = predictor.assess_risk(
        service=service,
        change_size=body.change_size,
    )
    return assessment.model_dump()


@router.get("/deployments")
async def list_deployments(
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    if service is not None:
        recs = predictor.get_service_history(
            service=service,
            limit=limit,
        )
    else:
        recs = predictor._records[-limit:]
    return [r.model_dump() for r in recs]


@router.get("/assessments")
async def list_assessments(
    service: str | None = None,
    min_risk_level: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    predictor = _get_predictor()
    return [
        a.model_dump()
        for a in predictor.list_assessments(
            service=service,
            risk=min_risk_level,
        )
    ]


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    assessment = predictor.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(404, f"Assessment '{assessment_id}' not found")
    return assessment.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    predictor = _get_predictor()
    return predictor.get_stats()
