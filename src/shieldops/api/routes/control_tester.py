"""Compliance control tester API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.control_tester import (
    ControlTestFrequency,
    ControlTestResult,
    ControlType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/control-tester",
    tags=["Control Tester"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Control tester service unavailable")
    return _engine


class RecordTestRequest(BaseModel):
    model_config = {"extra": "forbid"}

    control_id: str
    result: ControlTestResult = ControlTestResult.PASS
    control_type: ControlType = ControlType.PREVENTIVE
    frequency: ControlTestFrequency = ControlTestFrequency.MONTHLY
    pass_rate_pct: float = 0.0
    framework: str = ""
    details: str = ""


class AddEvidenceRequest(BaseModel):
    model_config = {"extra": "forbid"}

    test_record_id: str
    evidence_type: str = ""
    description: str = ""
    verified: bool = False


@router.post("/tests")
async def record_test(
    body: RecordTestRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_test(**body.model_dump())
    return result.model_dump()


@router.get("/tests")
async def list_tests(
    result: ControlTestResult | None = None,
    control_type: ControlType | None = None,
    framework: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_tests(
            result=result,
            control_type=control_type,
            framework=framework,
            limit=limit,
        )
    ]


@router.get("/tests/{record_id}")
async def get_test(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_test(record_id)
    if result is None:
        raise HTTPException(404, f"Test record '{record_id}' not found")
    return result.model_dump()


@router.post("/evidence")
async def add_evidence(
    body: AddEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_evidence(**body.model_dump())
    return result.model_dump()


@router.get("/analysis")
async def analyze_test_results(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_test_results()


@router.get("/failing")
async def identify_failing_controls(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failing_controls()


@router.get("/rankings")
async def rank_by_pass_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_pass_rate()


@router.get("/trends")
async def detect_test_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_test_trends()


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


cct_route = router
