"""Decision audit logger API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.decision_audit import (
    ConfidenceLevel,
    DecisionOutcome,
    DecisionType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/decision-audit",
    tags=["Decision Audit"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Decision audit service unavailable")
    return _engine


class RecordDecisionRequest(BaseModel):
    agent_name: str
    decision_type: DecisionType = DecisionType.REMEDIATION
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    confidence_score: float = 0.0
    details: str = ""


class AddRationaleRequest(BaseModel):
    rationale_name: str
    decision_type: DecisionType = DecisionType.REMEDIATION
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE
    weight: float = 0.0
    description: str = ""


@router.post("/decisions")
async def record_decision(
    body: RecordDecisionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_decision(**body.model_dump())
    return result.model_dump()


@router.get("/decisions")
async def list_decisions(
    agent_name: str | None = None,
    decision_type: DecisionType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_decisions(
            agent_name=agent_name, decision_type=decision_type, limit=limit
        )
    ]


@router.get("/decisions/{record_id}")
async def get_decision(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_decision(record_id)
    if result is None:
        raise HTTPException(404, f"Decision '{record_id}' not found")
    return result.model_dump()


@router.post("/rationales")
async def add_rationale(
    body: AddRationaleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rationale(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{agent_name}")
async def analyze_agent_decisions(
    agent_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_agent_decisions(agent_name)


@router.get("/low-confidence")
async def identify_low_confidence_decisions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_confidence_decisions()


@router.get("/rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/patterns")
async def detect_decision_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_decision_patterns()


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


dal_route = router
