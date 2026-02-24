"""Failure mode catalog API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/failure-mode-catalog", tags=["Failure Mode Catalog"])

_catalog: Any = None


def set_catalog(catalog: Any) -> None:
    global _catalog
    _catalog = catalog


def _get_catalog() -> Any:
    if _catalog is None:
        raise HTTPException(503, "Failure mode catalog service unavailable")
    return _catalog


class RegisterFailureModeRequest(BaseModel):
    service_name: str
    name: str
    severity: str = "MINOR"
    detection_method: str = "AUTOMATED_ALERT"
    mitigation_strategy: str = "RETRY"
    description: str = ""
    is_mitigated: bool = False


class RecordOccurrenceRequest(BaseModel):
    detected_at: float = 0.0
    resolved_at: float = 0.0
    notes: str = ""


@router.post("/modes")
async def register_failure_mode(
    body: RegisterFailureModeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    catalog = _get_catalog()
    mode = catalog.register_failure_mode(**body.model_dump())
    return mode.model_dump()


@router.get("/modes")
async def list_failure_modes(
    severity: str | None = None,
    service_name: str | None = None,
    detection_method: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    catalog = _get_catalog()
    return [
        m.model_dump()
        for m in catalog.list_failure_modes(
            severity=severity,
            service_name=service_name,
            detection_method=detection_method,
            limit=limit,
        )
    ]


@router.get("/modes/{mode_id}")
async def get_failure_mode(
    mode_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    catalog = _get_catalog()
    mode = catalog.get_failure_mode(mode_id)
    if mode is None:
        raise HTTPException(404, f"Failure mode '{mode_id}' not found")
    return mode.model_dump()


@router.post("/modes/{mode_id}/occurrences")
async def record_occurrence(
    mode_id: str,
    body: RecordOccurrenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    catalog = _get_catalog()
    occurrence = catalog.record_occurrence(failure_mode_id=mode_id, **body.model_dump())
    if occurrence is None:
        raise HTTPException(404, f"Failure mode '{mode_id}' not found")
    return occurrence.model_dump()


@router.get("/modes/{mode_id}/mtbf")
async def calculate_mtbf(
    mode_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    catalog = _get_catalog()
    return catalog.calculate_mtbf(mode_id)


@router.get("/ranking")
async def rank_by_frequency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    catalog = _get_catalog()
    return [m.model_dump() for m in catalog.rank_by_frequency()]


@router.get("/unmitigated")
async def identify_unmitigated_modes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    catalog = _get_catalog()
    return [m.model_dump() for m in catalog.identify_unmitigated_modes()]


@router.get("/detection-coverage")
async def analyze_detection_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    catalog = _get_catalog()
    return catalog.analyze_detection_coverage()


@router.get("/report")
async def generate_catalog_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    catalog = _get_catalog()
    return catalog.generate_catalog_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    catalog = _get_catalog()
    return catalog.get_stats()
