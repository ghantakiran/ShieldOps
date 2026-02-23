"""Service latency profiler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/latency-profiler",
    tags=["Latency Profiler"],
)

_profiler: Any = None


def set_profiler(profiler: Any) -> None:
    global _profiler
    _profiler = profiler


def _get_profiler() -> Any:
    if _profiler is None:
        raise HTTPException(503, "Latency profiler service unavailable")
    return _profiler


class RecordSampleRequest(BaseModel):
    service: str
    endpoint: str
    latency_ms: float


class BatchSampleRequest(BaseModel):
    samples: list[RecordSampleRequest]


class ComputeProfileRequest(BaseModel):
    service: str
    endpoint: str
    window: str = "daily"


class BaselineRequest(BaseModel):
    service: str
    endpoint: str


class DetectRegressionsRequest(BaseModel):
    service: str
    endpoint: str


@router.post("/samples")
async def record_sample(
    body: RecordSampleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    profiler = _get_profiler()
    sample = profiler.record_sample(
        service=body.service,
        endpoint=body.endpoint,
        latency_ms=body.latency_ms,
    )
    return sample.model_dump()


@router.post("/samples/batch")
async def record_batch(
    body: BatchSampleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    profiler = _get_profiler()
    count = 0
    for s in body.samples:
        profiler.record_sample(
            service=s.service,
            endpoint=s.endpoint,
            latency_ms=s.latency_ms,
        )
        count += 1
    return {"recorded": count}


@router.post("/compute")
async def compute_profile(
    body: ComputeProfileRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    profiler = _get_profiler()
    profile = profiler.compute_profile(
        service=body.service,
        endpoint=body.endpoint,
        window=body.window,
    )
    return profile.model_dump()


@router.put("/baseline")
async def set_baseline(
    body: BaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    profiler = _get_profiler()
    baseline = profiler.set_baseline(service=body.service, endpoint=body.endpoint)
    if baseline is None:
        raise HTTPException(404, "No profile found; compute a profile first")
    return baseline.model_dump()


@router.get("/baseline")
async def get_baseline(
    service: str,
    endpoint: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    profiler = _get_profiler()
    baseline = profiler.get_baseline(service=service, endpoint=endpoint)
    if baseline is None:
        raise HTTPException(404, "No baseline found")
    return baseline.model_dump()


@router.post("/regressions")
async def detect_regressions(
    body: DetectRegressionsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    profiler = _get_profiler()
    alerts = profiler.detect_regressions(service=body.service, endpoint=body.endpoint)
    return [a.model_dump() for a in alerts]


@router.get("/profiles")
async def list_profiles(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    profiler = _get_profiler()
    profiles = profiler.list_profiles(service=service)
    return [p.model_dump() for p in profiles]


@router.get("/ranking/{service}")
async def get_endpoint_ranking(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    profiler = _get_profiler()
    return profiler.get_endpoint_ranking(service)


@router.delete("/samples")
async def clear_samples(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    profiler = _get_profiler()
    count = profiler.clear_samples()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    profiler = _get_profiler()
    return profiler.get_stats()
