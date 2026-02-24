"""Alert Correlation Rules API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/alert-correlation-rules", tags=["Alert Correlation Rules"])

_instance: Any = None


def set_engine(inst: Any) -> None:
    global _instance
    _instance = inst


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(503, "Alert correlation rules service unavailable")
    return _instance


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterRuleRequest(BaseModel):
    name: str
    rule_type: str
    action: str
    source_pattern: str = ""
    target_pattern: str = ""
    time_window_seconds: int = 300
    priority: int = 0


class EvaluateAlertRequest(BaseModel):
    alert_name: str
    alert_source: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/rules")
async def register_rule(
    body: RegisterRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.register_rule(
        name=body.name,
        rule_type=body.rule_type,
        action=body.action,
        source_pattern=body.source_pattern,
        target_pattern=body.target_pattern,
        time_window_seconds=body.time_window_seconds,
        priority=body.priority,
    )
    return result.model_dump()


@router.get("/rules")
async def list_rules(
    rule_type: str | None = None,
    status: str | None = None,
    action: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_rules(
            rule_type=rule_type,
            status=status,
            action=action,
            limit=limit,
        )
    ]


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_rule(rule_id)
    if result is None:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return result.model_dump()


@router.post("/evaluate")
async def evaluate_alert(
    body: EvaluateAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    matches = engine.evaluate_alert(
        alert_name=body.alert_name,
        alert_source=body.alert_source,
    )
    return [m.model_dump() for m in matches]


@router.get("/correlated/{alert_name}")
async def find_correlated(
    alert_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [m.model_dump() for m in engine.find_correlated_alerts(alert_name)]


@router.get("/suppression-rate")
async def suppression_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_suppression_rate()


@router.get("/conflicts")
async def detect_conflicts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_rule_conflicts()


@router.get("/ranked")
async def ranked_rules(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.rank_rules_by_effectiveness()]


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_correlation_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
