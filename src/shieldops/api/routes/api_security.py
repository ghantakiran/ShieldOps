"""API security monitor routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/api-security",
    tags=["API Security"],
)

_monitor: Any = None


def set_monitor(monitor: Any) -> None:
    global _monitor
    _monitor = monitor


def _get_monitor() -> Any:
    if _monitor is None:
        raise HTTPException(503, "API security service unavailable")
    return _monitor


class RegisterEndpointRequest(BaseModel):
    path: str
    method: str = "GET"
    service: str = ""
    monitoring_mode: str = "passive"


class ReportRequestBody(BaseModel):
    endpoint_id: str
    source_ip: str = ""
    suspicious: bool = False
    metadata: dict[str, Any] | None = None


@router.post("/endpoints")
async def register_endpoint(
    body: RegisterEndpointRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    ep = monitor.register_endpoint(
        path=body.path,
        method=body.method,
        service=body.service,
        monitoring_mode=body.monitoring_mode,
    )
    return ep.model_dump()


@router.get("/endpoints")
async def list_endpoints(
    service: str | None = None,
    risk_level: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    endpoints = monitor.list_endpoints(service=service, risk_level=risk_level, limit=limit)
    return [ep.model_dump() for ep in endpoints]


@router.get("/endpoints/{endpoint_id}")
async def get_endpoint(
    endpoint_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    ep = monitor.get_endpoint(endpoint_id)
    if ep is None:
        raise HTTPException(404, f"Endpoint '{endpoint_id}' not found")
    return ep.model_dump()


@router.post("/requests")
async def report_request(
    body: ReportRequestBody,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.report_request(
        endpoint_id=body.endpoint_id,
        source_ip=body.source_ip,
        suspicious=body.suspicious,
        metadata=body.metadata,
    )


@router.post("/detect")
async def detect_threats(
    endpoint_id: str | None = None,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    alerts = monitor.detect_threats(endpoint_id=endpoint_id)
    return [a.model_dump() for a in alerts]


@router.get("/alerts")
async def get_alerts(
    endpoint_id: str | None = None,
    threat_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    alerts = monitor.get_alerts(endpoint_id=endpoint_id, threat_type=threat_type, limit=limit)
    return [a.model_dump() for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    if not monitor.acknowledge_alert(alert_id):
        raise HTTPException(404, f"Alert '{alert_id}' not found")
    return {"acknowledged": True}


@router.get("/risk/{endpoint_id}")
async def get_risk_score(
    endpoint_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    score = monitor.get_risk_score(endpoint_id)
    if score is None:
        raise HTTPException(404, f"Endpoint '{endpoint_id}' not found")
    return score


@router.get("/top-threats")
async def get_top_threats(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return monitor.get_top_threats(limit=limit)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.get_stats()
