"""Data export engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import require_role
from shieldops.utils.export_engine import ExportConfig

logger = structlog.get_logger()
router = APIRouter(prefix="/exports", tags=["Exports"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Export service unavailable")
    return _engine


class GenerateExportRequest(ExportConfig):
    data: list[dict[str, Any]] = []


@router.post("/generate")
async def generate_export(
    body: GenerateExportRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    config = ExportConfig(
        format=body.format,
        title=body.title,
        entity_type=body.entity_type,
        filters=body.filters,
        columns=body.columns,
        include_summary=body.include_summary,
        max_rows=body.max_rows,
    )
    result = eng.generate(body.data, config)
    return result.model_dump()


@router.get("/formats")
async def list_export_formats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    return {"formats": eng.supported_formats()}


@router.get("/{export_id}")
async def get_export(
    export_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    result = eng.get_export(export_id)
    if result is None:
        raise HTTPException(404, f"Export '{export_id}' not found")
    return result.model_dump()


@router.get("")
async def list_exports(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return [e.model_dump() for e in eng.list_exports(limit)]
