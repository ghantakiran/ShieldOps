"""Compliance gap analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/compliance-gaps", tags=["Compliance Gaps"])

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Compliance gap analyzer service unavailable")
    return _analyzer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterControlRequest(BaseModel):
    framework: str
    control_id: str
    name: str
    description: str = ""
    category: str = "general"


class AssessControlRequest(BaseModel):
    passed: bool
    findings: list[str] = Field(default_factory=list)
    assessor: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/controls")
async def register_control(
    body: RegisterControlRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    control = analyzer.register_control(**body.model_dump())
    return control.model_dump()


@router.post("/assess/{control_id}")
async def assess_control(
    control_id: str,
    body: AssessControlRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    result = analyzer.assess_control(control_id, **body.model_dump())
    if result is None:
        raise HTTPException(404, f"Control '{control_id}' not found")
    return result.model_dump()


@router.get("/controls")
async def list_controls(
    framework: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [c.model_dump() for c in analyzer.list_controls(framework=framework)]


@router.get("/gaps")
async def list_gaps(
    framework: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        g.model_dump()
        for g in analyzer.list_gaps(
            framework=framework,
            severity=severity,
            status=status,
        )
    ]


@router.get("/gaps/{gap_id}")
async def get_gap(
    gap_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    gap = analyzer.get_gap(gap_id)
    if gap is None:
        raise HTTPException(404, f"Gap '{gap_id}' not found")
    return gap.model_dump()


@router.put("/gaps/{gap_id}/remediate")
async def mark_remediated(
    gap_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    gap = analyzer.mark_remediated(gap_id)
    if gap is None:
        raise HTTPException(404, f"Gap '{gap_id}' not found")
    return gap.model_dump()


@router.get("/coverage/{framework}")
async def get_coverage(
    framework: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_coverage(framework)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
