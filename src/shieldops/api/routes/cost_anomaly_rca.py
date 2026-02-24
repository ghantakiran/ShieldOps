"""Cost anomaly root cause analysis API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cost-anomaly-rca", tags=["Cost Anomaly RCA"])

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Cost anomaly RCA service unavailable")
    return _analyzer


class RecordSpikeRequest(BaseModel):
    service_name: str
    resource_id: str = ""
    spike_amount: float = 0.0
    baseline_amount: float = 0.0
    detected_at: float = 0.0


class UpdateSpikeStatusRequest(BaseModel):
    status: str
    root_cause_category: str | None = None


@router.post("/spikes")
async def record_spike(
    body: RecordSpikeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    spike = analyzer.record_spike(**body.model_dump())
    return spike.model_dump()


@router.get("/spikes")
async def list_spikes(
    status: str | None = None,
    service_name: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        s.model_dump()
        for s in analyzer.list_spikes(status=status, service_name=service_name, limit=limit)
    ]


@router.get("/spikes/{spike_id}")
async def get_spike(
    spike_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    spike = analyzer.get_spike(spike_id)
    if spike is None:
        raise HTTPException(404, f"Spike '{spike_id}' not found")
    return spike.model_dump()


@router.post("/analyze/{spike_id}")
async def analyze_root_cause(
    spike_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    finding = analyzer.analyze_root_cause(spike_id)
    return finding.model_dump()


@router.get("/correlate/{spike_id}")
async def correlate_with_changes(
    spike_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.correlate_with_changes(spike_id)


@router.get("/top-offenders")
async def identify_top_offenders(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.identify_top_offenders()


@router.get("/excess-spend")
async def calculate_excess_spend(
    service_name: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.calculate_excess_spend(service_name=service_name)


@router.put("/spikes/{spike_id}/status")
async def update_spike_status(
    spike_id: str,
    body: UpdateSpikeStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    updated = analyzer.update_spike_status(spike_id, **body.model_dump())
    if not updated:
        raise HTTPException(404, f"Spike '{spike_id}' not found")
    return {"updated": True, "spike_id": spike_id}


@router.get("/report")
async def generate_rca_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.generate_rca_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
