"""Vulnerability lifecycle manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/vuln-lifecycle",
    tags=["Vulnerability Lifecycle"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Vulnerability lifecycle service unavailable")
    return _manager


class RegisterVulnRequest(BaseModel):
    cve_id: str = ""
    title: str = ""
    description: str = ""
    severity: str = "medium"
    cvss_score: float = 0.0
    affected_services: list[str] | None = None


class AdvancePhaseRequest(BaseModel):
    new_phase: str


class RecordPatchRequest(BaseModel):
    patch_version: str = ""
    outcome: str = "pending"
    applied_by: str = ""
    notes: str = ""


@router.post("/vulnerabilities")
async def register_vulnerability(
    body: RegisterVulnRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    vuln = manager.register_vulnerability(
        cve_id=body.cve_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        cvss_score=body.cvss_score,
        affected_services=body.affected_services,
    )
    return vuln.model_dump()


@router.get("/vulnerabilities")
async def list_vulnerabilities(
    phase: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    vulns = manager.list_vulnerabilities(phase=phase, severity=severity, limit=limit)
    return [v.model_dump() for v in vulns]


@router.get("/vulnerabilities/{vuln_id}")
async def get_vulnerability(
    vuln_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    vuln = manager.get_vulnerability(vuln_id)
    if vuln is None:
        raise HTTPException(404, f"Vulnerability '{vuln_id}' not found")
    return vuln.model_dump()


@router.post("/vulnerabilities/{vuln_id}/advance")
async def advance_phase(
    vuln_id: str,
    body: AdvancePhaseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    if not manager.advance_phase(vuln_id, body.new_phase):
        raise HTTPException(404, f"Vulnerability '{vuln_id}' not found")
    return {"advanced": True}


@router.post("/vulnerabilities/{vuln_id}/patch")
async def record_patch_attempt(
    vuln_id: str,
    body: RecordPatchRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    attempt = manager.record_patch_attempt(
        vuln_id=vuln_id,
        patch_version=body.patch_version,
        outcome=body.outcome,
        applied_by=body.applied_by,
        notes=body.notes,
    )
    if attempt is None:
        raise HTTPException(404, f"Vulnerability '{vuln_id}' not found")
    return attempt.model_dump()


@router.get("/vulnerabilities/{vuln_id}/exploit-risk")
async def predict_exploit_risk(
    vuln_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    prediction = manager.predict_exploit_risk(vuln_id)
    if prediction is None:
        raise HTTPException(404, f"Vulnerability '{vuln_id}' not found")
    return prediction.model_dump()


@router.get("/overdue")
async def get_overdue_patches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    manager = _get_manager()
    return manager.get_overdue_patches()


@router.get("/risk-summary")
async def get_risk_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_risk_summary()


@router.get("/patch-success")
async def get_patch_success_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_patch_success_rate()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    manager = _get_manager()
    return manager.get_stats()
