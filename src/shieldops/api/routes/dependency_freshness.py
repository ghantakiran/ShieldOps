"""Dependency freshness monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/dependency-freshness", tags=["Dependency Freshness"])

_monitor: Any = None


def set_monitor(monitor: Any) -> None:
    global _monitor
    _monitor = monitor


def _get_monitor() -> Any:
    if _monitor is None:
        raise HTTPException(503, "Dependency freshness service unavailable")
    return _monitor


class RegisterDependencyRequest(BaseModel):
    package_name: str
    current_version: str = ""
    latest_version: str = ""
    ecosystem: str = "PIP"
    service_name: str = ""
    urgency: str = "CURRENT"
    is_direct: bool = True
    has_security_advisory: bool = False


@router.post("/dependencies")
async def register_dependency(
    body: RegisterDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    dep = monitor.register_dependency(**body.model_dump())
    return dep.model_dump()


@router.get("/dependencies")
async def list_dependencies(
    ecosystem: str | None = None,
    urgency: str | None = None,
    service_name: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [
        d.model_dump()
        for d in monitor.list_dependencies(
            ecosystem=ecosystem, urgency=urgency, service_name=service_name, limit=limit
        )
    ]


@router.get("/dependencies/{dep_id}")
async def get_dependency(
    dep_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    dep = monitor.get_dependency(dep_id)
    if dep is None:
        raise HTTPException(404, f"Dependency '{dep_id}' not found")
    return dep.model_dump()


@router.post("/freshness-score/{service_name}")
async def calculate_freshness_score(
    service_name: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    score = monitor.calculate_freshness_score(service_name)
    return score.model_dump()


@router.get("/eol")
async def detect_eol_dependencies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [d.model_dump() for d in monitor.detect_eol_dependencies()]


@router.get("/security-updates")
async def identify_security_updates(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [d.model_dump() for d in monitor.identify_security_updates()]


@router.get("/ranking")
async def rank_services_by_freshness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [s.model_dump() for s in monitor.rank_services_by_freshness()]


@router.get("/ecosystem-health")
async def analyze_ecosystem_health(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return monitor.analyze_ecosystem_health()


@router.get("/report")
async def generate_freshness_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.generate_freshness_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.get_stats()
