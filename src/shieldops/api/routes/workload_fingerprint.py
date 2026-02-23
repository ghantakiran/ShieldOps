"""Workload fingerprint API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/workload-fingerprints", tags=["Workload Fingerprints"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Workload fingerprint service unavailable")
    return _engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordSampleRequest(BaseModel):
    service: str
    cpu_pct: float = 0.0
    memory_pct: float = 0.0
    request_rate: float = 0.0
    error_rate: float = 0.0
    latency_p99_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SetWorkloadTypeRequest(BaseModel):
    workload_type: str


class ClearSamplesRequest(BaseModel):
    service: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/samples")
async def record_sample(
    body: RecordSampleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    sample = engine.record_sample(**body.model_dump())
    return sample.model_dump()


@router.get("/samples/{service}")
async def get_samples(
    service: str,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [s.model_dump() for s in engine.get_samples(service, limit=limit)]


@router.get("/fingerprints")
async def list_fingerprints(
    status: str | None = None,
    workload_type: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        f.model_dump()
        for f in engine.list_fingerprints(
            status=status,
            workload_type=workload_type,
        )
    ]


@router.get("/fingerprints/{service}")
async def get_fingerprint(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    fp = engine.get_fingerprint(service)
    if fp is None:
        raise HTTPException(404, f"Fingerprint for service '{service}' not found")
    return fp.model_dump()


@router.put("/fingerprints/{service}/type")
async def set_workload_type(
    service: str,
    body: SetWorkloadTypeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    fp = engine.set_workload_type(service, body.workload_type)
    if fp is None:
        raise HTTPException(404, f"Fingerprint for service '{service}' not found")
    return fp.model_dump()


@router.post("/drift/{service}")
async def check_drift(
    service: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [a.model_dump() for a in engine.check_drift(service)]


@router.post("/clear")
async def clear_samples(
    body: ClearSamplesRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    cleared = engine.clear_samples(service=body.service)
    return {"cleared": cleared, "service": body.service}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
