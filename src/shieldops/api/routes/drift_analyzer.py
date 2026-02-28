"""Config drift analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.config.drift_analyzer import (
    DriftSeverity,
    DriftSource,
    DriftType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/drift-analyzer",
    tags=["Drift Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Drift analyzer service unavailable",
        )
    return _engine


class RecordDriftRequest(BaseModel):
    config_name: str
    drift_type: DriftType = DriftType.VALUE_CHANGE
    severity: DriftSeverity = DriftSeverity.MODERATE
    source: DriftSource = DriftSource.UNKNOWN
    deviation_pct: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    drift_type: DriftType = DriftType.VALUE_CHANGE
    severity: DriftSeverity = DriftSeverity.MODERATE
    max_deviation_pct: float = 5.0
    auto_remediate: bool = False


@router.post("/drifts")
async def record_drift(
    body: RecordDriftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_drift(**body.model_dump())
    return result.model_dump()


@router.get("/drifts")
async def list_drifts(
    config_name: str | None = None,
    drift_type: DriftType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_drifts(
            config_name=config_name,
            drift_type=drift_type,
            limit=limit,
        )
    ]


@router.get("/drifts/{record_id}")
async def get_drift(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_drift(record_id)
    if result is None:
        raise HTTPException(404, f"Drift '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/status/{config_name}")
async def analyze_drift_status(
    config_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_drift_status(config_name)


@router.get("/critical-drifts")
async def identify_critical_drifts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_drifts()


@router.get("/rankings")
async def rank_by_deviation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_deviation()


@router.get("/drift-patterns")
async def detect_drift_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_drift_patterns()


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


cda_route = router
