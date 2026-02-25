"""Policy violation tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
pvt_route = APIRouter(
    prefix="/policy-violation-tracker",
    tags=["Policy Violation Tracker"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Policy violation tracker service unavailable",
        )
    return _instance


# -- Request models --


class RecordViolationRequest(BaseModel):
    policy_name: str
    violator_name: str
    violator_type: str = "agent"
    severity: str = "low"
    domain: str = "infrastructure"
    description: str = ""


class ComputeTrendRequest(BaseModel):
    policy_name: str
    period_label: str = "current"


# -- Routes --


@pvt_route.post("/violations")
async def record_violation(
    body: RecordViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    violation = engine.record_violation(**body.model_dump())
    return violation.model_dump()


@pvt_route.get("/violations")
async def list_violations(
    policy_name: str | None = None,
    severity: str | None = None,
    domain: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        v.model_dump()
        for v in engine.list_violations(
            policy_name=policy_name,
            severity=severity,
            domain=domain,
            limit=limit,
        )
    ]


@pvt_route.get("/violations/{violation_id}")
async def get_violation(
    violation_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    violation = engine.get_violation(violation_id)
    if violation is None:
        raise HTTPException(404, f"Violation '{violation_id}' not found")
    return violation.model_dump()


@pvt_route.post("/trends")
async def compute_trend(
    body: ComputeTrendRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    trend = engine.compute_trend(**body.model_dump())
    return trend.model_dump()


@pvt_route.get("/trends")
async def list_trends(
    policy_name: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        t.model_dump()
        for t in engine.list_trends(
            policy_name=policy_name,
            limit=limit,
        )
    ]


@pvt_route.get("/repeat-offenders")
async def get_repeat_offenders(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_repeat_offenders()


@pvt_route.get("/effectiveness/{policy_name}")
async def get_policy_effectiveness(
    policy_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_policy_effectiveness(policy_name)


@pvt_route.get("/profile/{violator_name}")
async def get_violator_profile(
    violator_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_violator_profile(violator_name)


@pvt_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_violation_report().model_dump()


@pvt_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
