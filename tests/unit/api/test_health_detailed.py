"""Tests for GET /api/v1/health/detailed endpoint."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shieldops.api.app import app


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_healthy_sf() -> MagicMock:
    """Return a session_factory mock that executes SELECT."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = "PostgreSQL 15.4"
    session.execute = AsyncMock(return_value=result)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    sf = MagicMock(return_value=ctx)
    return sf


def _make_failing_sf() -> MagicMock:
    """Return a session_factory mock whose execute raises."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=ConnectionError("DB connection refused"))
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    sf = MagicMock(return_value=ctx)
    return sf


# ── Tests ────────────────────────────────────────────────────────────


class TestDetailedHealth:
    """Tests for the /health/detailed endpoint."""

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_all_healthy(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """When all checks pass, overall status is healthy."""
        mock_db.return_value = {
            "status": "healthy",
            "latency_ms": 3.2,
            "details": "PostgreSQL 15.4",
        }
        mock_redis.return_value = {
            "status": "healthy",
            "latency_ms": 1.0,
            "details": "Redis 7.2",
        }
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }
        mock_opa.return_value = {
            "status": "healthy",
            "latency_ms": 5.1,
            "details": "OPA at http://localhost:8181",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["checks"]["database"]["status"] == "healthy"
        assert data["checks"]["redis"]["status"] == "healthy"

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_database_down_returns_unhealthy(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """When database is down, overall status is unhealthy."""
        mock_db.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "Connection refused",
        }
        mock_redis.return_value = {
            "status": "healthy",
            "latency_ms": 1.0,
            "details": "Redis 7.2",
        }
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }
        mock_opa.return_value = {
            "status": "healthy",
            "latency_ms": 5.1,
            "details": "OPA at http://localhost:8181",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "unhealthy"
        assert "error" in data["checks"]["database"]

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_redis_down_returns_degraded(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """When Redis is down but DB is healthy, status is degraded."""
        mock_db.return_value = {
            "status": "healthy",
            "latency_ms": 3.2,
            "details": "PostgreSQL 15.4",
        }
        mock_redis.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "Redis connection refused",
        }
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }
        mock_opa.return_value = {
            "status": "healthy",
            "latency_ms": 5.1,
            "details": "OPA at http://localhost:8181",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["redis"]["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "healthy"

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_multiple_failures_with_db_down(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """When DB and other services fail, status is unhealthy."""
        mock_db.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "DB timeout",
        }
        mock_redis.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "Redis timeout",
        }
        mock_kafka.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "Kafka timeout",
        }
        mock_opa.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "OPA timeout",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unhealthy"

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_timeout_handling(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """When a check times out, it returns unhealthy via exception."""

        async def slow_check(_request: Any) -> dict[str, Any]:
            await asyncio.sleep(10)
            return {"status": "healthy", "latency_ms": 0}

        mock_db.side_effect = slow_check
        mock_redis.return_value = {
            "status": "healthy",
            "latency_ms": 1.0,
            "details": "Redis 7.2",
        }
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }
        mock_opa.return_value = {
            "status": "healthy",
            "latency_ms": 5.1,
            "details": "OPA at http://localhost:8181",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        # DB timed out -> exception -> unhealthy overall
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "unhealthy"
        assert "TimeoutError" in (data["checks"]["database"].get("error", "")) or "asyncio" in (
            data["checks"]["database"].get("error", "")
        )

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_response_structure(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """Validate the response JSON structure."""
        for mock in (mock_db, mock_redis, mock_kafka, mock_opa):
            mock.return_value = {
                "status": "healthy",
                "latency_ms": 1.0,
                "details": "OK",
            }

        resp = client.get("/api/v1/health/detailed")
        data = resp.json()

        # Top-level keys
        assert set(data.keys()) == {
            "status",
            "timestamp",
            "checks",
            "uptime_seconds",
        }

        # Status enum values
        assert data["status"] in ("healthy", "degraded", "unhealthy")

        # Timestamp is ISO format
        assert "T" in data["timestamp"]

        # Checks contains all 4 dependencies
        assert set(data["checks"].keys()) == {
            "database",
            "redis",
            "kafka",
            "opa",
        }

        # Each check has required fields
        for check_name, check_data in data["checks"].items():
            assert "status" in check_data, f"{check_name} missing status"
            assert check_data["status"] in (
                "healthy",
                "unhealthy",
            )
            assert "latency_ms" in check_data, f"{check_name} missing latency_ms"

        # Uptime is positive
        assert data["uptime_seconds"] >= 0

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_latency_values_present(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """Healthy checks include numeric latency_ms."""
        mock_db.return_value = {
            "status": "healthy",
            "latency_ms": 5.2,
            "details": "PostgreSQL 15.4",
        }
        mock_redis.return_value = {
            "status": "healthy",
            "latency_ms": 1.1,
            "details": "Redis 7.2",
        }
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": 2.3,
            "details": "Kafka OK",
        }
        mock_opa.return_value = {
            "status": "healthy",
            "latency_ms": 8.3,
            "details": "OPA OK",
        }

        resp = client.get("/api/v1/health/detailed")
        data = resp.json()

        assert data["checks"]["database"]["latency_ms"] == 5.2
        assert data["checks"]["redis"]["latency_ms"] == 1.1
        assert data["checks"]["kafka"]["latency_ms"] == 2.3
        assert data["checks"]["opa"]["latency_ms"] == 8.3

    def test_authentication_required(self):
        """Without auth override, endpoint requires authentication."""
        from shieldops.api.auth.dependencies import get_current_user

        # Temporarily remove the auth override
        original = app.dependency_overrides.get(get_current_user)
        app.dependency_overrides.pop(get_current_user, None)
        try:
            no_auth_client = TestClient(app, raise_server_exceptions=False)
            resp = no_auth_client.get("/api/v1/health/detailed")
            # Should be 401 or 403 without valid credentials
            assert resp.status_code in (401, 403)
        finally:
            if original is not None:
                app.dependency_overrides[get_current_user] = original

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_uptime_is_positive(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """Uptime should be a positive number."""
        for mock in (mock_db, mock_redis, mock_kafka, mock_opa):
            mock.return_value = {
                "status": "healthy",
                "latency_ms": 1.0,
                "details": "OK",
            }

        resp = client.get("/api/v1/health/detailed")
        data = resp.json()
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] > 0

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_exception_in_check_becomes_unhealthy(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """An unhandled exception in a check is caught and reported."""
        mock_db.return_value = {
            "status": "healthy",
            "latency_ms": 3.0,
            "details": "PostgreSQL 15.4",
        }
        mock_redis.side_effect = RuntimeError("Unexpected redis failure")
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }
        mock_opa.return_value = {
            "status": "healthy",
            "latency_ms": 5.0,
            "details": "OPA OK",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        redis_check = data["checks"]["redis"]
        assert redis_check["status"] == "unhealthy"
        assert "RuntimeError" in redis_check["error"]
        assert "Unexpected redis failure" in redis_check["error"]

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_opa_down_returns_degraded(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """When OPA is down but DB is healthy, status is degraded."""
        mock_db.return_value = {
            "status": "healthy",
            "latency_ms": 3.0,
            "details": "PostgreSQL 15.4",
        }
        mock_redis.return_value = {
            "status": "healthy",
            "latency_ms": 1.0,
            "details": "Redis 7.2",
        }
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }
        mock_opa.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": "OPA returned status 503",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["opa"]["status"] == "unhealthy"

    @patch("shieldops.api.routes.health._check_opa")
    @patch("shieldops.api.routes.health._check_kafka")
    @patch("shieldops.api.routes.health._check_redis")
    @patch("shieldops.api.routes.health._check_database")
    def test_kafka_skipped_still_healthy(
        self,
        mock_db: AsyncMock,
        mock_redis: AsyncMock,
        mock_kafka: AsyncMock,
        mock_opa: AsyncMock,
        client: TestClient,
    ):
        """Kafka not configured should not degrade overall status."""
        mock_db.return_value = {
            "status": "healthy",
            "latency_ms": 3.0,
            "details": "PostgreSQL 15.4",
        }
        mock_redis.return_value = {
            "status": "healthy",
            "latency_ms": 1.0,
            "details": "Redis 7.2",
        }
        mock_kafka.return_value = {
            "status": "healthy",
            "latency_ms": None,
            "details": "Kafka not configured (skipped)",
        }
        mock_opa.return_value = {
            "status": "healthy",
            "latency_ms": 5.0,
            "details": "OPA OK",
        }

        resp = client.get("/api/v1/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["checks"]["kafka"]["latency_ms"] is None
        assert "skipped" in data["checks"]["kafka"]["details"]

    def test_basic_health_still_works(self, client: TestClient):
        """The existing /health endpoint is not broken."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestSafeResult:
    """Unit tests for the _safe_result helper."""

    def test_returns_dict_as_is(self):
        from shieldops.api.routes.health import _safe_result

        result: dict[str, Any] = {
            "status": "healthy",
            "latency_ms": 1.0,
        }
        assert _safe_result("test", result) == result

    def test_converts_exception_to_unhealthy(self):
        from shieldops.api.routes.health import _safe_result

        exc = ConnectionError("host unreachable")
        result = _safe_result("db", exc)
        assert result["status"] == "unhealthy"
        assert result["latency_ms"] is None
        assert "ConnectionError" in result["error"]
        assert "host unreachable" in result["error"]

    def test_converts_timeout_to_unhealthy(self):
        from shieldops.api.routes.health import _safe_result

        exc = TimeoutError()
        result = _safe_result("redis", exc)
        assert result["status"] == "unhealthy"
        assert "TimeoutError" in result["error"]
