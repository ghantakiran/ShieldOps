"""Compliance auditor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.compliance_auditor import (
    AuditResult,
    ComplianceFramework,
    EvidenceType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/compliance-auditor",
    tags=["Compliance Auditor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Compliance auditor service unavailable")
    return _engine


class RecordAuditRequest(BaseModel):
    agent_name: str
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    audit_result: AuditResult = AuditResult.PASS
    evidence_type: EvidenceType = EvidenceType.LOG_ENTRY
    finding_count: int = 0
    details: str = ""


class AddEvidenceRequest(BaseModel):
    evidence_label: str
    compliance_framework: ComplianceFramework = ComplianceFramework.PCI_DSS
    audit_result: AuditResult = AuditResult.WARNING
    confidence_score: float = 0.0


@router.post("/audits")
async def record_audit(
    body: RecordAuditRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_audit(**body.model_dump())
    return result.model_dump()


@router.get("/audits")
async def list_audits(
    agent_name: str | None = None,
    compliance_framework: ComplianceFramework | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_audits(
            agent_name=agent_name, compliance_framework=compliance_framework, limit=limit
        )
    ]


@router.get("/audits/{record_id}")
async def get_audit(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_audit(record_id)
    if result is None:
        raise HTTPException(404, f"Audit '{record_id}' not found")
    return result.model_dump()


@router.post("/evidence")
async def add_evidence(
    body: AddEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_evidence(**body.model_dump())
    return result.model_dump()


@router.get("/compliance/{agent_name}")
async def analyze_agent_compliance(
    agent_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_agent_compliance(agent_name)


@router.get("/non-compliant")
async def identify_non_compliant_agents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_non_compliant_agents()


@router.get("/rankings")
async def rank_by_compliance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_compliance_score()


@router.get("/drift")
async def detect_compliance_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_compliance_drift()


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


aca_route = router
