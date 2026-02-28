"""Zero trust verifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.zero_trust_verifier import (
    ComplianceStatus,
    TrustLevel,
    VerificationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/zero-trust",
    tags=["Zero Trust"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Zero trust service unavailable")
    return _engine


class RecordVerificationRequest(BaseModel):
    service_name: str
    verification_type: VerificationType = VerificationType.IDENTITY
    trust_level: TrustLevel = TrustLevel.CONDITIONALLY_TRUSTED
    compliance_status: ComplianceStatus = ComplianceStatus.PENDING_REVIEW
    trust_score: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    verification_type: VerificationType = VerificationType.NETWORK
    trust_level: TrustLevel = TrustLevel.LIMITED
    min_trust_score: float = 0.0


@router.post("/verifications")
async def record_verification(
    body: RecordVerificationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_verification(**body.model_dump())
    return result.model_dump()


@router.get("/verifications")
async def list_verifications(
    service_name: str | None = None,
    verification_type: VerificationType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_verifications(
            service_name=service_name,
            verification_type=verification_type,
            limit=limit,
        )
    ]


@router.get("/verifications/{record_id}")
async def get_verification(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_verification(record_id)
    if result is None:
        raise HTTPException(404, f"Verification '{record_id}' not found")
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/trust/{service_name}")
async def analyze_service_trust(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_trust(service_name)


@router.get("/untrusted")
async def identify_untrusted_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_untrusted_services()


@router.get("/rankings")
async def rank_by_trust_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_trust_score()


@router.get("/violations")
async def detect_trust_violations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_trust_violations()


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


ztv_route = router
