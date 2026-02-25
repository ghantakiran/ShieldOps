"""SLA Cascader API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.sla_cascader import (
    CascadeImpact,
    DependencyRelation,
    PropagationMode,
)

logger = structlog.get_logger()
sc_route = APIRouter(
    prefix="/sla-cascader",
    tags=["SLA Cascader"],
)

_cascader: Any = None


def set_cascader(cascader: Any) -> None:
    global _cascader
    _cascader = cascader


def _get_cascader() -> Any:
    if _cascader is None:
        raise HTTPException(503, "SLA cascader unavailable")
    return _cascader


class RecordDependencyRequest(BaseModel):
    upstream_service: str
    downstream_service: str
    upstream_sla_pct: float
    downstream_sla_pct: float
    relation: DependencyRelation = DependencyRelation.HARD
    propagation: PropagationMode = PropagationMode.SERIAL


class ComputeSlaRequest(BaseModel):
    upstream_sla_pct: float
    downstream_sla_pct: float
    relation: DependencyRelation


class SimulateDegradationRequest(BaseModel):
    service: str
    degraded_sla_pct: float


@sc_route.post("/records")
async def record_dependency(
    body: RecordDependencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    cascader = _get_cascader()
    record = cascader.record_dependency(**body.model_dump())
    return record.model_dump()  # type: ignore[no-any-return]


@sc_route.get("/records")
async def list_records(
    upstream_service: str | None = None,
    impact: CascadeImpact | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    cascader = _get_cascader()
    return [  # type: ignore[no-any-return]
        r.model_dump()
        for r in cascader.list_records(
            upstream_service=upstream_service,
            impact=impact,
            limit=limit,
        )
    ]


@sc_route.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    cascader = _get_cascader()
    record = cascader.get_record(record_id)
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found")
    return record.model_dump()  # type: ignore[no-any-return]


@sc_route.post("/compute-sla")
async def compute_effective_sla(
    body: ComputeSlaRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    cascader = _get_cascader()
    return cascader.compute_effective_sla(  # type: ignore[no-any-return]
        body.upstream_sla_pct,
        body.downstream_sla_pct,
        body.relation,
    )


@sc_route.get("/cascade-paths/{source_service}")
async def trace_cascade_paths(
    source_service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    cascader = _get_cascader()
    paths = cascader.trace_cascade_paths(source_service)
    return [p.model_dump() for p in paths]  # type: ignore[no-any-return]


@sc_route.get("/weakest-links")
async def identify_weakest_links(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    cascader = _get_cascader()
    return cascader.identify_weakest_links()  # type: ignore[no-any-return]


@sc_route.post("/simulate")
async def simulate_degradation(
    body: SimulateDegradationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    cascader = _get_cascader()
    return cascader.simulate_degradation(  # type: ignore[no-any-return]
        body.service,
        body.degraded_sla_pct,
    )


@sc_route.get("/rank")
async def rank_by_cascade_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    cascader = _get_cascader()
    return cascader.rank_by_cascade_risk()  # type: ignore[no-any-return]


@sc_route.get("/report")
async def generate_cascade_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    cascader = _get_cascader()
    return cascader.generate_cascade_report().model_dump()  # type: ignore[no-any-return]


@sc_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    cascader = _get_cascader()
    return cascader.get_stats()  # type: ignore[no-any-return]


@sc_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    cascader = _get_cascader()
    cascader.clear_data()
    return {"status": "cleared"}
