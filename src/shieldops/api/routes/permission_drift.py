"""Permission drift detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.permission_drift import (
    DriftSeverity,
    DriftType,
    PermissionScope,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/permission-drift",
    tags=["Permission Drift"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Permission drift service unavailable")
    return _engine


class RecordDriftRequest(BaseModel):
    principal: str
    scope: PermissionScope = PermissionScope.IAM
    drift_type: DriftType = DriftType.UNUSED_PERMISSION
    severity: DriftSeverity = DriftSeverity.MEDIUM
    permission: str = ""
    unused_days: int = 0
    details: str = ""


class SetBaselineRequest(BaseModel):
    principal: str
    scope: PermissionScope = PermissionScope.IAM
    permissions: list[str] = []


@router.post("/drifts")
async def record_drift(
    body: RecordDriftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_drift(**body.model_dump())
    return result.model_dump()


@router.get("/drifts")
async def list_drifts(
    principal: str | None = None,
    drift_type: DriftType | None = None,
    severity: DriftSeverity | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_drifts(
            principal=principal, drift_type=drift_type, severity=severity, limit=limit
        )
    ]


@router.get("/drifts/{record_id}")
async def get_drift(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_drift(record_id)
    if result is None:
        raise HTTPException(404, f"Drift record '{record_id}' not found")
    return result.model_dump()


@router.post("/baselines")
async def set_baseline(
    body: SetBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.set_baseline(**body.model_dump())
    return result.model_dump()


@router.get("/unused")
async def detect_unused_permissions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_unused_permissions()


@router.get("/over-privileged")
async def detect_over_privileged_principals(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_over_privileged_principals()


@router.get("/compare/{principal}")
async def compare_to_baseline(
    principal: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compare_to_baseline(principal)


@router.get("/rankings")
async def rank_principals_by_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_principals_by_drift()


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


pd_route = router
