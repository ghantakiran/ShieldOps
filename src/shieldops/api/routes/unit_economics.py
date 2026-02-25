"""Unit Economics API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.unit_economics import UnitType

logger = structlog.get_logger()
ue_route = APIRouter(
    prefix="/unit-economics",
    tags=["Unit Economics"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Unit economics engine unavailable")
    return _engine


class RecordUnitCostRequest(BaseModel):
    service_name: str
    unit_type: UnitType
    total_cost: float
    total_units: int
    team: str = ""
    period: str = ""


class ComputeCostRequest(BaseModel):
    total_cost: float
    total_units: int


@ue_route.post("/records")
async def record_unit_cost(
    body: RecordUnitCostRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_unit_cost(**body.model_dump())
    return record.model_dump()  # type: ignore[no-any-return]


@ue_route.get("/records")
async def list_records(
    service_name: str | None = None,
    unit_type: UnitType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [  # type: ignore[no-any-return]
        r.model_dump()
        for r in engine.list_records(
            service_name=service_name,
            unit_type=unit_type,
            limit=limit,
        )
    ]


@ue_route.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_record(record_id)
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found")
    return record.model_dump()  # type: ignore[no-any-return]


@ue_route.post("/compute")
async def compute_cost_per_unit(
    body: ComputeCostRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compute_cost_per_unit(  # type: ignore[no-any-return]
        body.total_cost,
        body.total_units,
    )


@ue_route.get("/benchmarks/{service_name}")
async def create_benchmark(
    service_name: str,
    unit_type: UnitType | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    kwargs: dict[str, Any] = {"service_name": service_name}
    if unit_type is not None:
        kwargs["unit_type"] = unit_type
    benchmark = engine.create_benchmark(**kwargs)
    return benchmark.model_dump()  # type: ignore[no-any-return]


@ue_route.get("/expensive-services")
async def identify_expensive_services(
    threshold: float | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_expensive_services(  # type: ignore[no-any-return]
        threshold=threshold,
    )


@ue_route.get("/trend/{service_name}")
async def compute_efficiency_trend(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compute_efficiency_trend(  # type: ignore[no-any-return]
        service_name,
    )


@ue_route.get("/rank")
async def rank_by_cost_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cost_efficiency()  # type: ignore[no-any-return]


@ue_route.get("/report")
async def generate_economics_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_economics_report().model_dump()  # type: ignore[no-any-return]


@ue_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()  # type: ignore[no-any-return]


@ue_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    engine.clear_data()
    return {"status": "cleared"}
