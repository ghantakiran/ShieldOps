"""API routes for LLM usage and cost tracking."""

from typing import Any

from fastapi import APIRouter, HTTPException

from shieldops.utils.llm_router import LLMRouter

router = APIRouter()

_router_instance: LLMRouter | None = None


def set_llm_router(llm_router: LLMRouter) -> None:
    global _router_instance
    _router_instance = llm_router


def _get_router() -> LLMRouter:
    if _router_instance is None:
        raise HTTPException(status_code=503, detail="LLM router not initialized")
    return _router_instance


@router.get("/llm/usage")
async def llm_usage_stats() -> dict[str, Any]:
    llm_router = _get_router()
    stats = llm_router.get_usage_stats()
    return stats.model_dump()


@router.get("/llm/cost-breakdown")
async def llm_cost_breakdown(agent_type: str | None = None) -> dict[str, Any]:
    llm_router = _get_router()
    return llm_router.get_cost_breakdown(agent_type=agent_type)
