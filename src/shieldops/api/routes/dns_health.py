"""DNS health monitoring API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/dns-health", tags=["DNS Health"])

_monitor: Any = None


def set_monitor(inst: Any) -> None:
    global _monitor
    _monitor = inst


def _get_monitor() -> Any:
    if _monitor is None:
        raise HTTPException(503, "DNS health service unavailable")
    return _monitor


class RecordCheckRequest(BaseModel):
    domain: str
    record_type: str = "A"
    resolver: str = ""
    response_time_ms: float = 0.0
    ttl: int = 3600


class PropagationRequest(BaseModel):
    domain: str
    record_type: str = "A"
    expected_value: str = ""
    resolvers_checked: int = 0
    resolvers_consistent: int = 0


@router.post("/checks")
async def record_check(
    body: RecordCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    check = monitor.record_check(**body.model_dump())
    return check.model_dump()


@router.get("/checks")
async def list_checks(
    domain: str | None = None,
    record_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [
        c.model_dump()
        for c in monitor.list_checks(domain=domain, record_type=record_type, limit=limit)
    ]


@router.get("/checks/{check_id}")
async def get_check(
    check_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    check = monitor.get_check(check_id)
    if check is None:
        raise HTTPException(404, f"Check '{check_id}' not found")
    return check.model_dump()


@router.post("/propagation")
async def check_propagation(
    body: PropagationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    result = monitor.check_propagation(**body.model_dump())
    return result.model_dump()


@router.get("/failures")
async def detect_failures(
    domain: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [f.model_dump() for f in monitor.detect_failures(domain=domain)]


@router.get("/latency")
async def measure_resolution_latency(
    domain: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.measure_resolution_latency(domain=domain)


@router.get("/zone-report/{zone}")
async def generate_zone_report(
    zone: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.generate_zone_report(zone=zone)


@router.get("/propagation")
async def list_propagation_checks(
    domain: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [p.model_dump() for p in monitor.list_propagation_checks(domain=domain, limit=limit)]


@router.get("/ttl-anomalies")
async def detect_ttl_anomalies(
    min_ttl: int = 60,
    max_ttl: int = 86400,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [a.model_dump() for a in monitor.detect_ttl_anomalies(min_ttl=min_ttl, max_ttl=max_ttl)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.get_stats()
