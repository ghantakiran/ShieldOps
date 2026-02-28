"""Token optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.token_optimizer import (
    CostTier,
    OptimizationStrategy,
    TokenSavingsLevel,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/token-optimizer",
    tags=["Token Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Token optimizer service unavailable")
    return _engine


class RecordUsageRequest(BaseModel):
    agent_name: str
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.PROMPT_COMPRESSION
    savings_level: TokenSavingsLevel = TokenSavingsLevel.MODERATE
    cost_tier: CostTier = CostTier.STANDARD
    tokens_saved: int = 0
    details: str = ""


class AddResultRequest(BaseModel):
    result_label: str
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.PROMPT_COMPRESSION
    savings_level: TokenSavingsLevel = TokenSavingsLevel.GOOD
    savings_pct: float = 0.0


@router.post("/records")
async def record_usage(
    body: RecordUsageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_usage(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_usages(
    agent_name: str | None = None,
    optimization_strategy: OptimizationStrategy | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_usages(
            agent_name=agent_name,
            optimization_strategy=optimization_strategy,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_usage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_usage(record_id)
    if result is None:
        raise HTTPException(404, f"Usage record '{record_id}' not found")
    return result.model_dump()


@router.post("/results")
async def add_result(
    body: AddResultRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_result(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{agent_name}")
async def analyze_agent_savings(
    agent_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_agent_savings(agent_name)


@router.get("/identify")
async def identify_low_savings_agents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_savings_agents()


@router.get("/rankings")
async def rank_by_tokens_saved(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_tokens_saved()


@router.get("/detect")
async def detect_savings_regression(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_savings_regression()


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


ato_route = router
