"""Global search across all ShieldOps entities.

Provides a single search endpoint that queries investigations,
remediations, vulnerabilities, and agents in parallel using
parameterized ILIKE queries.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from shieldops.api.auth.dependencies import require_role
from shieldops.api.auth.models import UserResponse, UserRole

if TYPE_CHECKING:
    from shieldops.db.repository import Repository

logger = structlog.get_logger()

router = APIRouter()

_repository: Repository | None = None

VALID_ENTITY_TYPES = {
    "investigation",
    "remediation",
    "vulnerability",
    "agent",
}


def set_repository(repo: Any) -> None:
    """Inject the repository instance at startup."""
    global _repository
    _repository = repo


def _get_repo() -> Any:
    if _repository is None:
        raise HTTPException(503, "Search service unavailable")
    return _repository


def _compute_relevance(
    query: str,
    *fields: str | None,
) -> float:
    """Compute a simple relevance score (0.0-1.0).

    Higher scores for exact matches, lower for partial.
    """
    query_lower = query.lower()
    best = 0.0
    for field in fields:
        if field is None:
            continue
        field_lower = field.lower()
        if query_lower == field_lower:
            return 1.0
        if query_lower in field_lower:
            # Ratio of query length to field length
            ratio = len(query_lower) / max(len(field_lower), 1)
            score = 0.5 + (ratio * 0.4)
            best = max(best, score)
    return round(best, 2)


@router.get("/search")
async def global_search(
    request: Request,
    q: str = Query(..., min_length=2, max_length=200, description="Search query"),
    entity_types: str | None = Query(
        None,
        description=(
            "Comma-separated entity types to search: "
            "investigation, remediation, vulnerability, agent"
        ),
    ),
    limit: int = Query(20, ge=1, le=100),
    _user: UserResponse = Depends(require_role(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict[str, Any]:
    """Search across investigations, remediations, vulnerabilities, and agents."""
    repo = _get_repo()

    # Parse and validate entity type filters
    types_to_search = VALID_ENTITY_TYPES.copy()
    if entity_types:
        requested = {t.strip().lower() for t in entity_types.split(",")}
        invalid = requested - VALID_ENTITY_TYPES
        if invalid:
            raise HTTPException(
                400,
                f"Invalid entity types: {sorted(invalid)}. Valid: {sorted(VALID_ENTITY_TYPES)}",
            )
        types_to_search = requested

    # Per-entity limit: fetch more than needed, then trim after merge
    per_limit = min(limit, 50)

    # Build parallel search tasks
    tasks: dict[str, asyncio.Task[list[dict[str, Any]]]] = {}
    if "investigation" in types_to_search:
        tasks["investigation"] = asyncio.ensure_future(repo.search_investigations(q, per_limit))
    if "remediation" in types_to_search:
        tasks["remediation"] = asyncio.ensure_future(repo.search_remediations(q, per_limit))
    if "vulnerability" in types_to_search:
        tasks["vulnerability"] = asyncio.ensure_future(repo.search_vulnerabilities(q, per_limit))

    # Gather results (return exceptions instead of raising)
    results_map: dict[str, list[dict[str, Any]]] = {}
    if tasks:
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, raw_result in zip(tasks.keys(), gathered, strict=True):
            if isinstance(raw_result, BaseException):
                logger.warning(
                    "search_entity_failed",
                    entity_type=key,
                    error=str(raw_result),
                )
                results_map[key] = []
            else:
                results_map[key] = raw_result

    # Merge all results with entity_type and relevance
    merged: list[dict[str, Any]] = []

    for inv in results_map.get("investigation", []):
        merged.append(
            {
                "entity_type": "investigation",
                "id": inv.get("investigation_id", ""),
                "title": inv.get("alert_name", ""),
                "description": (
                    f"Severity: {inv.get('severity', 'unknown')} | "
                    f"Confidence: {inv.get('confidence', 0)}"
                ),
                "status": inv.get("status", ""),
                "relevance": _compute_relevance(
                    q,
                    inv.get("alert_name"),
                    inv.get("alert_id"),
                ),
                "url": (f"/investigations/{inv.get('investigation_id', '')}"),
                "created_at": inv.get("created_at"),
            }
        )

    for rem in results_map.get("remediation", []):
        merged.append(
            {
                "entity_type": "remediation",
                "id": rem.get("remediation_id", ""),
                "title": (f"{rem.get('action_type', '')} on {rem.get('target_resource', '')}"),
                "description": (
                    f"Environment: {rem.get('environment', '')} | Risk: {rem.get('risk_level', '')}"
                ),
                "status": rem.get("status", ""),
                "relevance": _compute_relevance(
                    q,
                    rem.get("action_type"),
                    rem.get("target_resource"),
                ),
                "url": (f"/remediations/{rem.get('remediation_id', '')}"),
                "created_at": rem.get("created_at"),
            }
        )

    for vuln in results_map.get("vulnerability", []):
        merged.append(
            {
                "entity_type": "vulnerability",
                "id": vuln.get("id", ""),
                "title": (vuln.get("title") or vuln.get("cve_id") or "Untitled vulnerability"),
                "description": (
                    f"Package: {vuln.get('package_name', '')} | "
                    f"Severity: {vuln.get('severity', '')}"
                ),
                "status": vuln.get("status", ""),
                "relevance": _compute_relevance(
                    q,
                    vuln.get("cve_id"),
                    vuln.get("title"),
                    vuln.get("package_name"),
                ),
                "url": f"/vulnerabilities/{vuln.get('id', '')}",
                "created_at": vuln.get("created_at"),
            }
        )

    # Sort by relevance descending, then by created_at descending
    merged.sort(
        key=lambda r: (
            r.get("relevance", 0),
            r.get("created_at") or "",
        ),
        reverse=True,
    )

    # Apply limit
    trimmed = merged[:limit]

    logger.info(
        "global_search",
        query=q,
        total=len(merged),
        returned=len(trimmed),
        entity_types=sorted(types_to_search),
    )

    return {
        "query": q,
        "total": len(merged),
        "results": trimmed,
    }
