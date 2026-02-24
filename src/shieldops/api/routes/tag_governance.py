"""Resource tag governance API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/tag-governance",
    tags=["Tag Governance"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Tag governance service unavailable")
    return _engine


class CreatePolicyRequest(BaseModel):
    name: str
    required_tags: list[str] | None = None
    action: str = "enforce"
    default_values: dict[str, str] | None = None
    resource_types: list[str] | None = None


class EvaluateResourceRequest(BaseModel):
    resource_id: str
    resource_type: str = ""
    existing_tags: dict[str, str] | None = None


class EvaluateBulkRequest(BaseModel):
    resources: list[dict[str, Any]]


@router.post("/policies")
async def create_policy(
    body: CreatePolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    policy = engine.create_policy(
        name=body.name,
        required_tags=body.required_tags,
        action=body.action,
        default_values=body.default_values,
        resource_types=body.resource_types,
    )
    return policy.model_dump()


@router.get("/policies")
async def list_policies(
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    policies = engine.list_policies(limit=limit)
    return [p.model_dump() for p in policies]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    policy = engine.get_policy(policy_id)
    if policy is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return policy.model_dump()


@router.post("/evaluate")
async def evaluate_resource(
    body: EvaluateResourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.evaluate_resource(
        resource_id=body.resource_id,
        resource_type=body.resource_type,
        existing_tags=body.existing_tags,
    )
    return report.model_dump()


@router.post("/evaluate-bulk")
async def evaluate_bulk(
    body: EvaluateBulkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    reports = engine.evaluate_bulk(body.resources)
    return [r.model_dump() for r in reports]


@router.post("/auto-tag")
async def auto_tag_resource(
    body: EvaluateResourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    applied = engine.auto_tag_resource(
        resource_id=body.resource_id,
        resource_type=body.resource_type,
        existing_tags=body.existing_tags,
    )
    return {"applied_tags": applied}


@router.get("/compliance")
async def get_compliance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_compliance_score().model_dump()


@router.get("/untagged")
async def get_untagged_resources(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.get_untagged_resources(limit=limit)


@router.get("/reports")
async def list_reports(
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    reports = engine.list_reports(limit=limit)
    return [r.model_dump() for r in reports]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
