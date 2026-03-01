"""Invoice Validation Engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.invoice_validator import (
    DiscrepancyType,
    InvoiceCategory,
    ValidationStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/invoice-validator", tags=["Invoice Validator"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Invoice validator service unavailable")
    return _engine


class RecordInvoiceRequest(BaseModel):
    invoice_id: str
    discrepancy_type: DiscrepancyType = DiscrepancyType.OVERCHARGE
    validation_status: ValidationStatus = ValidationStatus.PENDING_REVIEW
    invoice_category: InvoiceCategory = InvoiceCategory.COMPUTE
    discrepancy_amount: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddDiscrepancyRequest(BaseModel):
    detail_name: str
    discrepancy_type: DiscrepancyType = DiscrepancyType.OVERCHARGE
    amount_threshold: float = 0.0
    avg_discrepancy_amount: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_invoice(
    body: RecordInvoiceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_invoice(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_invoices(
    dtype: DiscrepancyType | None = None,
    status: ValidationStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_invoices(
            dtype=dtype,
            status=status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_invoice(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_invoice(record_id)
    if result is None:
        raise HTTPException(404, f"Invoice record '{record_id}' not found")
    return result.model_dump()


@router.post("/discrepancies")
async def add_discrepancy(
    body: AddDiscrepancyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_discrepancy(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_discrepancy_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_discrepancy_patterns()


@router.get("/high-discrepancies")
async def identify_high_discrepancies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_discrepancies()


@router.get("/amount-rankings")
async def rank_by_discrepancy_amount(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_discrepancy_amount()


@router.get("/anomalies")
async def detect_billing_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_billing_anomalies()


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


ivl_route = router
