"""Batch/bulk operations API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from shieldops.api.auth.dependencies import require_role
from shieldops.api.batch_engine import BatchConfig

logger = structlog.get_logger()
router = APIRouter(prefix="/batch", tags=["Batch Operations"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Batch service unavailable")
    return _engine


@router.post("", status_code=202)
async def submit_batch(
    config: BatchConfig,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> JSONResponse:
    eng = _get_engine()
    result = await eng.execute(config)
    return JSONResponse(status_code=202, content=result.model_dump())


@router.post("/validate")
async def validate_batch(
    config: BatchConfig,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    errors = await eng.validate(config)
    return {"valid": len(errors) == 0, "errors": errors}


@router.get("/{job_id}")
async def get_batch_job(
    job_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    job = eng.get_job(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return job.model_dump()


@router.get("")
async def list_batch_jobs(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return [j.model_dump() for j in eng.list_jobs(limit)]


@router.delete("/{job_id}")
async def delete_batch_job(
    job_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, str]:
    eng = _get_engine()
    if not eng.delete_job(job_id):
        raise HTTPException(404, f"Job '{job_id}' not found")
    return {"deleted": job_id}
