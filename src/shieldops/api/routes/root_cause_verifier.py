"""Root cause verifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.root_cause_verifier import (
    CausalStrength,
    EvidenceType,
    VerificationResult,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/root-cause-verifier",
    tags=["Root Cause Verifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Root cause verifier service unavailable",
        )
    return _engine


class RecordVerificationRequest(BaseModel):
    hypothesis: str
    evidence_type: EvidenceType = EvidenceType.LOG_PATTERN
    result: VerificationResult = VerificationResult.CONFIRMED
    strength: CausalStrength = CausalStrength.STRONG
    confidence_score: float = 0.0
    details: str = ""


class AddEvidenceChainRequest(BaseModel):
    chain_name: str
    evidence_type: EvidenceType = EvidenceType.LOG_PATTERN
    strength: CausalStrength = CausalStrength.STRONG
    link_count: int = 0
    weight: float = 1.0


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
    hypothesis: str | None = None,
    evidence_type: EvidenceType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_verifications(
            hypothesis=hypothesis,
            evidence_type=evidence_type,
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
        raise HTTPException(
            404,
            f"Verification '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/chains")
async def add_evidence_chain(
    body: AddEvidenceChainRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_evidence_chain(**body.model_dump())
    return result.model_dump()


@router.get("/accuracy/{hypothesis}")
async def analyze_accuracy(
    hypothesis: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_verification_accuracy(hypothesis)


@router.get("/disproved")
async def identify_disproved(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_disproved_hypotheses()


@router.get("/rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/weak-evidence")
async def detect_weak_evidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_weak_evidence()


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


rcv_route = router
