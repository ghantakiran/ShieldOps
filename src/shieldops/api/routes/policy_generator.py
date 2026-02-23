"""Policy generator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/policy-generator", tags=["Policy Generator"])

_generator: Any = None


def set_generator(generator: Any) -> None:
    global _generator
    _generator = generator


def _get_generator() -> Any:
    if _generator is None:
        raise HTTPException(503, "Policy generator service unavailable")
    return _generator


class AddRequirementRequest(BaseModel):
    name: str
    description: str
    category: str
    severity: str
    conditions: list[str] = Field(default_factory=list)


class GeneratePolicyRequest(BaseModel):
    name: str = ""


@router.post("/requirements")
async def add_requirement(
    body: AddRequirementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    generator = _get_generator()
    req = generator.create_requirement(
        description=body.description,
        category=body.category,
        severity=body.severity,
        conditions=body.conditions,
    )
    return req.model_dump()


@router.post("/generate/{requirement_id}")
async def generate_policy(
    requirement_id: str,
    body: GeneratePolicyRequest | None = None,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    generator = _get_generator()
    req = generator.get_requirement(requirement_id)
    if req is None:
        raise HTTPException(
            404,
            f"Requirement '{requirement_id}' not found",
        )
    name = body.name if body and body.name else f"policy-{requirement_id[:8]}"
    policy = generator.generate_policy(requirement_id=requirement_id, name=name)
    return policy.model_dump()


@router.get("/requirements")
async def list_requirements(
    category: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    generator = _get_generator()
    return [r.model_dump() for r in generator.list_requirements(category=category)]


@router.get("/policies")
async def list_policies(
    category: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    generator = _get_generator()
    return [p.model_dump() for p in generator.list_policies(category=category)]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    generator = _get_generator()
    policy = generator.get_policy(policy_id)
    if policy is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return policy.model_dump()


@router.delete("/requirements/{requirement_id}")
async def delete_requirement(
    requirement_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    generator = _get_generator()
    req = generator.get_requirement(requirement_id)
    if req is None:
        raise HTTPException(
            404,
            f"Requirement '{requirement_id}' not found",
        )
    del generator._requirements[requirement_id]
    return {
        "deleted": True,
        "requirement_id": requirement_id,
    }


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    generator = _get_generator()
    return generator.get_stats()
