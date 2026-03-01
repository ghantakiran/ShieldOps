"""Vulnerability Prioritizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.vuln_prioritizer import (
    ExploitMaturity,
    RemediationStatus,
    VulnSeverity,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/vuln-prioritizer", tags=["Vulnerability Prioritizer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Vulnerability prioritizer service unavailable")
    return _engine


class RecordVulnRequest(BaseModel):
    cve_id: str
    vuln_severity: VulnSeverity = VulnSeverity.LOW
    exploit_maturity: ExploitMaturity = ExploitMaturity.UNPROVEN
    remediation_status: RemediationStatus = RemediationStatus.OPEN
    cvss_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    cve_pattern: str
    vuln_severity: VulnSeverity = VulnSeverity.LOW
    max_age_days: int = 0
    auto_escalate: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_vuln(
    body: RecordVulnRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_vuln(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_vulns(
    severity: VulnSeverity | None = None,
    maturity: ExploitMaturity | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_vulns(
            severity=severity,
            maturity=maturity,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_vuln(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_vuln(record_id)
    if result is None:
        raise HTTPException(404, f"Vulnerability record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_severity_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_severity_distribution()


@router.get("/urgent")
async def identify_urgent_vulns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_urgent_vulns()


@router.get("/cvss-rankings")
async def rank_by_cvss(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cvss()


@router.get("/trends")
async def detect_vuln_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_vuln_trends()


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


vpr_route = router
