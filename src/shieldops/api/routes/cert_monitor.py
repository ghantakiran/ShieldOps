"""Certificate monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cert-monitor",
    tags=["Certificate Monitor"],
)

_instance: Any = None


def set_monitor(instance: Any) -> None:
    global _instance
    _instance = instance


def _get_monitor() -> Any:
    if _instance is None:
        raise HTTPException(503, "Certificate monitor service unavailable")
    return _instance


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterCertRequest(BaseModel):
    domain: str
    cert_type: str = "TLS"
    issuer: str = ""
    expires_at: float = 0.0
    auto_renew: bool = False


class RenewRequest(BaseModel):
    new_expires_at: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/certificates")
async def register_certificate(
    body: RegisterCertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    result = monitor.register_certificate(
        domain=body.domain,
        cert_type=body.cert_type.lower(),
        issuer=body.issuer,
        expires_at=body.expires_at,
        auto_renew=body.auto_renew,
    )
    return result.model_dump()


@router.get("/certificates")
async def list_certificates(
    cert_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    ct = cert_type.lower() if cert_type is not None else None
    st = status.lower() if status is not None else None
    return [
        c.model_dump()
        for c in monitor.list_certificates(
            cert_type=ct,
            status=st,
            limit=limit,
        )
    ]


@router.get("/certificates/{cert_id}")
async def get_certificate(
    cert_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    result = monitor.get_certificate(cert_id)
    if result is None:
        raise HTTPException(404, f"Certificate '{cert_id}' not found")
    return result.model_dump()


@router.get("/expiring")
async def check_expiring(
    days_ahead: int | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    alerts = monitor.check_expiring(days_ahead=days_ahead)
    return [a.model_dump() for a in alerts]


@router.post("/certificates/{cert_id}/acknowledge")
async def acknowledge_alert(
    cert_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    # Find the most recent alert for this certificate
    alerts = [a for a in monitor._alerts if a.certificate_id == cert_id]
    if not alerts:
        raise HTTPException(404, f"No alerts found for certificate '{cert_id}'")
    latest_alert = alerts[-1]
    monitor.acknowledge_alert(latest_alert.id)
    return latest_alert.model_dump()


@router.put("/certificates/{cert_id}/renew")
async def renew_certificate(
    cert_id: str,
    body: RenewRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    success = monitor.renew_certificate(cert_id, new_expires_at=body.new_expires_at)
    if not success:
        raise HTTPException(404, f"Certificate '{cert_id}' not found")
    result = monitor.get_certificate(cert_id)
    return result.model_dump()


@router.put("/certificates/{cert_id}/revoke")
async def revoke_certificate(
    cert_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    success = monitor.revoke_certificate(cert_id)
    if not success:
        raise HTTPException(404, f"Certificate '{cert_id}' not found")
    result = monitor.get_certificate(cert_id)
    return result.model_dump()


@router.get("/inventory-summary")
async def generate_inventory_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.generate_inventory_summary().model_dump()


@router.delete("/certificates/{cert_id}")
async def delete_certificate(
    cert_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    success = monitor.delete_certificate(cert_id)
    if not success:
        raise HTTPException(404, f"Certificate '{cert_id}' not found")
    return {"deleted": True, "cert_id": cert_id}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.get_stats()
