"""LLM token cost tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.llm_cost_tracker import (
    LLMProvider,
    TokenCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/llm-cost-tracker",
    tags=["LLM Cost Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "LLM cost tracker service unavailable")
    return _engine


class RecordCostRequest(BaseModel):
    agent_name: str
    provider: LLMProvider = LLMProvider.ANTHROPIC
    category: TokenCategory = TokenCategory.INPUT
    token_count: int = 0
    cost_usd: float = 0.0
    details: str = ""


class AddBreakdownRequest(BaseModel):
    provider_name: str
    provider: LLMProvider = LLMProvider.ANTHROPIC
    category: TokenCategory = TokenCategory.INPUT
    total_tokens: int = 0
    description: str = ""


@router.post("/costs")
async def record_cost(
    body: RecordCostRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_cost(**body.model_dump())
    return result.model_dump()


@router.get("/costs")
async def list_costs(
    agent_name: str | None = None,
    provider: LLMProvider | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_costs(
            agent_name=agent_name,
            provider=provider,
            limit=limit,
        )
    ]


@router.get("/costs/{record_id}")
async def get_cost(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_cost(record_id)
    if result is None:
        raise HTTPException(404, f"Cost record '{record_id}' not found")
    return result.model_dump()


@router.post("/breakdowns")
async def add_breakdown(
    body: AddBreakdownRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_breakdown(**body.model_dump())
    return result.model_dump()


@router.get("/agent-analysis/{agent_name}")
async def analyze_agent_costs(
    agent_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_agent_costs(agent_name)


@router.get("/high-cost-agents")
async def identify_high_cost_agents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_cost_agents()


@router.get("/rankings")
async def rank_by_total_cost(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_total_cost()


@router.get("/trends")
async def detect_cost_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_cost_trends()


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


lct_route = router
