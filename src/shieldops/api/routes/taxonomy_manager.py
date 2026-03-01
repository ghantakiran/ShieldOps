"""Taxonomy Manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.taxonomy_manager import (
    TaxonomyLevel,
    TaxonomyQuality,
    TaxonomyStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/taxonomy-manager",
    tags=["Taxonomy Manager"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Taxonomy manager service unavailable")
    return _engine


class RecordTaxonomyRequest(BaseModel):
    taxonomy_id: str
    taxonomy_level: TaxonomyLevel = TaxonomyLevel.DOMAIN
    taxonomy_status: TaxonomyStatus = TaxonomyStatus.DRAFT
    taxonomy_quality: TaxonomyQuality = TaxonomyQuality.ADEQUATE
    completeness_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMappingRequest(BaseModel):
    taxonomy_id: str
    taxonomy_level: TaxonomyLevel = TaxonomyLevel.DOMAIN
    mapping_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/taxonomies")
async def record_taxonomy(
    body: RecordTaxonomyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_taxonomy(**body.model_dump())
    return result.model_dump()


@router.get("/taxonomies")
async def list_taxonomies(
    level: TaxonomyLevel | None = None,
    status: TaxonomyStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_taxonomies(
            level=level,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/taxonomies/{record_id}")
async def get_taxonomy(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_taxonomy(record_id)
    if result is None:
        raise HTTPException(404, f"Taxonomy '{record_id}' not found")
    return result.model_dump()


@router.post("/mappings")
async def add_mapping(
    body: AddMappingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_mapping(**body.model_dump())
    return result.model_dump()


@router.get("/coverage")
async def analyze_taxonomy_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_taxonomy_coverage()


@router.get("/poor-taxonomies")
async def identify_poor_taxonomies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_taxonomies()


@router.get("/completeness-rankings")
async def rank_by_completeness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_completeness()


@router.get("/trends")
async def detect_taxonomy_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_taxonomy_trends()


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


txm_route = router
