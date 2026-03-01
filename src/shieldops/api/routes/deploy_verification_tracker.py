"""Deploy Verification Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deploy_verification_tracker import (
    VerificationResult,
    VerificationScope,
    VerificationStep,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deploy-verification-tracker",
    tags=["Deploy Verification Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deploy verification tracker service unavailable")
    return _engine


class RecordVerificationRequest(BaseModel):
    deploy_id: str
    verification_step: VerificationStep = VerificationStep.SMOKE_TEST
    verification_result: VerificationResult = VerificationResult.PASSED
    verification_scope: VerificationScope = VerificationScope.UNIT
    coverage_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    deploy_id: str
    verification_step: VerificationStep = VerificationStep.SMOKE_TEST
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/verifications")
async def record_verification(
    body: RecordVerificationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_verification(**body.model_dump())
    return result.model_dump()


@router.get("/verifications")
async def list_verifications(
    step: VerificationStep | None = None,
    result: VerificationResult | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_verifications(
            step=step,
            result=result,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/verifications/{record_id}")
async def get_verification(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_verification(record_id)
    if found is None:
        raise HTTPException(404, f"Verification '{record_id}' not found")
    return found.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_verification_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_verification_distribution()


@router.get("/failed-verifications")
async def identify_failed_verifications(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_verifications()


@router.get("/coverage-rankings")
async def rank_by_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_coverage()


@router.get("/trends")
async def detect_verification_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_verification_trends()


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


dhx_route = router
