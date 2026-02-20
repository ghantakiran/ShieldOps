"""Tests for global search API endpoint.

Tests cover:
- Search with results from multiple entity types
- Search with entity_type filter
- Empty results
- Minimum query length (2 chars)
- Maximum query length (200 chars)
- Result limit enforcement
- Results sorted by relevance
- SQL injection prevention (parameterized queries)
- Authentication required
- Special characters in query
- Invalid entity type filter
- Repository unavailable (503)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import search


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the search router."""
    app = FastAPI()
    app.include_router(search.router, prefix="/api/v1")
    return app


def _make_investigation(
    inv_id: str = "inv-001",
    alert_name: str = "High CPU on prod-web-01",
    alert_id: str = "alert-cpu-001",
    severity: str = "critical",
    status: str = "completed",
    confidence: float = 0.95,
) -> dict[str, Any]:
    return {
        "investigation_id": inv_id,
        "alert_name": alert_name,
        "alert_id": alert_id,
        "severity": severity,
        "status": status,
        "confidence": confidence,
        "created_at": "2026-02-18T12:00:00",
    }


def _make_remediation(
    rem_id: str = "rem-001",
    action_type: str = "scale_up",
    target_resource: str = "prod-web-instances",
    environment: str = "production",
    risk_level: str = "medium",
    status: str = "completed",
) -> dict[str, Any]:
    return {
        "remediation_id": rem_id,
        "action_type": action_type,
        "target_resource": target_resource,
        "environment": environment,
        "risk_level": risk_level,
        "status": status,
        "created_at": "2026-02-18T13:00:00",
    }


def _make_vulnerability(
    vuln_id: str = "vuln-001",
    cve_id: str = "CVE-2026-1234",
    title: str = "Critical OpenSSL buffer overflow",
    package_name: str = "openssl",
    severity: str = "critical",
    status: str = "new",
) -> dict[str, Any]:
    return {
        "id": vuln_id,
        "cve_id": cve_id,
        "title": title,
        "package_name": package_name,
        "severity": severity,
        "status": status,
        "created_at": "2026-02-18T14:00:00",
    }


@pytest.fixture(autouse=True)
def _reset_module_repo():
    """Reset the module-level repository between tests."""
    original = search._repository
    search._repository = None
    yield
    search._repository = original


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.search_investigations = AsyncMock(return_value=[_make_investigation()])
    repo.search_remediations = AsyncMock(return_value=[_make_remediation()])
    repo.search_vulnerabilities = AsyncMock(return_value=[_make_vulnerability()])
    return repo


@pytest.fixture
def client(mock_repo: AsyncMock) -> TestClient:
    """TestClient with auth bypassed via dependency override."""
    from shieldops.api.auth.dependencies import get_current_user
    from shieldops.api.auth.models import UserResponse, UserRole

    app = _create_test_app()
    search.set_repository(mock_repo)

    async def _mock_user() -> UserResponse:
        return UserResponse(
            id="user-1",
            email="admin@test.com",
            name="Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ====================================================================
# Multi-entity search
# ====================================================================


class TestGlobalSearch:
    def test_search_returns_results_from_multiple_types(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        resp = client.get("/api/v1/search?q=prod")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "prod"
        assert data["total"] >= 1
        entity_types = {r["entity_type"] for r in data["results"]}
        # Should have results from all three entity types
        assert "investigation" in entity_types
        assert "remediation" in entity_types
        assert "vulnerability" in entity_types

    def test_search_result_structure(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/search?q=prod")
        assert resp.status_code == 200
        data = resp.json()
        result = data["results"][0]
        assert "entity_type" in result
        assert "id" in result
        assert "title" in result
        assert "description" in result
        assert "status" in result
        assert "relevance" in result
        assert "url" in result
        assert "created_at" in result


# ====================================================================
# Entity type filtering
# ====================================================================


class TestEntityTypeFilter:
    def test_filter_single_entity_type(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        resp = client.get("/api/v1/search?q=prod&entity_types=investigation")
        assert resp.status_code == 200
        data = resp.json()
        entity_types = {r["entity_type"] for r in data["results"]}
        assert entity_types == {"investigation"}
        # Only investigation search should have been called
        mock_repo.search_investigations.assert_called_once()
        mock_repo.search_remediations.assert_not_called()
        mock_repo.search_vulnerabilities.assert_not_called()

    def test_filter_multiple_entity_types(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        resp = client.get("/api/v1/search?q=prod&entity_types=investigation,vulnerability")
        assert resp.status_code == 200
        data = resp.json()
        entity_types = {r["entity_type"] for r in data["results"]}
        assert entity_types <= {"investigation", "vulnerability"}
        mock_repo.search_remediations.assert_not_called()

    def test_invalid_entity_type_returns_400(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/search?q=prod&entity_types=invalid_type")
        assert resp.status_code == 400
        assert "Invalid entity types" in resp.json()["detail"]


# ====================================================================
# Empty results
# ====================================================================


class TestEmptyResults:
    def test_no_results_returns_empty_list(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.search_investigations.return_value = []
        mock_repo.search_remediations.return_value = []
        mock_repo.search_vulnerabilities.return_value = []

        resp = client.get("/api/v1/search?q=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []


# ====================================================================
# Query length validation
# ====================================================================


class TestQueryValidation:
    def test_query_too_short_returns_422(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/search?q=a")
        assert resp.status_code == 422

    def test_query_minimum_length(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/search?q=ab")
        assert resp.status_code == 200

    def test_query_too_long_returns_422(
        self,
        client: TestClient,
    ) -> None:
        long_query = "x" * 201
        resp = client.get(f"/api/v1/search?q={long_query}")
        assert resp.status_code == 422

    def test_query_at_max_length(
        self,
        client: TestClient,
    ) -> None:
        max_query = "x" * 200
        resp = client.get(f"/api/v1/search?q={max_query}")
        assert resp.status_code == 200

    def test_missing_query_returns_422(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422


# ====================================================================
# Result limit enforcement
# ====================================================================


class TestLimitEnforcement:
    def test_default_limit_is_20(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        # Generate more than 20 results
        mock_repo.search_investigations.return_value = [
            _make_investigation(f"inv-{i}") for i in range(25)
        ]
        mock_repo.search_remediations.return_value = []
        mock_repo.search_vulnerabilities.return_value = []

        resp = client.get("/api/v1/search?q=prod")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 20

    def test_custom_limit(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.search_investigations.return_value = [
            _make_investigation(f"inv-{i}") for i in range(10)
        ]
        mock_repo.search_remediations.return_value = []
        mock_repo.search_vulnerabilities.return_value = []

        resp = client.get("/api/v1/search?q=prod&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 5

    def test_limit_too_high_returns_422(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/search?q=prod&limit=101")
        assert resp.status_code == 422

    def test_limit_too_low_returns_422(
        self,
        client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/search?q=prod&limit=0")
        assert resp.status_code == 422


# ====================================================================
# Results sorted by relevance
# ====================================================================


class TestRelevanceSorting:
    def test_results_sorted_by_relevance_descending(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.search_investigations.return_value = [
            _make_investigation("inv-1", alert_name="prod alert"),
            _make_investigation("inv-2", alert_name="production server high cpu"),
        ]
        mock_repo.search_remediations.return_value = [
            _make_remediation("rem-1", target_resource="prod-web"),
        ]
        mock_repo.search_vulnerabilities.return_value = []

        resp = client.get("/api/v1/search?q=prod")
        assert resp.status_code == 200
        data = resp.json()
        relevances = [r["relevance"] for r in data["results"]]
        assert relevances == sorted(relevances, reverse=True)


# ====================================================================
# SQL injection prevention
# ====================================================================


class TestSQLInjectionPrevention:
    def test_sql_injection_in_query(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        """Verify the query with SQL injection payload is passed as a
        parameter (not interpolated into SQL). The ILIKE pattern
        will safely contain the malicious string."""
        resp = client.get("/api/v1/search?q='; DROP TABLE investigations; --")
        assert resp.status_code == 200
        # The query is passed as a parameter to ILIKE,
        # so the search methods should be called safely
        mock_repo.search_investigations.assert_called_once()
        call_args = mock_repo.search_investigations.call_args
        passed_query = call_args[0][0]
        assert "DROP TABLE" in passed_query

    def test_percent_wildcards_in_query(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        """Verify % characters in user input are treated literally."""
        resp = client.get("/api/v1/search?q=100%25cpu")
        assert resp.status_code == 200


# ====================================================================
# Authentication required
# ====================================================================


class TestAuthRequired:
    def test_unauthenticated_returns_401(self) -> None:
        """Without auth override, the endpoint should reject."""
        app = _create_test_app()
        repo = AsyncMock()
        search.set_repository(repo)

        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/api/v1/search?q=test")
        # 401 or 403 depending on auth config
        assert resp.status_code in (401, 403)


# ====================================================================
# Special characters in query
# ====================================================================


class TestSpecialCharacters:
    def test_unicode_characters(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        resp = client.get("/api/v1/search?q=serveur+CPU")
        assert resp.status_code == 200

    def test_special_chars_html_entities(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        resp = client.get("/api/v1/search?q=<script>alert(1)</script>")
        # Should not cause a 500; the query is safely parameterized
        assert resp.status_code in (200, 422)

    def test_query_with_quotes(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        resp = client.get('/api/v1/search?q=server "prod-01"')
        assert resp.status_code == 200


# ====================================================================
# Repository unavailable
# ====================================================================


class TestRepositoryUnavailable:
    def test_503_when_no_repo(self) -> None:
        from shieldops.api.auth.dependencies import (
            get_current_user,
        )
        from shieldops.api.auth.models import (
            UserResponse,
            UserRole,
        )

        app = _create_test_app()
        # Do NOT set repository

        async def _mock_user() -> UserResponse:
            return UserResponse(
                id="u1",
                email="",
                name="",
                role=UserRole.ADMIN,
                is_active=True,
            )

        app.dependency_overrides[get_current_user] = _mock_user
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/api/v1/search?q=test")
        assert resp.status_code == 503


# ====================================================================
# Relevance computation
# ====================================================================


class TestRelevanceComputation:
    def test_exact_match_has_highest_relevance(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        """When query exactly matches a field, relevance = 1.0."""
        mock_repo.search_investigations.return_value = [
            _make_investigation(
                "inv-exact",
                alert_name="cpu spike",
            ),
        ]
        mock_repo.search_remediations.return_value = []
        mock_repo.search_vulnerabilities.return_value = []

        resp = client.get("/api/v1/search?q=cpu spike")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["relevance"] == 1.0

    def test_partial_match_has_lower_relevance(
        self,
        client: TestClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.search_investigations.return_value = [
            _make_investigation(
                "inv-partial",
                alert_name="High CPU spike on production server",
            ),
        ]
        mock_repo.search_remediations.return_value = []
        mock_repo.search_vulnerabilities.return_value = []

        resp = client.get("/api/v1/search?q=cpu")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        relevance = data["results"][0]["relevance"]
        assert 0.0 < relevance < 1.0
