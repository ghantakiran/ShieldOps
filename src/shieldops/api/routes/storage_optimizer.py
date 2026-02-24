"""Storage optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/storage-optimizer", tags=["Storage Optimizer"])

_optimizer: Any = None


def set_optimizer(inst: Any) -> None:
    global _optimizer
    _optimizer = inst


def _get_optimizer() -> Any:
    if _optimizer is None:
        raise HTTPException(503, "Storage optimizer service unavailable")
    return _optimizer


class RegisterAssetRequest(BaseModel):
    asset_name: str
    current_tier: str = "HOT"
    size_gb: float = 0.0
    last_accessed_at: float | None = None
    access_frequency: str = "MONTHLY"
    monthly_cost: float = 0.0


class UpdateStatusRequest(BaseModel):
    status: str


@router.post("/assets")
async def register_asset(
    body: RegisterAssetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    asset = optimizer.register_asset(**body.model_dump())
    return asset.model_dump()


@router.get("/assets")
async def list_assets(
    current_tier: str | None = None,
    access_frequency: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [
        a.model_dump()
        for a in optimizer.list_assets(
            current_tier=current_tier, access_frequency=access_frequency, limit=limit
        )
    ]


@router.get("/assets/{asset_id}")
async def get_asset(
    asset_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    asset = optimizer.get_asset(asset_id)
    if asset is None:
        raise HTTPException(404, f"Asset '{asset_id}' not found")
    return asset.model_dump()


@router.post("/migrations/recommend")
async def recommend_tier_migrations(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [m.model_dump() for m in optimizer.recommend_tier_migrations()]


@router.get("/migrations/{migration_id}")
async def get_migration(
    migration_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    migration = optimizer.get_migration(migration_id)
    if migration is None:
        raise HTTPException(404, f"Migration '{migration_id}' not found")
    return migration.model_dump()


@router.put("/migrations/{migration_id}/status")
async def update_migration_status(
    migration_id: str,
    body: UpdateStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    result = optimizer.update_migration_status(migration_id, status=body.status)
    if not result:
        raise HTTPException(404, f"Migration '{migration_id}' not found")
    return result.model_dump()


@router.get("/cold-data")
async def detect_cold_data(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [d.model_dump() for d in optimizer.detect_cold_data()]


@router.get("/savings")
async def estimate_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.estimate_savings()


@router.get("/optimization-report")
async def generate_optimization_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.generate_optimization_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.get_stats()
