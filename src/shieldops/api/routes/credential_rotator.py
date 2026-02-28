"""Credential rotation orchestrator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.credential_rotator import (
    CredentialType,
    RotationStatus,
    RotationStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/credential-rotator",
    tags=["Credential Rotator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Credential-rotator service unavailable")
    return _engine


class RecordRotationRequest(BaseModel):
    service_name: str
    credential_type: CredentialType = CredentialType.API_KEY
    status: RotationStatus = RotationStatus.SCHEDULED
    strategy: RotationStrategy = RotationStrategy.ZERO_DOWNTIME
    duration_seconds: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    credential_type: CredentialType = CredentialType.API_KEY
    strategy: RotationStrategy = RotationStrategy.ZERO_DOWNTIME
    rotation_interval_days: int = 90
    max_age_days: float = 180.0


@router.post("/rotations")
async def record_rotation(
    body: RecordRotationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_rotation(**body.model_dump())
    return result.model_dump()


@router.get("/rotations")
async def list_rotations(
    service_name: str | None = None,
    credential_type: CredentialType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_rotations(
            service_name=service_name,
            credential_type=credential_type,
            limit=limit,
        )
    ]


@router.get("/rotations/{record_id}")
async def get_rotation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_rotation(record_id)
    if result is None:
        raise HTTPException(404, f"Rotation '{record_id}' not found")
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/health/{service_name}")
async def analyze_rotation_health(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_rotation_health(service_name)


@router.get("/failed-rotations")
async def identify_failed_rotations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_rotations()


@router.get("/rankings")
async def rank_by_rotation_frequency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_rotation_frequency()


@router.get("/stale-credentials")
async def detect_stale_credentials(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_stale_credentials()


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


cro_route = router
