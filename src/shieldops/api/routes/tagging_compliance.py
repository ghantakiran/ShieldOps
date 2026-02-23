"""Cloud resource tagging compliance API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/tagging-compliance", tags=["Tagging Compliance"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Tagging compliance service unavailable")
    return _engine


class CreatePolicyRequest(BaseModel):
    name: str
    required_tags: list[str] = Field(default_factory=list)
    optional_tags: list[str] = Field(default_factory=list)
    allowed_values: dict[str, list[str]] = Field(default_factory=dict)
    provider: str | None = None


class ScanResourceRequest(BaseModel):
    resource_id: str
    resource_type: str
    provider: str
    tags: dict[str, str] = Field(default_factory=dict)


class SuggestTagsRequest(BaseModel):
    resource_id: str
    resource_type: str


@router.post("/policies")
async def create_policy(
    body: CreatePolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    policy = engine.create_policy(**body.model_dump())
    return policy.model_dump()


@router.get("/policies")
async def list_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [p.model_dump() for p in engine.list_policies()]


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    if not engine.delete_policy(policy_id):
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return {"status": "deleted"}


@router.post("/scan")
async def scan_resource(
    body: ScanResourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.scan_resource(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_records(
    status: str | None = None,
    provider: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_records(status=status, provider=provider)]


@router.get("/records/{resource_id}")
async def get_record(
    resource_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_record(resource_id)
    if record is None:
        raise HTTPException(404, f"Record '{resource_id}' not found")
    return record.model_dump()


@router.get("/report")
async def get_compliance_report(
    provider: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_compliance_report(provider=provider).model_dump()


@router.post("/suggest")
async def suggest_tags(
    body: SuggestTagsRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.suggest_tags(**body.model_dump())


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
