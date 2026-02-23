"""Service dependency impact analysis API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/impact-analyzer",
    tags=["Impact Analyzer"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Impact analyzer service unavailable")
    return _analyzer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AddDependencyRequest(BaseModel):
    source_service: str
    target_service: str
    dependency_type: str = "runtime"
    criticality: int = 3


class SimulateFailureRequest(BaseModel):
    failed_service: str
    direction: str = "downstream"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/dependencies")
async def add_dependency(
    body: AddDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    dep = analyzer.add_dependency(
        source_service=body.source_service,
        target_service=body.target_service,
        dependency_type=body.dependency_type,
        criticality=body.criticality,
    )
    return dep.model_dump()


@router.get("/dependencies")
async def list_dependencies(
    service: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    deps = analyzer.list_dependencies(service=service)
    return [d.model_dump() for d in deps[-limit:]]


@router.delete("/dependencies/{dependency_id}")
async def remove_dependency(
    dependency_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    removed = analyzer.remove_dependency(dependency_id)
    if not removed:
        raise HTTPException(404, f"Dependency '{dependency_id}' not found")
    return {"deleted": True, "dependency_id": dependency_id}


@router.post("/simulate")
async def simulate_failure(
    body: SimulateFailureRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    sim = analyzer.simulate_failure(
        failed_service=body.failed_service,
        direction=body.direction,
    )
    return sim.model_dump()


@router.get("/simulations")
async def list_simulations(
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    sims = analyzer.list_simulations(status=status)
    return [s.model_dump() for s in sims[-limit:]]


@router.get("/simulations/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    sim = analyzer.get_simulation(simulation_id)
    if sim is None:
        raise HTTPException(404, f"Simulation '{simulation_id}' not found")
    return sim.model_dump()


@router.get("/paths")
async def get_impact_paths(
    simulation_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    paths = analyzer.get_impact_paths(simulation_id)
    return [p.model_dump() for p in paths]


@router.get("/critical-services")
async def get_critical_services(
    min_dependents: int = 3,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_critical_services(min_dependents=min_dependents)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
