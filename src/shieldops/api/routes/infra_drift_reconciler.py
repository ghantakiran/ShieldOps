"""Infrastructure Drift Reconciler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.infra_drift_reconciler import (
    DriftType,
    IaCProvider,
    ReconcileAction,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/infra-drift-reconciler",
    tags=["Infrastructure Drift Reconciler"],
)

_instance: Any = None


def set_reconciler(reconciler: Any) -> None:
    global _instance
    _instance = reconciler


def _get_reconciler() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Infra drift reconciler unavailable",
        )
    return _instance


class RecordDriftRequest(BaseModel):
    resource_type: str = ""
    resource_id: str = ""
    provider: IaCProvider = IaCProvider.TERRAFORM
    drift_type: DriftType = DriftType.MODIFIED
    expected_value: str = ""
    actual_value: str = ""
    reconcile_action: ReconcileAction = ReconcileAction.MANUAL_REVIEW


class ReconcileDriftRequest(BaseModel):
    drift_id: str
    action: ReconcileAction = ReconcileAction.APPLY_IAC


@router.post("/record")
async def record_drift(
    body: RecordDriftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    rec = _get_reconciler()
    drift = rec.record_drift(**body.model_dump())
    return drift.model_dump()


@router.post("/reconcile")
async def reconcile_drift(
    body: ReconcileDriftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    rec = _get_reconciler()
    result = rec.reconcile_drift(
        drift_id=body.drift_id,
        action=body.action,
    )
    if result is None:
        raise HTTPException(404, "Drift not found")
    return result.model_dump()


@router.post("/auto-reconcile")
async def auto_reconcile(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    rec = _get_reconciler()
    results = rec.auto_reconcile_safe_drifts()
    return [r.model_dump() for r in results]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    rec = _get_reconciler()
    return rec.get_stats()


@router.get("/report")
async def get_drift_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    rec = _get_reconciler()
    return rec.generate_drift_report().model_dump()


@router.get("/score")
async def get_drift_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    rec = _get_reconciler()
    return rec.calculate_drift_score()


@router.get("/persistent")
async def get_persistent_drifts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    rec = _get_reconciler()
    return rec.identify_persistent_drifts()


@router.get("/effort")
async def get_reconcile_effort(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    rec = _get_reconciler()
    return rec.estimate_reconcile_effort()


@router.get("")
async def list_drifts(
    provider: IaCProvider | None = None,
    drift_type: DriftType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    rec = _get_reconciler()
    return [
        d.model_dump()
        for d in rec.list_drifts(
            provider=provider,
            drift_type=drift_type,
            limit=limit,
        )
    ]


@router.get("/{drift_id}")
async def get_drift(
    drift_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    rec = _get_reconciler()
    drift = rec.get_drift(drift_id)
    if drift is None:
        raise HTTPException(404, f"Drift '{drift_id}' not found")
    return drift.model_dump()
