"""Agent performance benchmark API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/agent-benchmarks", tags=["Agent Benchmarks"])

_benchmarker: Any = None


def set_benchmarker(benchmarker: Any) -> None:
    global _benchmarker
    _benchmarker = benchmarker


def _get_benchmarker() -> Any:
    if _benchmarker is None:
        raise HTTPException(503, "Agent benchmark service unavailable")
    return _benchmarker


class RecordExecutionRequest(BaseModel):
    agent_type: str
    duration_seconds: float = 0.0
    success: bool = True
    confidence: float = 0.0
    token_usage: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/record")
async def record_execution(
    body: RecordExecutionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    bm = _get_benchmarker()
    result = bm.record_execution(**body.model_dump())
    return result.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    bm = _get_benchmarker()
    return bm.get_stats()


@router.get("")
async def list_benchmarks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    bm = _get_benchmarker()
    return bm.list_benchmarks()


@router.get("/{agent_type}")
async def get_benchmark(
    agent_type: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    bm = _get_benchmarker()
    return bm.get_benchmark(agent_type)


@router.get("/{agent_type}/regressions")
async def get_regressions(
    agent_type: str,
    window_size: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    bm = _get_benchmarker()
    return [r.model_dump() for r in bm.detect_regressions(agent_type, window_size)]


@router.post("/{agent_type}/baseline")
async def compute_baseline(
    agent_type: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    bm = _get_benchmarker()
    baseline = bm.compute_baseline(agent_type)
    return baseline.model_dump()
