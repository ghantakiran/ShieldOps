"""Service health report API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/health-reports", tags=["Health Reports"])

_generator: Any = None


def set_generator(gen: Any) -> None:
    global _generator
    _generator = gen


def _get_generator() -> Any:
    if _generator is None:
        raise HTTPException(503, "Health report service unavailable")
    return _generator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordMetricRequest(BaseModel):
    service: str
    metric_name: str
    value: float
    weight: float = 1.0
    category: str = "general"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/metrics")
async def record_metric(
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    metric = gen.record_metric(**body.model_dump())
    return metric.model_dump()


@router.post("/generate/{service}")
async def generate_report(
    service: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    report = gen.generate_report(service)
    return report.model_dump()


@router.get("/reports")
async def list_reports(
    service: str | None = None,
    min_grade: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    gen = _get_generator()
    return [r.model_dump() for r in gen.list_reports(service=service, min_grade=min_grade)]


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    report = gen.get_report(report_id)
    if report is None:
        raise HTTPException(404, f"Report '{report_id}' not found")
    return report.model_dump()


@router.get("/metrics")
async def list_metrics(
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    gen = _get_generator()
    return [m.model_dump() for m in gen.list_metrics(service=service, limit=limit)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    return gen.get_stats()
