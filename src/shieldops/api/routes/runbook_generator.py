"""Runbook generator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_generator import (
    RunbookQuality,
    RunbookScope,
    RunbookSource,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-generator",
    tags=["Runbook Generator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Runbook generator service unavailable",
        )
    return _engine


class RecordRunbookRequest(BaseModel):
    runbook_name: str
    source: RunbookSource = RunbookSource.INCIDENT_PATTERN
    quality: RunbookQuality = RunbookQuality.DRAFT
    scope: RunbookScope = RunbookScope.SERVICE_SPECIFIC
    accuracy_score: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    source: RunbookSource = RunbookSource.INCIDENT_PATTERN
    scope: RunbookScope = RunbookScope.SERVICE_SPECIFIC
    min_incidents: int = 3
    auto_generate: bool = True


@router.post("/runbooks")
async def record_runbook(
    body: RecordRunbookRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_runbook(**body.model_dump())
    return result.model_dump()


@router.get("/runbooks")
async def list_runbooks(
    runbook_name: str | None = None,
    source: RunbookSource | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_runbooks(
            runbook_name=runbook_name,
            source=source,
            limit=limit,
        )
    ]


@router.get("/runbooks/{record_id}")
async def get_runbook(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_runbook(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Runbook '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/quality/{runbook_name}")
async def analyze_runbook_quality(
    runbook_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_runbook_quality(runbook_name)


@router.get("/obsolete")
async def identify_obsolete_runbooks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_obsolete_runbooks()


@router.get("/rankings")
async def rank_by_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_accuracy()


@router.get("/quality-gaps")
async def detect_quality_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_quality_gaps()


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


org_route = router
