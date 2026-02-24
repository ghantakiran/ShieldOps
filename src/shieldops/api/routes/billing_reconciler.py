"""Billing reconciler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/billing-reconciler",
    tags=["Billing Reconciler"],
)

_instance: Any = None


def set_reconciler(reconciler: Any) -> None:
    global _instance
    _instance = reconciler


def _get_reconciler() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Billing reconciler service unavailable",
        )
    return _instance


class RecordBillingRequest(BaseModel):
    provider: str = "aws"
    account_id: str = ""
    service_name: str = ""
    expected_cost: float = 0.0
    actual_cost: float = 0.0
    billing_period: str = ""


class ReconcilePeriodRequest(BaseModel):
    billing_period: str


@router.post("/records")
async def record_billing(
    body: RecordBillingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    record = reconciler.record_billing(
        **body.model_dump(),
    )
    return record.model_dump()


@router.get("/records")
async def list_records(
    provider: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reconciler = _get_reconciler()
    return [
        r.model_dump()
        for r in reconciler.list_records(
            provider=provider,
            status=status,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    record = reconciler.get_record(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Record '{record_id}' not found",
        )
    return record.model_dump()


@router.post("/reconcile")
async def reconcile_period(
    body: ReconcilePeriodRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    result = reconciler.reconcile_period(
        body.billing_period,
    )
    return result.model_dump()


@router.get("/discrepancies")
async def detect_discrepancies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reconciler = _get_reconciler()
    return [r.model_dump() for r in reconciler.detect_discrepancies()]


@router.post("/flag-unexpected")
async def flag_unexpected(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reconciler = _get_reconciler()
    return [r.model_dump() for r in (reconciler.flag_unexpected_charges())]


@router.get("/accuracy")
async def accuracy_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    rate = reconciler.calculate_accuracy_rate()
    return {"accuracy_rate": rate}


@router.get("/annual-leakage")
async def annual_leakage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    leakage = reconciler.estimate_annual_leakage()
    return {"annual_leakage": leakage}


@router.get("/report")
async def reconciler_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    report = reconciler.generate_reconciler_report()
    return report.model_dump()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    count = reconciler.clear_data()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconciler = _get_reconciler()
    return reconciler.get_stats()
