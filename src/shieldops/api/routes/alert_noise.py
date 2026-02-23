"""Alert noise analysis API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-noise",
    tags=["Alert Noise"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Alert noise service unavailable")
    return _analyzer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordAlertRequest(BaseModel):
    alert_name: str
    source: str = "custom"
    service: str = ""
    responder: str = ""
    tags: list[str] = Field(default_factory=list)


class ResolveAlertRequest(BaseModel):
    outcome: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/alerts")
async def record_alert(
    body: RecordAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    record = analyzer.record_alert(
        alert_name=body.alert_name,
        source=body.source,
        service=body.service,
        responder=body.responder,
        tags=body.tags,
    )
    return record.model_dump()


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    body: ResolveAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    record = analyzer.resolve_alert(alert_id, body.outcome)
    if record is None:
        raise HTTPException(404, f"Alert '{alert_id}' not found")
    return record.model_dump()


@router.get("/alerts")
async def list_alerts(
    alert_name: str | None = None,
    source: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    alerts = analyzer.list_alerts(alert_name=alert_name, source=source, outcome=outcome)
    return [a.model_dump() for a in alerts[-limit:]]


@router.post("/analyze")
async def analyze_noise(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    reports = analyzer.analyze_noise()
    return [r.model_dump() for r in reports]


@router.get("/noisy")
async def get_top_noisy(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    reports = analyzer.get_top_noisy_alerts(limit=limit)
    return [r.model_dump() for r in reports]


@router.get("/signal-to-noise")
async def get_signal_to_noise(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return {"signal_to_noise": analyzer.get_signal_to_noise()}


@router.get("/fatigue/{responder}")
async def get_fatigue(
    responder: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_fatigue_score(responder)


@router.post("/clear")
async def clear_records(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    count = analyzer.clear_records()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
