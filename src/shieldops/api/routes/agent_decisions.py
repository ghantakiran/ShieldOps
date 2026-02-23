"""Agent decision explainability API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/agent-decisions", tags=["Agent Decisions"])

_explainer: Any = None


def set_explainer(explainer: Any) -> None:
    global _explainer
    _explainer = explainer


def _get_explainer() -> Any:
    if _explainer is None:
        raise HTTPException(503, "Agent decision service unavailable")
    return _explainer


class RecordDecisionRequest(BaseModel):
    agent_id: str
    action: str
    agent_type: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    confidence: str = "medium"


class AddStepRequest(BaseModel):
    description: str
    reasoning: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    confidence: str = "medium"


class AddAlternativeRequest(BaseModel):
    description: str
    reason_rejected: str = ""
    estimated_impact: str = ""
    confidence: str = "low"


class FinalizeRequest(BaseModel):
    outcome: str
    summary: str = ""


@router.post("")
async def record_decision(
    body: RecordDecisionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    explainer = _get_explainer()
    decision = explainer.record_decision(**body.model_dump())
    return decision.model_dump()


@router.post("/{decision_id}/steps")
async def add_step(
    decision_id: str,
    body: AddStepRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    explainer = _get_explainer()
    step = explainer.add_step(decision_id=decision_id, **body.model_dump())
    if step is None:
        raise HTTPException(404, f"Decision '{decision_id}' not found")
    return step.model_dump()


@router.post("/{decision_id}/alternatives")
async def add_alternative(
    decision_id: str,
    body: AddAlternativeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    explainer = _get_explainer()
    alt = explainer.add_alternative(decision_id=decision_id, **body.model_dump())
    if alt is None:
        raise HTTPException(404, f"Decision '{decision_id}' not found")
    return alt.model_dump()


@router.put("/{decision_id}/finalize")
async def finalize_decision(
    decision_id: str,
    body: FinalizeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    explainer = _get_explainer()
    decision = explainer.finalize_decision(decision_id=decision_id, **body.model_dump())
    if decision is None:
        raise HTTPException(404, f"Decision '{decision_id}' not found")
    return decision.model_dump()


@router.get("/{decision_id}")
async def get_decision(
    decision_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    explainer = _get_explainer()
    decision = explainer.get_decision(decision_id)
    if decision is None:
        raise HTTPException(404, f"Decision '{decision_id}' not found")
    return decision.model_dump()


@router.get("")
async def list_decisions(
    agent_id: str | None = None,
    outcome: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    explainer = _get_explainer()
    return [d.model_dump() for d in explainer.list_decisions(agent_id=agent_id, outcome=outcome)]


@router.get("/by-agent/{agent_id}")
async def get_by_agent(
    agent_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    explainer = _get_explainer()
    return [d.model_dump() for d in explainer.get_by_agent(agent_id)]


@router.get("/{decision_id}/explain")
async def get_explanation(
    decision_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    explainer = _get_explainer()
    explanation = explainer.get_explanation(decision_id)
    if explanation is None:
        raise HTTPException(404, f"Decision '{decision_id}' not found")
    return explanation


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    explainer = _get_explainer()
    return explainer.get_stats()
