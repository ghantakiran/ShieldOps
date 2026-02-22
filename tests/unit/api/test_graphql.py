"""Tests for GraphQL-style query API."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.graphql import routes as graphql_routes
from shieldops.api.graphql.schema import GraphQLRequest, QueryField, QueryResolver


def _mock_user() -> UserResponse:
    return UserResponse(id="usr-t", email="t@t.com", name="T", role=UserRole.ADMIN, is_active=True)


def _mock_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.list_investigations = AsyncMock(
        return_value=[
            {
                "investigation_id": "inv-1",
                "alert_name": "HighCPU",
                "severity": "warning",
                "status": "completed",
            },
            {
                "investigation_id": "inv-2",
                "alert_name": "OOM",
                "severity": "critical",
                "status": "in_progress",
            },
        ]
    )
    repo.get_investigation = AsyncMock(
        return_value={
            "investigation_id": "inv-1",
            "alert_name": "HighCPU",
            "severity": "warning",
        }
    )
    repo.list_remediations = AsyncMock(
        return_value=[
            {"remediation_id": "rem-1", "action_type": "restart", "status": "completed"},
        ]
    )
    repo.get_remediation = AsyncMock(
        return_value={
            "remediation_id": "rem-1",
            "action_type": "restart",
        }
    )
    repo.list_security_scans = AsyncMock(return_value=[])
    repo.list_vulnerabilities = AsyncMock(return_value=[])
    repo.count_investigations = AsyncMock(return_value=42)
    repo.count_remediations = AsyncMock(return_value=17)
    return repo


class TestQueryResolver:
    @pytest.mark.asyncio
    async def test_resolve_investigations(self) -> None:
        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        request = GraphQLRequest(
            queries=[
                QueryField(name="investigations", limit=10),
            ]
        )
        response = await resolver.resolve(request)
        assert "investigations" in response.data
        assert len(response.data["investigations"]) == 2
        assert response.errors == []

    @pytest.mark.asyncio
    async def test_resolve_with_field_selection(self) -> None:
        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        request = GraphQLRequest(
            queries=[
                QueryField(
                    name="investigations",
                    fields=["investigation_id", "severity"],
                ),
            ]
        )
        response = await resolver.resolve(request)
        items = response.data["investigations"]
        assert len(items) == 2
        # Only selected fields should be present
        for item in items:
            assert "investigation_id" in item
            assert "severity" in item
            assert "alert_name" not in item

    @pytest.mark.asyncio
    async def test_resolve_single_investigation(self) -> None:
        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        request = GraphQLRequest(
            queries=[
                QueryField(name="investigation", filters={"id": "inv-1"}),
            ]
        )
        response = await resolver.resolve(request)
        assert response.data["investigation"]["investigation_id"] == "inv-1"

    @pytest.mark.asyncio
    async def test_resolve_remediations(self) -> None:
        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        request = GraphQLRequest(
            queries=[
                QueryField(name="remediations"),
            ]
        )
        response = await resolver.resolve(request)
        assert len(response.data["remediations"]) == 1

    @pytest.mark.asyncio
    async def test_resolve_agents(self) -> None:
        resolver = QueryResolver()
        request = GraphQLRequest(
            queries=[
                QueryField(name="agents"),
            ]
        )
        response = await resolver.resolve(request)
        agents = response.data["agents"]
        assert len(agents) == 6
        types = [a["type"] for a in agents]
        assert "investigation" in types
        assert "supervisor" in types

    @pytest.mark.asyncio
    async def test_resolve_analytics(self) -> None:
        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        request = GraphQLRequest(
            queries=[
                QueryField(name="analytics_summary"),
            ]
        )
        response = await resolver.resolve(request)
        summary = response.data["analytics_summary"]
        assert summary["total_investigations"] == 42
        assert summary["total_remediations"] == 17

    @pytest.mark.asyncio
    async def test_unknown_query(self) -> None:
        resolver = QueryResolver()
        request = GraphQLRequest(
            queries=[
                QueryField(name="nonexistent"),
            ]
        )
        response = await resolver.resolve(request)
        assert len(response.errors) == 1
        assert "Unknown query" in response.errors[0]

    @pytest.mark.asyncio
    async def test_multiple_queries(self) -> None:
        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        request = GraphQLRequest(
            queries=[
                QueryField(name="investigations", limit=5),
                QueryField(name="agents"),
                QueryField(name="analytics_summary"),
            ]
        )
        response = await resolver.resolve(request)
        assert "investigations" in response.data
        assert "agents" in response.data
        assert "analytics_summary" in response.data
        assert response.errors == []

    @pytest.mark.asyncio
    async def test_no_repository(self) -> None:
        resolver = QueryResolver(repository=None)
        request = GraphQLRequest(
            queries=[
                QueryField(name="investigations"),
            ]
        )
        response = await resolver.resolve(request)
        assert response.data["investigations"] == []

    @pytest.mark.asyncio
    async def test_available_queries(self) -> None:
        resolver = QueryResolver()
        queries = resolver.available_queries
        assert "investigations" in queries
        assert "agents" in queries
        assert len(queries) >= 6

    @pytest.mark.asyncio
    async def test_filters_passed_to_repository(self) -> None:
        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        request = GraphQLRequest(
            queries=[
                QueryField(name="investigations", filters={"status": "completed"}),
            ]
        )
        await resolver.resolve(request)
        repo.list_investigations.assert_called_once_with(
            status="completed",
            limit=50,
            offset=0,
        )


class TestGraphQLRoutes:
    def test_query_endpoint(self) -> None:
        app = FastAPI()
        app.include_router(graphql_routes.router, prefix="/api/v1")
        app.dependency_overrides[get_current_user] = _mock_user

        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        graphql_routes.set_resolver(resolver)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/graphql",
            json={
                "queries": [
                    {"name": "investigations", "limit": 5},
                    {"name": "agents"},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "investigations" in data["data"]
        assert "agents" in data["data"]

    def test_schema_endpoint(self) -> None:
        app = FastAPI()
        app.include_router(graphql_routes.router, prefix="/api/v1")
        app.dependency_overrides[get_current_user] = _mock_user

        resolver = QueryResolver()
        graphql_routes.set_resolver(resolver)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/graphql/schema")
        assert resp.status_code == 200
        assert len(resp.json()["queries"]) >= 6

    def test_resolver_not_initialized(self) -> None:
        app = FastAPI()
        app.include_router(graphql_routes.router, prefix="/api/v1")
        app.dependency_overrides[get_current_user] = _mock_user

        original = graphql_routes._resolver
        graphql_routes._resolver = None

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/graphql", json={"queries": [{"name": "agents"}]})
        assert resp.status_code == 200
        assert "not initialized" in resp.json()["errors"][0]

        graphql_routes._resolver = original

    def test_field_selection_via_api(self) -> None:
        app = FastAPI()
        app.include_router(graphql_routes.router, prefix="/api/v1")
        app.dependency_overrides[get_current_user] = _mock_user

        repo = _mock_repository()
        resolver = QueryResolver(repository=repo)
        graphql_routes.set_resolver(resolver)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/graphql",
            json={
                "queries": [
                    {
                        "name": "investigations",
                        "fields": ["investigation_id"],
                    }
                ]
            },
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["investigations"]
        for item in items:
            assert "investigation_id" in item
            assert "alert_name" not in item
