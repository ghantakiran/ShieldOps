"""Tests for shieldops.api.exceptions module.

Covers ShieldOpsError base class and all subclasses, to_problem_detail() RFC 7807
serialization, error_context context manager, shieldops_exception_handler, and
register_exception_handlers.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.testclient import TestClient

from shieldops.api.exceptions import (
    AuthenticationError,
    CircuitOpenError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    PolicyDeniedError,
    RateLimitError,
    ShieldOpsError,
    ValidationError,
    error_context,
    register_exception_handlers,
    shieldops_exception_handler,
)

# ---------------------------------------------------------------------------
# ShieldOpsError base class
# ---------------------------------------------------------------------------


class TestShieldOpsErrorBase:
    """Tests for the ShieldOpsError base exception."""

    def test_default_status_code(self) -> None:
        assert ShieldOpsError.status_code == 500

    def test_default_error_type(self) -> None:
        assert ShieldOpsError.error_type == "about:blank"

    def test_default_title(self) -> None:
        assert ShieldOpsError.title == "Internal Server Error"

    def test_default_detail_is_title(self) -> None:
        err = ShieldOpsError()
        assert err.detail == "Internal Server Error"

    def test_custom_detail(self) -> None:
        err = ShieldOpsError("Something went wrong")
        assert err.detail == "Something went wrong"

    def test_instance_field(self) -> None:
        err = ShieldOpsError("err", instance="/api/v1/agents/123")
        assert err.instance == "/api/v1/agents/123"

    def test_default_instance_is_empty(self) -> None:
        err = ShieldOpsError("err")
        assert err.instance == ""

    def test_extra_fields(self) -> None:
        err = ShieldOpsError("err", extra={"agent_id": "abc"})
        assert err.extra == {"agent_id": "abc"}

    def test_default_extra_is_empty_dict(self) -> None:
        err = ShieldOpsError("err")
        assert err.extra == {}

    def test_is_exception(self) -> None:
        err = ShieldOpsError("err")
        assert isinstance(err, Exception)

    def test_str_representation(self) -> None:
        err = ShieldOpsError("custom message")
        assert str(err) == "custom message"


# ---------------------------------------------------------------------------
# to_problem_detail() — RFC 7807 format
# ---------------------------------------------------------------------------


class TestToProblemDetail:
    """Tests for the to_problem_detail() serialization."""

    def test_required_rfc7807_fields(self) -> None:
        err = ShieldOpsError("Something broke")
        body = err.to_problem_detail()
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body

    def test_type_field(self) -> None:
        err = ShieldOpsError("err")
        assert err.to_problem_detail()["type"] == "about:blank"

    def test_title_field(self) -> None:
        err = ShieldOpsError("err")
        assert err.to_problem_detail()["title"] == "Internal Server Error"

    def test_status_field(self) -> None:
        err = ShieldOpsError("err")
        assert err.to_problem_detail()["status"] == 500

    def test_detail_field(self) -> None:
        err = ShieldOpsError("custom detail")
        assert err.to_problem_detail()["detail"] == "custom detail"

    def test_instance_included_when_set(self) -> None:
        err = ShieldOpsError("err", instance="/api/v1/foo/bar")
        body = err.to_problem_detail()
        assert body["instance"] == "/api/v1/foo/bar"

    def test_instance_excluded_when_empty(self) -> None:
        err = ShieldOpsError("err")
        body = err.to_problem_detail()
        assert "instance" not in body

    def test_extra_fields_merged_into_body(self) -> None:
        err = ShieldOpsError("err", extra={"agent_id": "abc", "severity": "critical"})
        body = err.to_problem_detail()
        assert body["agent_id"] == "abc"
        assert body["severity"] == "critical"

    def test_extra_empty_does_not_add_fields(self) -> None:
        err = ShieldOpsError("err")
        body = err.to_problem_detail()
        # Only the 4 standard fields should be present
        assert set(body.keys()) == {"type", "title", "status", "detail"}


# ---------------------------------------------------------------------------
# Exception subclasses — status codes, error types, titles
# ---------------------------------------------------------------------------


_SUBCLASS_SPECS: list[tuple[type[ShieldOpsError], int, str, str]] = [
    (NotFoundError, 404, "urn:shieldops:error:not-found", "Not Found"),
    (ConflictError, 409, "urn:shieldops:error:conflict", "Conflict"),
    (ValidationError, 422, "urn:shieldops:error:validation", "Validation Error"),
    (PolicyDeniedError, 403, "urn:shieldops:error:policy-denied", "Policy Denied"),
    (RateLimitError, 429, "urn:shieldops:error:rate-limit", "Rate Limit Exceeded"),
    (CircuitOpenError, 503, "urn:shieldops:error:circuit-open", "Circuit Open"),
    (ExternalServiceError, 502, "urn:shieldops:error:external-service", "External Service Error"),
    (AuthenticationError, 401, "urn:shieldops:error:authentication", "Authentication Required"),
]


class TestExceptionSubclasses:
    """Tests for each ShieldOpsError subclass."""

    @pytest.mark.parametrize(
        "cls,expected_status,expected_type,expected_title",
        _SUBCLASS_SPECS,
        ids=[c[0].__name__ for c in _SUBCLASS_SPECS],
    )
    def test_status_code(
        self,
        cls: type[ShieldOpsError],
        expected_status: int,
        expected_type: str,
        expected_title: str,
    ) -> None:
        assert cls.status_code == expected_status

    @pytest.mark.parametrize(
        "cls,expected_status,expected_type,expected_title",
        _SUBCLASS_SPECS,
        ids=[c[0].__name__ for c in _SUBCLASS_SPECS],
    )
    def test_error_type(
        self,
        cls: type[ShieldOpsError],
        expected_status: int,
        expected_type: str,
        expected_title: str,
    ) -> None:
        assert cls.error_type == expected_type

    @pytest.mark.parametrize(
        "cls,expected_status,expected_type,expected_title",
        _SUBCLASS_SPECS,
        ids=[c[0].__name__ for c in _SUBCLASS_SPECS],
    )
    def test_title(
        self,
        cls: type[ShieldOpsError],
        expected_status: int,
        expected_type: str,
        expected_title: str,
    ) -> None:
        assert cls.title == expected_title

    @pytest.mark.parametrize(
        "cls,expected_status,expected_type,expected_title",
        _SUBCLASS_SPECS,
        ids=[c[0].__name__ for c in _SUBCLASS_SPECS],
    )
    def test_is_shieldops_error(
        self,
        cls: type[ShieldOpsError],
        expected_status: int,
        expected_type: str,
        expected_title: str,
    ) -> None:
        err = cls("test detail")
        assert isinstance(err, ShieldOpsError)

    @pytest.mark.parametrize(
        "cls,expected_status,expected_type,expected_title",
        _SUBCLASS_SPECS,
        ids=[c[0].__name__ for c in _SUBCLASS_SPECS],
    )
    def test_to_problem_detail_status_matches(
        self,
        cls: type[ShieldOpsError],
        expected_status: int,
        expected_type: str,
        expected_title: str,
    ) -> None:
        err = cls("test")
        body = err.to_problem_detail()
        assert body["status"] == expected_status
        assert body["type"] == expected_type
        assert body["title"] == expected_title

    def test_not_found_with_detail(self) -> None:
        err = NotFoundError("Agent not found", instance="/api/v1/agents/xyz")
        body = err.to_problem_detail()
        assert body["detail"] == "Agent not found"
        assert body["instance"] == "/api/v1/agents/xyz"

    def test_policy_denied_with_extra(self) -> None:
        err = PolicyDeniedError(
            "Blast radius exceeded",
            extra={"policy": "max_replicas", "limit": 10},
        )
        body = err.to_problem_detail()
        assert body["policy"] == "max_replicas"
        assert body["limit"] == 10

    def test_validation_error_default_detail_is_title(self) -> None:
        err = ValidationError()
        assert err.detail == "Validation Error"

    def test_authentication_error_default_detail_is_title(self) -> None:
        err = AuthenticationError()
        assert err.detail == "Authentication Required"


# ---------------------------------------------------------------------------
# error_context context manager
# ---------------------------------------------------------------------------


class TestErrorContext:
    """Tests for the error_context context manager."""

    def test_no_exception_passes_through(self) -> None:
        with error_context(ExternalServiceError, detail="should not appear"):
            result = 1 + 1
        assert result == 2

    def test_wraps_generic_exception(self) -> None:
        with (
            pytest.raises(ExternalServiceError) as exc_info,
            error_context(ExternalServiceError, detail="OPA call failed"),
        ):
            raise ConnectionError("connection refused")
        assert "OPA call failed" in str(exc_info.value)

    def test_wrapped_exception_has_correct_type(self) -> None:
        with pytest.raises(NotFoundError), error_context(NotFoundError, detail="missing"):
            raise KeyError("not found")

    def test_shieldops_error_passes_through_unchanged(self) -> None:
        original = NotFoundError("original message", instance="/api/v1/agents/abc")
        with (
            pytest.raises(NotFoundError) as exc_info,
            error_context(ExternalServiceError, detail="should not wrap"),
        ):
            raise original
        assert exc_info.value is original
        assert exc_info.value.detail == "original message"

    def test_shieldops_subclass_passes_through(self) -> None:
        """Any ShieldOpsError subclass should pass through without wrapping."""
        original = PolicyDeniedError("denied by OPA")
        with pytest.raises(PolicyDeniedError) as exc_info, error_context(ExternalServiceError):
            raise original
        assert exc_info.value is original

    def test_uses_exception_str_when_no_detail(self) -> None:
        with pytest.raises(ExternalServiceError) as exc_info, error_context(ExternalServiceError):
            raise RuntimeError("underlying error message")
        assert "underlying error message" in str(exc_info.value)

    def test_preserves_exception_chain(self) -> None:
        with (
            pytest.raises(ExternalServiceError) as exc_info,
            error_context(ExternalServiceError, detail="wrapped"),
        ):
            raise ValueError("root cause")
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_kwargs_forwarded_to_exception(self) -> None:
        with (
            pytest.raises(ExternalServiceError) as exc_info,
            error_context(
                ExternalServiceError,
                detail="call failed",
                instance="/api/v1/opa",
                extra={"service": "opa"},
            ),
        ):
            raise RuntimeError("timeout")
        assert exc_info.value.instance == "/api/v1/opa"
        assert exc_info.value.extra == {"service": "opa"}


# ---------------------------------------------------------------------------
# shieldops_exception_handler
# ---------------------------------------------------------------------------


class TestShieldopsExceptionHandler:
    """Tests for the shieldops_exception_handler function."""

    def _make_request(self) -> Request:
        """Create a minimal mock request for testing the handler."""
        scope = {"type": "http", "method": "GET", "path": "/test"}
        return Request(scope=scope)

    def test_returns_json_response(self) -> None:
        err = NotFoundError("Agent not found")
        resp = shieldops_exception_handler(self._make_request(), err)
        assert resp.status_code == 404

    def test_response_body_is_problem_detail(self) -> None:
        err = NotFoundError("Agent not found", instance="/api/v1/agents/xyz")
        resp = shieldops_exception_handler(self._make_request(), err)
        body = resp.body.decode()
        import json

        data = json.loads(body)
        assert data["type"] == "urn:shieldops:error:not-found"
        assert data["title"] == "Not Found"
        assert data["status"] == 404
        assert data["detail"] == "Agent not found"
        assert data["instance"] == "/api/v1/agents/xyz"

    def test_content_type_is_problem_json(self) -> None:
        err = ShieldOpsError("err")
        resp = shieldops_exception_handler(self._make_request(), err)
        assert resp.media_type == "application/problem+json"

    def test_handler_with_each_subclass(self) -> None:
        for cls, expected_status, _, _ in _SUBCLASS_SPECS:
            err = cls("test detail")
            resp = shieldops_exception_handler(self._make_request(), err)
            assert resp.status_code == expected_status

    def test_handler_includes_extra_fields(self) -> None:
        err = PolicyDeniedError(
            "Denied", extra={"policy_id": "max-replicas", "environment": "prod"}
        )
        resp = shieldops_exception_handler(self._make_request(), err)
        import json

        data = json.loads(resp.body.decode())
        assert data["policy_id"] == "max-replicas"
        assert data["environment"] == "prod"


# ---------------------------------------------------------------------------
# register_exception_handlers
# ---------------------------------------------------------------------------


class TestRegisterExceptionHandlers:
    """Tests for the register_exception_handlers function."""

    def test_registers_handler_on_app(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        # The handler should be registered — we verify by checking the
        # exception_handlers dict
        assert ShieldOpsError in app.exception_handlers

    def test_end_to_end_not_found(self) -> None:
        """Integration test: a route raising NotFoundError returns 404 problem detail."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/agents/{agent_id}")
        async def get_agent(agent_id: str) -> dict:
            raise NotFoundError(
                f"Agent {agent_id} not found",
                instance=f"/api/v1/agents/{agent_id}",
            )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/agents/xyz")
        assert resp.status_code == 404
        data = resp.json()
        assert data["type"] == "urn:shieldops:error:not-found"
        assert data["detail"] == "Agent xyz not found"

    def test_end_to_end_policy_denied(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/actions")
        async def create_action() -> dict:
            raise PolicyDeniedError("Blast radius exceeded")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/actions")
        assert resp.status_code == 403
        assert resp.json()["title"] == "Policy Denied"

    def test_end_to_end_rate_limit(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/limited")
        async def limited() -> dict:
            raise RateLimitError("Too many requests")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/limited")
        assert resp.status_code == 429

    def test_end_to_end_conflict(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/resources")
        async def create_resource() -> dict:
            raise ConflictError("Resource already exists", extra={"resource_id": "abc"})

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/resources")
        assert resp.status_code == 409
        assert resp.json()["resource_id"] == "abc"

    def test_end_to_end_authentication_error(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/secure")
        async def secure() -> dict:
            raise AuthenticationError("Token expired")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/secure")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Token expired"
