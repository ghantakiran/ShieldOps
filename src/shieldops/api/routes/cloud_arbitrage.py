"""Cloud cost arbitrage analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cloud_arbitrage import (
    CloudProvider,
    WorkloadType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cloud-arbitrage",
    tags=["Cloud Arbitrage"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cloud arbitrage service unavailable")
    return _engine


class RecordArbitrageRequest(BaseModel):
    service_name: str
    current_provider: CloudProvider = CloudProvider.AWS
    workload_type: WorkloadType = WorkloadType.COMPUTE
    savings_pct: float = 0.0
    details: str = ""


class AddOpportunityRequest(BaseModel):
    opportunity_name: str
    target_provider: CloudProvider = CloudProvider.GCP
    workload_type: WorkloadType = WorkloadType.COMPUTE
    estimated_savings_usd: float = 0.0
    description: str = ""


@router.post("/arbitrages")
async def record_arbitrage(
    body: RecordArbitrageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_arbitrage(**body.model_dump())
    return result.model_dump()


@router.get("/arbitrages")
async def list_arbitrages(
    service_name: str | None = None,
    current_provider: CloudProvider | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_arbitrages(
            service_name=service_name,
            current_provider=current_provider,
            limit=limit,
        )
    ]


@router.get("/arbitrages/{record_id}")
async def get_arbitrage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_arbitrage(record_id)
    if result is None:
        raise HTTPException(404, f"Arbitrage record '{record_id}' not found")
    return result.model_dump()


@router.post("/opportunities")
async def add_opportunity(
    body: AddOpportunityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_opportunity(**body.model_dump())
    return result.model_dump()


@router.get("/savings-analysis/{service_name}")
async def analyze_savings_potential(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_savings_potential(service_name)


@router.get("/high-savings-services")
async def identify_high_savings_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_savings_services()


@router.get("/rankings")
async def rank_by_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_savings()


@router.get("/trends")
async def detect_arbitrage_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_arbitrage_trends()


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


car_route = router
