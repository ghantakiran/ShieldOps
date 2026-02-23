"""API contract testing routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/contract-testing",
    tags=["Contract Testing"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Contract testing service unavailable")
    return _engine


class RegisterSchemaRequest(BaseModel):
    api_name: str
    version: str
    schema_format: str = "openapi_3"
    schema_content: dict[str, Any] = {}


class CheckCompatibilityRequest(BaseModel):
    api_name: str
    from_version: str
    to_version: str


@router.post("/schemas")
async def register_schema(
    body: RegisterSchemaRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    schema = engine.register_schema(
        api_name=body.api_name,
        version=body.version,
        schema_format=body.schema_format,
        schema_content=body.schema_content,
    )
    return schema.model_dump()


@router.get("/schemas")
async def list_schemas(
    api_name: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    schemas = engine.list_versions(api_name) if api_name else list(engine._schemas.values())
    return [s.model_dump() for s in schemas[-limit:]]


@router.get("/schemas/{api_name}/{version}")
async def get_schema_version(
    api_name: str,
    version: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    versions = engine.list_versions(api_name)
    match = [v for v in versions if v.version == version]
    if not match:
        raise HTTPException(404, f"Schema '{api_name}' version '{version}' not found")
    return match[0].model_dump()


@router.get("/schemas/{api_name}/latest")
async def get_latest_version(
    api_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    latest = engine.get_latest_version(api_name)
    if latest is None:
        raise HTTPException(404, f"No schemas found for '{api_name}'")
    return latest.model_dump()


@router.post("/check")
async def check_compatibility(
    body: CheckCompatibilityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    check = engine.check_compatibility(
        api_name=body.api_name,
        from_version=body.from_version,
        to_version=body.to_version,
    )
    return check.model_dump()


@router.get("/drift/{api_name}")
async def get_schema_drift(
    api_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_schema_drift(api_name)


@router.get("/checks")
async def list_checks(
    api_name: str | None = None,
    result: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    checks = engine.list_checks(api_name=api_name, result=result)
    return [c.model_dump() for c in checks[-limit:]]


@router.post("/detect-breaking")
async def detect_breaking_changes(
    body: CheckCompatibilityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    changes = engine.detect_breaking_changes(
        api_name=body.api_name,
        from_version=body.from_version,
        to_version=body.to_version,
    )
    return [c.model_dump() for c in changes]


@router.delete("/schemas/{schema_id}")
async def delete_schema(
    schema_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    deleted = engine.delete_schema(schema_id)
    if not deleted:
        raise HTTPException(404, f"Schema '{schema_id}' not found")
    return {"deleted": True, "schema_id": schema_id}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
