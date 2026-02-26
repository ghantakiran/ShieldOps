"""Team cognitive load tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.cognitive_load import (
    LoadLevel,
    LoadSource,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cognitive-load",
    tags=["Cognitive Load"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cognitive load service unavailable")
    return _engine


class RecordLoadRequest(BaseModel):
    team_name: str
    source: LoadSource = LoadSource.ALERT_VOLUME
    level: LoadLevel = LoadLevel.MODERATE
    load_score: float = 0.0
    details: str = ""


class AddContributorRequest(BaseModel):
    contributor_name: str
    source: LoadSource = LoadSource.ALERT_VOLUME
    level: LoadLevel = LoadLevel.MODERATE
    impact_score: float = 0.0
    description: str = ""


@router.post("/loads")
async def record_load(
    body: RecordLoadRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_load(**body.model_dump())
    return result.model_dump()


@router.get("/loads")
async def list_loads(
    team_name: str | None = None,
    source: LoadSource | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_loads(team_name=team_name, source=source, limit=limit)
    ]


@router.get("/loads/{record_id}")
async def get_load(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_load(record_id)
    if result is None:
        raise HTTPException(404, f"Load record '{record_id}' not found")
    return result.model_dump()


@router.post("/contributors")
async def add_contributor(
    body: AddContributorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_contributor(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{team_name}")
async def analyze_team_load(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_team_load(team_name)


@router.get("/overloaded")
async def identify_overloaded_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overloaded_teams()


@router.get("/rankings")
async def rank_by_load_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_load_score()


@router.get("/trends")
async def detect_load_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_load_trends()


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


clt_route = router
