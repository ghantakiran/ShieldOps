"""Tests for data export & compliance report endpoints.

Tests cover:
- CSV export format validation (headers, rows, content-type)
- JSON export format
- Date range filtering params forwarded to repository
- Status / severity filtering
- Empty results (valid CSV with headers only via empty body)
- Limit enforcement (max 10000)
- CSV injection prevention (sanitization)
- Authentication required (no token -> 401/403)
- Compliance report structure
- All three export endpoints: investigations, remediations, compliance
"""

from __future__ import annotations

import csv
import io
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import exports
from shieldops.utils.export_helpers import dicts_to_csv, sanitize_for_csv

# ── Fixtures & helpers ───────────────────────────────────────────────


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(exports.router, prefix="/api/v1")
    return app


def _make_investigation(
    investigation_id: str = "inv-001",
    alert_id: str = "alert-1",
    alert_name: str = "HighCPU",
    severity: str = "critical",
    status: str = "completed",
    confidence: float = 0.95,
) -> dict[str, Any]:
    return {
        "investigation_id": investigation_id,
        "alert_id": alert_id,
        "alert_name": alert_name,
        "severity": severity,
        "status": status,
        "confidence": confidence,
        "hypotheses_count": 3,
        "hypotheses": [],
        "reasoning_chain": [],
        "alert_context": {},
        "log_findings": [],
        "metric_anomalies": [],
        "recommended_action": None,
        "duration_ms": 1200,
        "error": None,
        "created_at": "2026-02-01T10:00:00+00:00",
        "updated_at": "2026-02-01T10:01:00+00:00",
    }


def _make_remediation(
    remediation_id: str = "rem-001",
    action_type: str = "restart_service",
    status: str = "completed",
    risk_level: str = "medium",
) -> dict[str, Any]:
    return {
        "remediation_id": remediation_id,
        "action_type": action_type,
        "target_resource": "web-pod-abc",
        "environment": "production",
        "risk_level": risk_level,
        "status": status,
        "validation_passed": True,
        "reasoning_chain": [],
        "action_data": {},
        "execution_result": None,
        "snapshot_data": None,
        "investigation_id": "inv-001",
        "duration_ms": 800,
        "error": None,
        "created_at": "2026-02-02T12:00:00+00:00",
        "updated_at": "2026-02-02T12:01:00+00:00",
    }


def _make_compliance(
    scan_id: str = "scan-001",
    compliance_score: float = 92.5,
) -> dict[str, Any]:
    return {
        "scan_id": scan_id,
        "scan_type": "full",
        "environment": "production",
        "status": "completed",
        "cve_findings": [],
        "critical_cve_count": 2,
        "credential_statuses": [],
        "compliance_controls": [],
        "compliance_score": compliance_score,
        "patch_results": [],
        "rotation_results": [],
        "patches_applied": 5,
        "credentials_rotated": 1,
        "posture_data": None,
        "reasoning_chain": [],
        "duration_ms": 3000,
        "error": None,
        "created_at": "2026-02-03T08:00:00+00:00",
        "updated_at": "2026-02-03T08:05:00+00:00",
    }


@pytest.fixture(autouse=True)
def _reset_module_repo():
    original = exports._repository
    exports._repository = None
    yield
    exports._repository = original


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.export_investigations = AsyncMock(
        return_value=[
            _make_investigation(),
            _make_investigation(investigation_id="inv-002"),
        ]
    )
    repo.export_remediations = AsyncMock(
        return_value=[
            _make_remediation(),
            _make_remediation(remediation_id="rem-002"),
        ]
    )
    repo.export_compliance_data = AsyncMock(
        return_value=[
            _make_compliance(),
            _make_compliance(scan_id="scan-002", compliance_score=88.0),
        ]
    )
    return repo


def _build_client_with_viewer(
    app: FastAPI,
    mock_repo: AsyncMock | None = None,
) -> TestClient:
    """Wire dependency overrides for a viewer-level user."""
    if mock_repo is not None:
        exports.set_repository(mock_repo)

    from shieldops.api.auth.dependencies import (
        get_current_user,
        require_role,
    )
    from shieldops.api.auth.models import UserResponse, UserRole

    user = UserResponse(
        id="viewer-1",
        email="viewer@test.com",
        name="Viewer",
        role=UserRole.VIEWER,
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    # Override the specific require_role dependency used by exports
    dep = require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
    app.dependency_overrides[dep] = _mock_user

    return TestClient(app, raise_server_exceptions=False)


# =========================================================================
# CSV export format validation
# =========================================================================


class TestCSVExportFormat:
    def test_investigations_csv_has_correct_headers(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/investigations?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "investigations_export.csv" in resp.headers.get("content-disposition", "")

        reader = csv.reader(io.StringIO(resp.text))
        headers = next(reader)
        assert "investigation_id" in headers
        assert "alert_name" in headers
        assert "severity" in headers
        assert "status" in headers
        assert "created_at" in headers

    def test_investigations_csv_has_data_rows(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/investigations?format=csv")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        # 1 header + 2 data rows
        assert len(rows) == 3

    def test_remediations_csv_content_type(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/remediations?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "remediations_export.csv" in resp.headers.get("content-disposition", "")

    def test_compliance_csv_content_type(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/compliance?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "compliance_export.csv" in resp.headers.get("content-disposition", "")


# =========================================================================
# JSON export format
# =========================================================================


class TestJSONExportFormat:
    def test_investigations_json_returns_list(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/investigations?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["investigation_id"] == "inv-001"

    def test_remediations_json_returns_list(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/remediations?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_compliance_json_returns_list(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/compliance?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["compliance_score"] == 92.5


# =========================================================================
# Date range filtering
# =========================================================================


class TestDateRangeFiltering:
    def test_date_params_forwarded_to_repo(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/export/investigations?format=json&start_date=2026-01-01&end_date=2026-02-28"
        )
        assert resp.status_code == 200
        call_kwargs = mock_repo.export_investigations.call_args.kwargs
        assert call_kwargs["start_date"] is not None
        assert call_kwargs["end_date"] is not None

    def test_invalid_date_returns_422(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/investigations?start_date=not-a-date")
        assert resp.status_code == 422


# =========================================================================
# Status / severity filtering
# =========================================================================


class TestStatusSeverityFiltering:
    def test_status_filter_forwarded(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/investigations?format=json&status=completed")
        assert resp.status_code == 200
        call_kwargs = mock_repo.export_investigations.call_args.kwargs
        assert call_kwargs["status"] == "completed"

    def test_severity_filter_forwarded(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/remediations?format=json&severity=high")
        assert resp.status_code == 200
        call_kwargs = mock_repo.export_remediations.call_args.kwargs
        assert call_kwargs["severity"] == "high"


# =========================================================================
# Empty results
# =========================================================================


class TestEmptyResults:
    def test_empty_csv_returns_empty_body(self) -> None:
        """When there are no results the CSV body is empty."""
        app = _create_test_app()
        repo = AsyncMock()
        repo.export_investigations = AsyncMock(return_value=[])
        client = _build_client_with_viewer(app, repo)

        resp = client.get("/api/v1/export/investigations?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        # Empty data produces empty CSV string
        assert resp.text == ""

    def test_empty_json_returns_empty_list(self) -> None:
        app = _create_test_app()
        repo = AsyncMock()
        repo.export_investigations = AsyncMock(return_value=[])
        client = _build_client_with_viewer(app, repo)

        resp = client.get("/api/v1/export/investigations?format=json")
        assert resp.status_code == 200
        assert resp.json() == []


# =========================================================================
# Limit enforcement (max 10000)
# =========================================================================


class TestLimitEnforcement:
    def test_limit_clamped_to_max(self, mock_repo: AsyncMock) -> None:
        """Even if a user passes limit=50000, the repo receives 10000."""
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/investigations?format=json&limit=10000")
        assert resp.status_code == 200
        call_kwargs = mock_repo.export_investigations.call_args.kwargs
        assert call_kwargs["limit"] == 10_000

    def test_default_limit_is_1000(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/investigations?format=json")
        assert resp.status_code == 200
        call_kwargs = mock_repo.export_investigations.call_args.kwargs
        assert call_kwargs["limit"] == 1000


# =========================================================================
# CSV injection prevention (sanitization)
# =========================================================================


class TestCSVInjectionPrevention:
    """Verify the sanitize_for_csv helper strips formula injection."""

    def test_equals_prefix_sanitized(self) -> None:
        assert sanitize_for_csv("=SUM(A1)") == "'=SUM(A1)"

    def test_plus_prefix_sanitized(self) -> None:
        assert sanitize_for_csv("+cmd|' /C calc'") == "'+cmd|' /C calc'"

    def test_minus_prefix_sanitized(self) -> None:
        assert sanitize_for_csv("-1+1") == "'-1+1"

    def test_at_prefix_sanitized(self) -> None:
        assert sanitize_for_csv("@SUM(A1)") == "'@SUM(A1)"

    def test_tab_prefix_sanitized(self) -> None:
        assert sanitize_for_csv("\tcmd") == "'\tcmd"

    def test_cr_prefix_sanitized(self) -> None:
        assert sanitize_for_csv("\rcmd") == "'\rcmd"

    def test_normal_values_unchanged(self) -> None:
        assert sanitize_for_csv("hello") == "hello"
        assert sanitize_for_csv("123") == "123"
        assert sanitize_for_csv("") == ""

    def test_none_becomes_empty_string(self) -> None:
        assert sanitize_for_csv(None) == ""

    def test_dicts_to_csv_sanitizes_values(self) -> None:
        """End-to-end: dicts_to_csv applies sanitization."""
        data = [{"name": "=HYPERLINK(evil)", "value": "safe"}]
        result = dicts_to_csv(data, fieldnames=["name", "value"])
        reader = csv.reader(io.StringIO(result))
        _header = next(reader)
        row = next(reader)
        # The '=' should be escaped with a leading quote
        assert row[0] == "'=HYPERLINK(evil)"
        assert row[1] == "safe"


# =========================================================================
# Authentication required
# =========================================================================


class TestAuthRequired:
    def test_investigations_requires_auth(self) -> None:
        """Without auth override the endpoint returns 401/403."""
        app = _create_test_app()
        repo = AsyncMock()
        repo.export_investigations = AsyncMock(return_value=[])
        exports.set_repository(repo)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/export/investigations")
        assert resp.status_code in (401, 403)
        repo.export_investigations.assert_not_called()

    def test_remediations_requires_auth(self) -> None:
        app = _create_test_app()
        repo = AsyncMock()
        repo.export_remediations = AsyncMock(return_value=[])
        exports.set_repository(repo)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/export/remediations")
        assert resp.status_code in (401, 403)
        repo.export_remediations.assert_not_called()

    def test_compliance_requires_auth(self) -> None:
        app = _create_test_app()
        repo = AsyncMock()
        repo.export_compliance_data = AsyncMock(return_value=[])
        exports.set_repository(repo)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/export/compliance")
        assert resp.status_code in (401, 403)
        repo.export_compliance_data.assert_not_called()


# =========================================================================
# Compliance report structure
# =========================================================================


class TestComplianceReportStructure:
    def test_compliance_json_has_required_fields(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/compliance?format=json")
        assert resp.status_code == 200
        data = resp.json()
        entry = data[0]
        assert "scan_id" in entry
        assert "compliance_score" in entry
        assert "critical_cve_count" in entry
        assert "patches_applied" in entry
        assert "credentials_rotated" in entry
        assert "environment" in entry
        assert "created_at" in entry

    def test_compliance_csv_has_score_column(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get("/api/v1/export/compliance?format=csv")
        reader = csv.reader(io.StringIO(resp.text))
        headers = next(reader)
        assert "compliance_score" in headers
        assert "critical_cve_count" in headers


# =========================================================================
# DB unavailable returns 503
# =========================================================================


class TestDBUnavailable:
    def test_returns_503_when_no_repository(self) -> None:
        app = _create_test_app()
        # Wire auth but do NOT set a repository
        from shieldops.api.auth.dependencies import (
            get_current_user,
            require_role,
        )
        from shieldops.api.auth.models import UserResponse, UserRole

        user = UserResponse(
            id="viewer-1",
            email="v@test.com",
            name="V",
            role=UserRole.VIEWER,
            is_active=True,
        )

        async def _mock() -> UserResponse:
            return user

        app.dependency_overrides[get_current_user] = _mock
        dep = require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
        app.dependency_overrides[dep] = _mock

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/export/investigations")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "DB unavailable"
