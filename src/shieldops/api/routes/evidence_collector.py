"""Compliance evidence collector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/compliance-evidence", tags=["Compliance Evidence"])

_collector: Any = None


def set_collector(collector: Any) -> None:
    global _collector
    _collector = collector


def _get_collector() -> Any:
    if _collector is None:
        raise HTTPException(503, "Compliance evidence service unavailable")
    return _collector


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CollectEvidenceRequest(BaseModel):
    title: str
    evidence_type: str
    framework: str
    control_id: str = ""
    description: str = ""
    source_system: str = ""
    file_path: str = ""
    hash_value: str = ""
    collected_by: str = ""
    valid_from: float | None = None
    valid_until: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreatePackageRequest(BaseModel):
    name: str
    framework: str
    evidence_ids: list[str] = Field(default_factory=list)


class AddToPackageRequest(BaseModel):
    evidence_id: str


class FinalizePackageRequest(BaseModel):
    reviewer: str
    notes: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/evidence")
async def collect_evidence(
    body: CollectEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    item = collector.collect_evidence(**body.model_dump())
    return item.model_dump()


@router.get("/evidence")
async def list_evidence(
    framework: str | None = None,
    evidence_type: str | None = None,
    control_id: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    collector = _get_collector()
    return [
        e.model_dump()
        for e in collector.list_evidence(
            framework=framework,
            evidence_type=evidence_type,
            control_id=control_id,
        )
    ]


@router.get("/evidence/{evidence_id}")
async def get_evidence(
    evidence_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    item = collector.get_evidence(evidence_id)
    if item is None:
        raise HTTPException(404, f"Evidence '{evidence_id}' not found")
    return item.model_dump()


@router.delete("/evidence/{evidence_id}")
async def delete_evidence(
    evidence_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    deleted = collector.delete_evidence(evidence_id)
    if not deleted:
        raise HTTPException(404, f"Evidence '{evidence_id}' not found")
    return {"deleted": True, "evidence_id": evidence_id}


@router.post("/packages")
async def create_package(
    body: CreatePackageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    package = collector.create_package(**body.model_dump())
    return package.model_dump()


@router.get("/packages")
async def list_packages(
    framework: str | None = None,
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    collector = _get_collector()
    return [
        p.model_dump()
        for p in collector.list_packages(
            framework=framework,
            status=status,
        )
    ]


@router.get("/packages/{package_id}")
async def get_package(
    package_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    package = collector.get_package(package_id)
    if package is None:
        raise HTTPException(404, f"Package '{package_id}' not found")
    return package.model_dump()


@router.put("/packages/{package_id}/add-evidence")
async def add_to_package(
    package_id: str,
    body: AddToPackageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    package = collector.add_to_package(package_id, body.evidence_id)
    if package is None:
        raise HTTPException(404, f"Package '{package_id}' not found")
    return package.model_dump()


@router.put("/packages/{package_id}/finalize")
async def finalize_package(
    package_id: str,
    body: FinalizePackageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    package = collector.finalize_package(package_id, body.reviewer, notes=body.notes)
    if package is None:
        raise HTTPException(404, f"Package '{package_id}' not found")
    return package.model_dump()


@router.get("/coverage/{framework}")
async def get_coverage(
    framework: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    return collector.get_coverage(framework)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    collector = _get_collector()
    return collector.get_stats()
