"""Network flow API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/network-flow",
    tags=["Network Flow"],
)

_instance: Any = None


def set_analyzer(instance: Any) -> None:
    global _instance
    _instance = instance


def _get_analyzer() -> Any:
    if _instance is None:
        raise HTTPException(503, "Network flow service unavailable")
    return _instance


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordFlowRequest(BaseModel):
    source_ip: str
    dest_ip: str
    source_port: int = 0
    dest_port: int = 0
    protocol: str = "tcp"
    direction: str = "inbound"
    bytes_transferred: int = 0
    packets: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/flows")
async def record_flow(
    body: RecordFlowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    result = analyzer.record_flow(
        source_ip=body.source_ip,
        dest_ip=body.dest_ip,
        source_port=body.source_port,
        dest_port=body.dest_port,
        protocol=body.protocol,
        direction=body.direction,
        bytes_transferred=body.bytes_transferred,
        packets=body.packets,
    )
    return result.model_dump()


@router.get("/flows")
async def list_flows(
    direction: str | None = None,
    anomaly: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        f.model_dump()
        for f in analyzer.list_flows(
            direction=direction,
            anomaly=anomaly,
            limit=limit,
        )
    ]


@router.get("/flows/{flow_id}")
async def get_flow(
    flow_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    result = analyzer.get_flow(flow_id)
    if result is None:
        raise HTTPException(404, f"Flow '{flow_id}' not found")
    return result.model_dump()


@router.get("/anomalies")
async def detect_anomalies(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [f.model_dump() for f in analyzer.detect_anomalies(limit=limit)]


@router.get("/top-talkers")
async def get_top_talkers(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_top_talkers(limit=limit)


@router.get("/firewall-recommendations")
async def generate_firewall_recommendations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [r.model_dump() for r in analyzer.generate_firewall_recommendations()]


@router.get("/traffic-patterns")
async def analyze_traffic_patterns(
    source_ip: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.analyze_traffic_patterns(source_ip=source_ip)


@router.get("/data-exfiltration")
async def detect_data_exfiltration(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [f.model_dump() for f in analyzer.detect_data_exfiltration()]


@router.get("/summary")
async def generate_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.generate_summary().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
