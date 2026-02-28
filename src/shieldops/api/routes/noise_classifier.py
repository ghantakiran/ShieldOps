"""Alert Noise Classifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.noise_classifier import (
    ClassificationMethod,
    NoiseCategory,
    SignalStrength,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/noise-classifier",
    tags=["Noise Classifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Alert noise classifier service unavailable",
        )
    return _engine


class RecordNoiseRequest(BaseModel):
    alert_name: str
    source: str = ""
    category: NoiseCategory = NoiseCategory.INFORMATIONAL
    signal_strength: SignalStrength = SignalStrength.UNKNOWN
    method: ClassificationMethod = ClassificationMethod.RULE_BASED
    noise_score: float = 0.0
    suppressed: bool = False
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    category: NoiseCategory = NoiseCategory.INFORMATIONAL
    method: ClassificationMethod = ClassificationMethod.RULE_BASED
    pattern: str = ""
    threshold: float = 0.5
    enabled: bool = True
    description: str = ""


@router.post("/records")
async def record_noise(
    body: RecordNoiseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_noise(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_noises(
    category: NoiseCategory | None = None,
    signal_strength: SignalStrength | None = None,
    method: ClassificationMethod | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_noises(
            category=category,
            signal_strength=signal_strength,
            method=method,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_noise(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_noise(record_id)
    if record is None:
        raise HTTPException(404, f"Noise record '{record_id}' not found")
    return record.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.add_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/by-source")
async def analyze_noise_by_source(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_noise_by_source()


@router.get("/noisy-alerts")
async def identify_noisy_alerts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_noisy_alerts()


@router.get("/rank-by-ratio")
async def rank_by_noise_ratio(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_noise_ratio()


@router.get("/trends")
async def detect_noise_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_noise_trends()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_report()
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


anc_route = router
