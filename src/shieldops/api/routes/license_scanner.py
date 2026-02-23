"""Dependency license scanner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/license-scanner",
    tags=["License Scanner"],
)

_scanner: Any = None


def set_scanner(scanner: Any) -> None:
    global _scanner
    _scanner = scanner


def _get_scanner() -> Any:
    if _scanner is None:
        raise HTTPException(503, "License scanner service unavailable")
    return _scanner


class RegisterDependencyRequest(BaseModel):
    name: str
    version: str = ""
    spdx_id: str = ""
    project: str = ""


class BatchDependencyRequest(BaseModel):
    dependencies: list[RegisterDependencyRequest]


class CreatePolicyRequest(BaseModel):
    name: str
    spdx_pattern: str = ""
    category: str | None = None
    action: str = "allow"


@router.post("/dependencies")
async def register_dependency(
    body: RegisterDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    dep = scanner.register_dependency(
        name=body.name,
        version=body.version,
        spdx_id=body.spdx_id,
        project=body.project,
    )
    return dep.model_dump()


@router.post("/dependencies/batch")
async def register_batch(
    body: BatchDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    count = 0
    for d in body.dependencies:
        scanner.register_dependency(
            name=d.name,
            version=d.version,
            spdx_id=d.spdx_id,
            project=d.project,
        )
        count += 1
    return {"registered": count}


@router.get("/dependencies")
async def list_dependencies(
    project: str | None = None,
    category: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    deps = scanner.list_dependencies(project=project, category=category)
    return [d.model_dump() for d in deps[-limit:]]


@router.post("/policies")
async def create_policy(
    body: CreatePolicyRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    policy = scanner.create_policy(
        name=body.name,
        spdx_pattern=body.spdx_pattern,
        category=body.category,
        action=body.action,
    )
    return policy.model_dump()


@router.get("/policies")
async def list_policies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    policies = scanner.list_policies()
    return [p.model_dump() for p in policies]


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    policy = scanner.get_policy(policy_id)
    if policy is None:
        raise HTTPException(404, f"Policy '{policy_id}' not found")
    return policy.model_dump()


@router.post("/evaluate/{project}")
async def evaluate_project(
    project: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    violations = scanner.evaluate_project(project)
    return [v.model_dump() for v in violations]


@router.get("/violations")
async def list_violations(
    project: str | None = None,
    action: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scanner = _get_scanner()
    violations = scanner.list_violations(project=project, action=action)
    return [v.model_dump() for v in violations[-limit:]]


@router.get("/classify/{spdx_id}")
async def classify_license(
    spdx_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    category = scanner.classify_license(spdx_id)
    risk = scanner.assess_risk(spdx_id)
    return {"spdx_id": spdx_id, "category": category, "risk": risk}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scanner = _get_scanner()
    return scanner.get_stats()
