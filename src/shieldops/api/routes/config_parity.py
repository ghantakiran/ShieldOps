"""Configuration parity validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/config-parity",
    tags=["Config Parity"],
)

_validator: Any = None


def set_validator(validator: Any) -> None:
    global _validator
    _validator = validator


def _get_validator() -> Any:
    if _validator is None:
        raise HTTPException(503, "Config parity service unavailable")
    return _validator


class CaptureConfigRequest(BaseModel):
    environment: str
    role: str = "development"
    service: str = ""
    config_data: dict[str, Any] = {}


class CompareRequest(BaseModel):
    env_a: str
    env_b: str
    service: str = ""


class CompareAllRequest(BaseModel):
    service: str = ""


@router.post("/configs")
async def capture_config(
    body: CaptureConfigRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    config = validator.capture_config(
        environment=body.environment,
        role=body.role,
        service=body.service,
        config_data=body.config_data,
    )
    return config.model_dump()


@router.get("/configs")
async def list_configs(
    environment: str | None = None,
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    configs = validator.list_configs(environment=environment, service=service)
    return [c.model_dump() for c in configs[-limit:]]


@router.get("/configs/{config_id}")
async def get_config(
    config_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    config = validator.get_config(config_id)
    if config is None:
        raise HTTPException(404, f"Config '{config_id}' not found")
    return config.model_dump()


@router.post("/compare")
async def compare_environments(
    body: CompareRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    report = validator.compare_environments(
        env_a=body.env_a,
        env_b=body.env_b,
        service=body.service,
    )
    return report.model_dump()


@router.post("/compare-all")
async def compare_all(
    body: CompareAllRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    reports = validator.compare_all_environments(service=body.service)
    return [r.model_dump() for r in reports]


@router.get("/violations")
async def list_violations(
    env_a: str | None = None,
    violation_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    violations = validator.list_violations(env_a=env_a, violation_type=violation_type)
    return [v.model_dump() for v in violations[-limit:]]


@router.get("/score/{env_a}/{env_b}")
async def get_parity_score(
    env_a: str,
    env_b: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    score = validator.get_parity_score(env_a, env_b)
    return {"env_a": env_a, "env_b": env_b, "score": score}


@router.get("/critical")
async def get_critical_divergences(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    critical = validator.get_critical_divergences()
    return [v.model_dump() for v in critical]


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    deleted = validator.delete_config(config_id)
    if not deleted:
        raise HTTPException(404, f"Config '{config_id}' not found")
    return {"deleted": True, "config_id": config_id}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    return validator.get_stats()
