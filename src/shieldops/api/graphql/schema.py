"""GraphQL-style query resolver for ShieldOps.

Provides a flexible query endpoint that supports field selection,
filtering, and nested resolution -- similar to GraphQL but using
plain FastAPI + Pydantic (no Strawberry dependency required).
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class QueryField(BaseModel):
    """A field selection with optional sub-fields and filters."""

    name: str
    fields: list[str] = Field(default_factory=list)  # If empty, return all
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 50
    offset: int = 0


class GraphQLRequest(BaseModel):
    """A query request with multiple top-level queries."""

    queries: list[QueryField] = Field(default_factory=list)


class GraphQLResponse(BaseModel):
    """Response containing results for each queried resource."""

    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class QueryResolver:
    """Resolves GraphQL-style queries against the ShieldOps repository."""

    def __init__(self, repository: Any = None) -> None:
        self._repository = repository
        self._resolvers: dict[str, Any] = {
            "investigations": self._resolve_investigations,
            "investigation": self._resolve_investigation,
            "remediations": self._resolve_remediations,
            "remediation": self._resolve_remediation,
            "security_scans": self._resolve_security_scans,
            "agents": self._resolve_agents,
            "vulnerabilities": self._resolve_vulnerabilities,
            "analytics_summary": self._resolve_analytics_summary,
        }

    @property
    def available_queries(self) -> list[str]:
        return list(self._resolvers.keys())

    async def resolve(self, request: GraphQLRequest) -> GraphQLResponse:
        """Resolve all queries in the request."""
        response = GraphQLResponse()

        for query in request.queries:
            resolver = self._resolvers.get(query.name)
            if not resolver:
                response.errors.append(f"Unknown query: {query.name}")
                continue

            try:
                result = await resolver(query)
                # Apply field selection
                if query.fields:
                    result = self._select_fields(result, query.fields)
                response.data[query.name] = result
            except Exception as e:
                response.errors.append(f"Error resolving {query.name}: {e}")
                logger.error("graphql_resolve_error", query=query.name, error=str(e))

        return response

    def _select_fields(self, data: Any, fields: list[str]) -> Any:
        """Filter response to only include selected fields."""
        if isinstance(data, list):
            return [self._select_fields(item, fields) for item in data]
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k in fields}
        return data

    # -- Resolvers -----------------------------------------------------

    async def _resolve_investigations(self, query: QueryField) -> list[dict[str, Any]]:
        if not self._repository:
            return []
        result: list[dict[str, Any]] = await self._repository.list_investigations(
            status=query.filters.get("status"),
            limit=query.limit,
            offset=query.offset,
        )
        return result

    async def _resolve_investigation(self, query: QueryField) -> dict[str, Any] | None:
        if not self._repository:
            return None
        inv_id = query.filters.get("id", "")
        if not inv_id:
            return None
        result: dict[str, Any] | None = await self._repository.get_investigation(inv_id)
        return result

    async def _resolve_remediations(self, query: QueryField) -> list[dict[str, Any]]:
        if not self._repository:
            return []
        result: list[dict[str, Any]] = await self._repository.list_remediations(
            environment=query.filters.get("environment"),
            status=query.filters.get("status"),
            limit=query.limit,
            offset=query.offset,
        )
        return result

    async def _resolve_remediation(self, query: QueryField) -> dict[str, Any] | None:
        if not self._repository:
            return None
        rem_id = query.filters.get("id", "")
        if not rem_id:
            return None
        result: dict[str, Any] | None = await self._repository.get_remediation(rem_id)
        return result

    async def _resolve_security_scans(self, query: QueryField) -> list[dict[str, Any]]:
        if not self._repository:
            return []
        result: list[dict[str, Any]] = await self._repository.list_security_scans(
            environment=query.filters.get("environment"),
            scan_type=query.filters.get("scan_type"),
            status=query.filters.get("status"),
            limit=query.limit,
            offset=query.offset,
        )
        return result

    async def _resolve_agents(self, query: QueryField) -> list[dict[str, Any]]:
        """Return static agent type listing (no DB query needed)."""
        agent_types = [
            {"type": "investigation", "description": "Root cause analysis from alerts"},
            {"type": "remediation", "description": "Execute infrastructure changes"},
            {"type": "security", "description": "CVE patching, credential rotation"},
            {"type": "cost", "description": "Cost analysis and optimization"},
            {"type": "learning", "description": "Playbook and threshold refinement"},
            {"type": "supervisor", "description": "Orchestrates specialist agents"},
        ]
        return agent_types

    async def _resolve_vulnerabilities(self, query: QueryField) -> list[dict[str, Any]]:
        if not self._repository:
            return []
        result: list[dict[str, Any]] = await self._repository.list_vulnerabilities(
            status=query.filters.get("status"),
            severity=query.filters.get("severity"),
            limit=query.limit,
            offset=query.offset,
        )
        return result

    async def _resolve_analytics_summary(self, query: QueryField) -> dict[str, Any]:
        """Return a basic analytics summary."""
        if not self._repository:
            return {"total_investigations": 0, "total_remediations": 0}

        try:
            inv_count = await self._repository.count_investigations()
            rem_count = await self._repository.count_remediations()
        except Exception:
            inv_count = 0
            rem_count = 0

        return {
            "total_investigations": inv_count,
            "total_remediations": rem_count,
        }
