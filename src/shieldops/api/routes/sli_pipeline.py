"""SLI pipeline API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/sli-pipeline", tags=["SLI Pipeline"])

_pipeline: Any = None


def set_pipeline(pipeline: Any) -> None:
    global _pipeline
    _pipeline = pipeline


def _get_pipeline() -> Any:
    if _pipeline is None:
        raise HTTPException(503, "SLI pipeline service unavailable")
    return _pipeline


class RegisterSLIRequest(BaseModel):
    service_name: str
    sli_type: str = "AVAILABILITY"
    name: str = ""
    aggregation: str = "AVERAGE"
    target_value: float = 99.9
    warning_threshold: float = 99.5
    critical_threshold: float = 99.0
    unit: str = "percent"


class IngestDataPointRequest(BaseModel):
    value: float
    timestamp: float | None = None
    labels: dict[str, str] | None = None


@router.post("/definitions")
async def register_sli(
    body: RegisterSLIRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    sli = pipeline.register_sli(**body.model_dump())
    return sli.model_dump()


@router.get("/definitions")
async def list_slis(
    service_name: str | None = None,
    sli_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    pipeline = _get_pipeline()
    return [
        s.model_dump()
        for s in pipeline.list_slis(service_name=service_name, sli_type=sli_type, limit=limit)
    ]


@router.get("/definitions/{sli_id}")
async def get_sli(
    sli_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    sli = pipeline.get_sli(sli_id)
    if sli is None:
        raise HTTPException(404, f"SLI '{sli_id}' not found")
    return sli.model_dump()


@router.post("/definitions/{sli_id}/data-points")
async def ingest_data_point(
    sli_id: str,
    body: IngestDataPointRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    result = pipeline.ingest_data_point(sli_id, **body.model_dump())
    if result is None:
        raise HTTPException(404, f"SLI '{sli_id}' not found")
    return result.model_dump()


@router.post("/definitions/{sli_id}/calculate")
async def calculate_sli_value(
    sli_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    result = pipeline.calculate_sli_value(sli_id)
    return result.model_dump()


@router.post("/definitions/{sli_id}/health")
async def evaluate_sli_health(
    sli_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    result = pipeline.evaluate_sli_health(sli_id)
    return result.model_dump()


@router.post("/definitions/{sli_id}/regression")
async def detect_sli_regression(
    sli_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    result = pipeline.detect_sli_regression(sli_id)
    return result.model_dump()


@router.get("/services/{service_name}/aggregate")
async def aggregate_service_slis(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    result = pipeline.aggregate_service_slis(service_name)
    return result.model_dump()


@router.get("/report")
async def generate_pipeline_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    return pipeline.generate_pipeline_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    pipeline = _get_pipeline()
    return pipeline.get_stats()
