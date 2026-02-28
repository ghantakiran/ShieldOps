"""Prompt cache manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.prompt_cache import (
    CacheOutcome,
    CacheStrategy,
    EvictionPolicy,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/prompt-cache",
    tags=["Prompt Cache"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Prompt cache service unavailable")
    return _engine


class RecordEntryRequest(BaseModel):
    cache_key: str
    cache_strategy: CacheStrategy = CacheStrategy.EXACT_MATCH
    cache_outcome: CacheOutcome = CacheOutcome.MISS
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    entry_size_bytes: int = 0
    details: str = ""


class AddEventRequest(BaseModel):
    event_label: str
    cache_strategy: CacheStrategy = CacheStrategy.EXACT_MATCH
    cache_outcome: CacheOutcome = CacheOutcome.HIT
    latency_ms: float = 0.0


@router.post("/records")
async def record_entry(
    body: RecordEntryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_entry(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_entries(
    cache_key: str | None = None,
    cache_strategy: CacheStrategy | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_entries(
            cache_key=cache_key, cache_strategy=cache_strategy, limit=limit
        )
    ]


@router.get("/records/{record_id}")
async def get_entry(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_entry(record_id)
    if result is None:
        raise HTTPException(404, f"Cache entry '{record_id}' not found")
    return result.model_dump()


@router.post("/events")
async def add_event(
    body: AddEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_event(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{cache_key}")
async def analyze_cache_performance(
    cache_key: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_cache_performance(cache_key)


@router.get("/identify")
async def identify_low_hit_keys(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_hit_keys()


@router.get("/rankings")
async def rank_by_hit_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_hit_rate()


@router.get("/detect")
async def detect_cache_thrashing(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_cache_thrashing()


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


pcm_route = router
