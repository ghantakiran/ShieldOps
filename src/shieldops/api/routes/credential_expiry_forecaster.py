"""Credential expiry forecaster API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
cef_route = APIRouter(
    prefix="/credential-expiry-forecaster",
    tags=["Credential Expiry Forecaster"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Credential expiry forecaster service unavailable",
        )
    return _instance


# -- Request models --


class RegisterCredentialRequest(BaseModel):
    credential_name: str
    credential_type: str = "api_key"
    service_name: str = ""
    expires_at: float = 0.0
    owner: str = ""


class UpdateStatusRequest(BaseModel):
    credential_id: str
    status: str


# -- Routes --


@cef_route.post("/credentials")
async def register_credential(
    body: RegisterCredentialRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.register_credential(**body.model_dump())
    return record.model_dump()


@cef_route.get("/credentials")
async def list_credentials(
    credential_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        c.model_dump()
        for c in engine.list_credentials(
            credential_type=credential_type,
            status=status,
            limit=limit,
        )
    ]


@cef_route.get("/credentials/{credential_id}")
async def get_credential(
    credential_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    cred = engine.get_credential(credential_id)
    if cred is None:
        raise HTTPException(404, f"Credential '{credential_id}' not found")
    return cred.model_dump()


@cef_route.post("/forecasts/{credential_id}")
async def forecast_renewal(
    credential_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    forecast = engine.forecast_renewal(credential_id)
    if forecast is None:
        raise HTTPException(404, f"Credential '{credential_id}' not found")
    return forecast.model_dump()


@cef_route.get("/forecasts")
async def list_forecasts(
    credential_id: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        f.model_dump()
        for f in engine.list_forecasts(
            credential_id=credential_id,
            limit=limit,
        )
    ]


@cef_route.post("/update-status")
async def update_status(
    body: UpdateStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.update_status(body.credential_id, body.status)
    if not result:
        raise HTTPException(404, f"Credential '{body.credential_id}' not found")
    return {"updated": True, "credential_id": body.credential_id}


@cef_route.get("/expired-unrotated")
async def get_expired_unrotated(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [c.model_dump() for c in engine.find_expired_unrotated()]


@cef_route.get("/urgency/{credential_id}")
async def get_urgency(
    credential_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_urgency(credential_id)


@cef_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_expiry_report().model_dump()


@cef_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
