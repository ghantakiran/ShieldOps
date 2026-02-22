"""Security report generation API endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/security/reports", tags=["Security Reports"])

_report_generator: Any = None


def set_generator(gen: Any) -> None:
    global _report_generator
    _report_generator = gen


@router.post("/executive")
async def generate_executive_report(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _report_generator is None:
        raise HTTPException(status_code=501, detail="Report generation not configured")
    report = await _report_generator.generate_executive_report()
    data: dict[str, Any] = report.model_dump()
    return data


@router.post("/compliance/{framework}")
async def generate_compliance_report(
    framework: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _report_generator is None:
        raise HTTPException(status_code=501, detail="Report generation not configured")
    report = await _report_generator.generate_compliance_report(framework)
    data: dict[str, Any] = report.model_dump()
    return data


@router.post("/vulnerability")
async def generate_vulnerability_report(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    if _report_generator is None:
        raise HTTPException(status_code=501, detail="Report generation not configured")
    report = await _report_generator.generate_vulnerability_report()
    data: dict[str, Any] = report.model_dump()
    return data


@router.get("/history")
async def report_history(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, list[dict[str, Any]]]:
    if _report_generator is None:
        raise HTTPException(status_code=501, detail="Report generation not configured")
    return {"reports": _report_generator.get_history()}
