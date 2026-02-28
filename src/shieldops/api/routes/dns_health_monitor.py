"""DNS health monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.dns_health_monitor import (
    DNSHealth,
    DNSProvider,
    DNSRecordType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dns-health",
    tags=["DNS Health"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "DNS health service unavailable")
    return _engine


class RecordCheckRequest(BaseModel):
    domain_name: str
    record_type: DNSRecordType = DNSRecordType.A_RECORD
    health: DNSHealth = DNSHealth.HEALTHY
    provider: DNSProvider = DNSProvider.ROUTE53
    resolution_ms: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    record_type: DNSRecordType = DNSRecordType.A_RECORD
    provider: DNSProvider = DNSProvider.ROUTE53
    max_resolution_ms: float = 100.0
    ttl_seconds: float = 300.0


@router.post("/checks")
async def record_check(
    body: RecordCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_check(**body.model_dump())
    return result.model_dump()


@router.get("/checks")
async def list_checks(
    domain_name: str | None = None,
    record_type: DNSRecordType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_checks(
            domain_name=domain_name,
            record_type=record_type,
            limit=limit,
        )
    ]


@router.get("/checks/{record_id}")
async def get_check(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_check(record_id)
    if result is None:
        raise HTTPException(404, f"Check '{record_id}' not found")
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/health/{domain_name}")
async def analyze_dns_health(
    domain_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_dns_health(domain_name)


@router.get("/failing-domains")
async def identify_failing_domains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failing_domains()


@router.get("/rankings")
async def rank_by_resolution_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_resolution_time()


@router.get("/dns-issues")
async def detect_dns_issues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_dns_issues()


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


dhm_route = router
