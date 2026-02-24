"""Compliance evidence chain API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.evidence_chain import (
    ChainStatus,
    ComplianceFramework,
    EvidenceType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/evidence-chain",
    tags=["Evidence Chain"],
)

_instance: Any = None


def set_chain_manager(manager: Any) -> None:
    global _instance
    _instance = manager


def _get_chain_manager() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Evidence chain service unavailable",
        )
    return _instance


# -- Request models --


class CreateChainRequest(BaseModel):
    framework: ComplianceFramework = ComplianceFramework.SOC2


class AddEvidenceRequest(BaseModel):
    evidence_type: EvidenceType
    description: str
    content_hash: str
    collector: str = ""


class CoverageRequest(BaseModel):
    framework: ComplianceFramework


# -- Routes --


@router.post("/chains")
async def create_chain(
    body: CreateChainRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    chain = mgr.create_chain(**body.model_dump())
    return chain.model_dump()


@router.get("/chains")
async def list_chains(
    framework: ComplianceFramework | None = None,
    status: ChainStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_chain_manager()
    return [
        c.model_dump()
        for c in mgr.list_chains(
            framework=framework,
            status=status,
            limit=limit,
        )
    ]


@router.get("/chains/{chain_id}")
async def get_chain(
    chain_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    chain = mgr.get_chain(chain_id)
    if chain is None:
        raise HTTPException(
            404,
            f"Chain '{chain_id}' not found",
        )
    return chain.model_dump()


@router.post("/chains/{chain_id}/evidence")
async def add_evidence(
    chain_id: str,
    body: AddEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    item = mgr.add_evidence(
        chain_id=chain_id,
        **body.model_dump(),
    )
    if item is None:
        raise HTTPException(
            404,
            f"Chain '{chain_id}' not found",
        )
    return item.model_dump()


@router.get("/chains/{chain_id}/verify")
async def verify_chain(
    chain_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    return mgr.verify_chain_integrity(chain_id)


@router.get("/chains/{chain_id}/export")
async def export_chain(
    chain_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    result = mgr.export_chain(chain_id)
    if result is None:
        raise HTTPException(
            404,
            f"Chain '{chain_id}' not found",
        )
    return result


@router.get("/broken")
async def get_broken_chains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_chain_manager()
    return mgr.detect_broken_chains()


@router.post("/coverage")
async def get_coverage(
    body: CoverageRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    return mgr.calculate_coverage(body.framework)


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    report = mgr.generate_evidence_report()
    return report.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_chain_manager()
    return mgr.get_stats()
