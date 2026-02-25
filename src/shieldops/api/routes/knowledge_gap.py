"""Knowledge Gap Detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.knowledge_gap import (
    GapPriority,
    GapType,
    KnowledgeArea,
)

logger = structlog.get_logger()
kg_route = APIRouter(
    prefix="/knowledge-gap",
    tags=["Knowledge Gap Detector"],
)

_instance: Any = None


def set_detector(detector: Any) -> None:
    global _instance
    _instance = detector


def _get_detector() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Knowledge gap service unavailable",
        )
    return _instance


class RecordGapRequest(BaseModel):
    service_name: str = ""
    gap_type: GapType = GapType.MISSING_RUNBOOK
    area: KnowledgeArea = KnowledgeArea.INCIDENT_RESPONSE
    priority: GapPriority = GapPriority.MEDIUM
    description: str = ""
    single_expert: str = ""
    doc_age_days: int = 0


class ResolveGapRequest(BaseModel):
    gap_id: str


@kg_route.post("/record")
async def record_gap(
    body: RecordGapRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    det = _get_detector()
    gap = det.record_gap(**body.model_dump())
    return gap.model_dump()  # type: ignore[no-any-return]


@kg_route.post("/resolve")
async def resolve_gap(
    body: ResolveGapRequest,
    _user: Any = Depends(
        require_role("operator")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    det = _get_detector()
    result = det.resolve_gap(body.gap_id)
    if result is None:
        raise HTTPException(404, "Gap not found")
    return result.model_dump()  # type: ignore[no-any-return]


@kg_route.get("/stats")
async def get_stats(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    det = _get_detector()
    return det.get_stats()  # type: ignore[no-any-return]


@kg_route.get("/report")
async def get_knowledge_report(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    det = _get_detector()
    return det.generate_knowledge_report().model_dump()  # type: ignore[no-any-return]


@kg_route.get("/coverage")
async def get_coverage(
    service_name: str | None = None,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    det = _get_detector()
    return det.calculate_coverage(  # type: ignore[no-any-return]
        service_name=service_name,
    ).model_dump()


@kg_route.get("/tribal-risks")
async def get_tribal_risks(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    det = _get_detector()
    return det.detect_tribal_knowledge_risks()  # type: ignore[no-any-return]


@kg_route.get("/stale")
async def get_stale_docs(
    max_age_days: int = 180,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    det = _get_detector()
    return det.identify_stale_documentation(  # type: ignore[no-any-return]
        max_age_days=max_age_days,
    )


@kg_route.get("/priority-ranking")
async def get_priority_ranking(
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    det = _get_detector()
    return det.rank_by_priority()  # type: ignore[no-any-return]


@kg_route.get("")
async def list_gaps(
    service_name: str | None = None,
    gap_type: GapType | None = None,
    limit: int = 50,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> list[dict[str, Any]]:
    det = _get_detector()
    return [  # type: ignore[no-any-return]
        g.model_dump()
        for g in det.list_gaps(
            service_name=service_name,
            gap_type=gap_type,
            limit=limit,
        )
    ]


@kg_route.get("/{gap_id}")
async def get_gap(
    gap_id: str,
    _user: Any = Depends(
        require_role("viewer")  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    det = _get_detector()
    gap = det.get_gap(gap_id)
    if gap is None:
        raise HTTPException(404, f"Gap '{gap_id}' not found")
    return gap.model_dump()  # type: ignore[no-any-return]
