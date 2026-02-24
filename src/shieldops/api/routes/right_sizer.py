"""Right sizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/right-sizer", tags=["Right Sizer"])

_right_sizer: Any = None


def set_right_sizer(inst: Any) -> None:
    global _right_sizer
    _right_sizer = inst


def _get_right_sizer() -> Any:
    if _right_sizer is None:
        raise HTTPException(503, "Right sizer service unavailable")
    return _right_sizer


class RecordUtilizationRequest(BaseModel):
    resource_id: str
    resource_type: str = "COMPUTE"
    utilization_pct: float = 0.0
    instance_type: str = ""
    cost_per_hour: float = 0.0
    region: str = ""


@router.post("/utilization")
async def record_utilization(
    body: RecordUtilizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    sizer = _get_right_sizer()
    sample = sizer.record_utilization(**body.model_dump())
    return sample.model_dump()


@router.get("/utilization")
async def list_samples(
    resource_id: str | None = None,
    resource_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    sizer = _get_right_sizer()
    return [
        s.model_dump()
        for s in sizer.list_samples(
            resource_id=resource_id, resource_type=resource_type, limit=limit
        )
    ]


@router.get("/utilization/{sample_id}")
async def get_sample(
    sample_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    sizer = _get_right_sizer()
    sample = sizer.get_sample(sample_id)
    if sample is None:
        raise HTTPException(404, f"Sample '{sample_id}' not found")
    return sample.model_dump()


@router.post("/recommendations/generate")
async def generate_recommendations(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    sizer = _get_right_sizer()
    return [r.model_dump() for r in sizer.generate_recommendations()]


@router.get("/recommendations")
async def list_recommendations(
    action: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    sizer = _get_right_sizer()
    return [r.model_dump() for r in sizer.list_recommendations(action=action, limit=limit)]


@router.get("/recommendations/{rec_id}")
async def get_recommendation(
    rec_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    sizer = _get_right_sizer()
    rec = sizer.get_recommendation(rec_id)
    if rec is None:
        raise HTTPException(404, f"Recommendation '{rec_id}' not found")
    return rec.model_dump()


@router.get("/savings")
async def estimate_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    sizer = _get_right_sizer()
    return sizer.estimate_savings()


@router.get("/trends/{resource_id}")
async def analyze_utilization_trends(
    resource_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    sizer = _get_right_sizer()
    return sizer.analyze_utilization_trends(resource_id=resource_id)


@router.get("/summary")
async def generate_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    sizer = _get_right_sizer()
    return sizer.generate_summary()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    sizer = _get_right_sizer()
    return sizer.get_stats()
