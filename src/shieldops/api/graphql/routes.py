"""FastAPI routes for GraphQL-style query API."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse
from shieldops.api.graphql.schema import GraphQLRequest, QueryResolver

logger = structlog.get_logger()
router = APIRouter()

_resolver: QueryResolver | None = None


def set_resolver(resolver: QueryResolver) -> None:
    global _resolver  # noqa: PLW0603
    _resolver = resolver


@router.post("/graphql")
async def graphql_query(
    request: GraphQLRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Execute GraphQL-style queries.

    Example request body:
    {
        "queries": [
            {
                "name": "investigations",
                "fields": ["investigation_id", "alert_name", "severity", "status"],
                "filters": {"status": "completed"},
                "limit": 10
            },
            {
                "name": "agents",
                "fields": ["type", "description"]
            }
        ]
    }
    """
    if not _resolver:
        return {"data": {}, "errors": ["GraphQL resolver not initialized"]}
    response = await _resolver.resolve(request)
    return response.model_dump(mode="json")


@router.get("/graphql/schema")
async def get_schema(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List available queries and their descriptions."""
    if not _resolver:
        return {"queries": []}
    return {
        "queries": [
            {"name": q, "description": f"Query {q} resources"} for q in _resolver.available_queries
        ],
    }
