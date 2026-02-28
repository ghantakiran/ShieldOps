"""Runbook chainer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_chainer import (
    ChainMode,
    ChainStatus,
    TransitionType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-chainer",
    tags=["Runbook Chainer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Runbook chainer service unavailable")
    return _engine


class RecordChainRequest(BaseModel):
    chain_name: str
    chain_mode: ChainMode = ChainMode.SEQUENTIAL
    chain_status: ChainStatus = ChainStatus.PENDING
    transition_type: TransitionType = TransitionType.SUCCESS
    runbook_count: int = 0
    details: str = ""


class AddLinkRequest(BaseModel):
    link_name: str
    chain_mode: ChainMode = ChainMode.SEQUENTIAL
    chain_status: ChainStatus = ChainStatus.EXECUTING
    execution_time_seconds: float = 0.0


@router.post("/chains")
async def record_chain(
    body: RecordChainRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_chain(**body.model_dump())
    return result.model_dump()


@router.get("/chains")
async def list_chains(
    chain_name: str | None = None,
    chain_status: ChainStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_chains(chain_name=chain_name, chain_status=chain_status, limit=limit)
    ]


@router.get("/chains/{record_id}")
async def get_chain(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_chain(record_id)
    if result is None:
        raise HTTPException(404, f"Chain record '{record_id}' not found")
    return result.model_dump()


@router.post("/links")
async def add_link(
    body: AddLinkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_link(**body.model_dump())
    return result.model_dump()


@router.get("/chain-efficiency/{chain_name}")
async def analyze_chain_efficiency(
    chain_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_chain_efficiency(chain_name)


@router.get("/broken-chains")
async def identify_broken_chains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_broken_chains()


@router.get("/rankings")
async def rank_by_execution_speed(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_execution_speed()


@router.get("/loops")
async def detect_chain_loops(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_chain_loops()


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


rce_route = router
