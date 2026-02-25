"""Posture trend API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.posture_trend import PostureDomain

logger = structlog.get_logger()
router = APIRouter(
    prefix="/posture-trend",
    tags=["Posture Trend"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Posture trend service unavailable",
        )
    return _engine


class RecordSnapshotRequest(BaseModel):
    domain: PostureDomain
    score: float
    max_score: float = 100.0
    findings_count: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    scan_source: str = ""


@router.post("/snapshots")
async def record_snapshot(
    body: RecordSnapshotRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    snapshot = engine.record_snapshot(**body.model_dump())
    return snapshot.model_dump()


@router.get("/snapshots")
async def list_snapshots(
    domain: PostureDomain | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        s.model_dump()
        for s in engine.list_snapshots(
            domain=domain,
            limit=limit,
        )
    ]


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(
    snapshot_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    snapshot = engine.get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(404, f"Snapshot '{snapshot_id}' not found")
    return snapshot.model_dump()


@router.get("/regression/{domain}")
async def detect_regression(
    domain: PostureDomain,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    regression = engine.detect_regression(domain)
    if regression is not None:
        return regression.model_dump()
    return {"regression": None}


@router.get("/trend/{domain}")
async def compute_trend(
    domain: PostureDomain,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compute_trend(domain)


@router.get("/improvement-velocity")
async def calculate_improvement_velocity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_improvement_velocity()


@router.get("/weakest-domains")
async def identify_weakest_domains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_weakest_domains()


@router.get("/regressions")
async def rank_regressions_by_severity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_regressions_by_severity()


@router.get("/report")
async def generate_trend_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_trend_report()
    return report.model_dump()


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


pt_route = router
