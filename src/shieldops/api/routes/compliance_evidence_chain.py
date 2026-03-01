"""Compliance Evidence Chain Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.compliance_evidence_chain import (
    ChainRisk,
    ChainStatus,
    EvidenceLink,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/compliance-evidence-chain",
    tags=["Compliance Evidence Chain"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Compliance evidence chain service unavailable")
    return _engine


class RecordChainRequest(BaseModel):
    chain_id: str
    chain_status: ChainStatus = ChainStatus.PENDING
    evidence_link: EvidenceLink = EvidenceLink.CONTROL_TO_EVIDENCE
    chain_risk: ChainRisk = ChainRisk.NONE
    integrity_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddValidationRequest(BaseModel):
    chain_id: str
    chain_status: ChainStatus = ChainStatus.PENDING
    validation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/chains")
async def record_chain(
    body: RecordChainRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_chain(**body.model_dump())
    return result.model_dump()


@router.get("/chains")
async def list_chains(
    status: ChainStatus | None = None,
    link: EvidenceLink | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_chains(
            status=status,
            link=link,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/chains/{record_id}")
async def get_chain(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_chain(record_id)
    if result is None:
        raise HTTPException(404, f"Chain record '{record_id}' not found")
    return result.model_dump()


@router.post("/validations")
async def add_validation(
    body: AddValidationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_validation(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_chain_integrity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_chain_integrity()


@router.get("/broken-chains")
async def identify_broken_chains(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_broken_chains()


@router.get("/integrity-rankings")
async def rank_by_integrity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_integrity()


@router.get("/trends")
async def detect_chain_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_chain_trends()


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


cec_route = router
