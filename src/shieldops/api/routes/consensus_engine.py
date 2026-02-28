"""Agent consensus engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.consensus_engine import (
    ConsensusStrategy,
    DisagreementAction,
    VoteType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/consensus-engine",
    tags=["Consensus Engine"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Consensus engine service unavailable")
    return _engine


class RecordDecisionRequest(BaseModel):
    decision_id: str
    vote_type: VoteType = VoteType.APPROVE
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY
    disagreement_action: DisagreementAction = DisagreementAction.ESCALATE
    voter_count: int = 0
    details: str = ""


class AddVoteRequest(BaseModel):
    agent_name: str
    vote_type: VoteType = VoteType.APPROVE
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY
    confidence_score: float = 0.0


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
    decision_id: str | None = None,
    consensus_strategy: ConsensusStrategy | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_decisions(
            decision_id=decision_id,
            consensus_strategy=consensus_strategy,
            limit=limit,
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


@router.post("/votes")
async def add_vote(
    body: AddVoteRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_vote(**body.model_dump())
    return result.model_dump()


@router.get("/consensus-quality/{decision_id}")
async def analyze_consensus_quality(
    decision_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_consensus_quality(decision_id)


@router.get("/disputed-decisions")
async def identify_disputed_decisions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_disputed_decisions()


@router.get("/rankings")
async def rank_by_disagreement_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_disagreement_rate()


@router.get("/voting-deadlocks")
async def detect_voting_deadlocks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_voting_deadlocks()


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


ace_route = router
