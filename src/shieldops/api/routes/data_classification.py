"""Data Classification Engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.data_classification import (
    ClassificationStatus,
    DataCategory,
    DataSensitivity,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/data-classification", tags=["Data Classification"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Data classification service unavailable")
    return _engine


class RecordClassificationRequest(BaseModel):
    classification_id: str
    data_sensitivity: DataSensitivity = DataSensitivity.UNCLASSIFIED
    classification_status: ClassificationStatus = ClassificationStatus.PENDING
    data_category: DataCategory = DataCategory.OPERATIONAL
    coverage_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    classification_id: str
    data_sensitivity: DataSensitivity = DataSensitivity.UNCLASSIFIED
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_classification(
    body: RecordClassificationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_classification(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_classifications(
    sensitivity: DataSensitivity | None = None,
    status: ClassificationStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_classifications(
            sensitivity=sensitivity,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_classification(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_classification(record_id)
    if result is None:
        raise HTTPException(404, f"Classification record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/coverage")
async def analyze_classification_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_classification_coverage()


@router.get("/unclassified")
async def identify_unclassified_data(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unclassified_data()


@router.get("/sensitivity-rankings")
async def rank_by_sensitivity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_sensitivity()


@router.get("/drift")
async def detect_classification_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_classification_drift()


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


dce_route = router
