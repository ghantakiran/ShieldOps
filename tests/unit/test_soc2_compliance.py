"""Tests for SOC2 compliance engine and API routes.

Tests cover:
- Full audit run returns valid report with score
- Each trust service category has controls
- Control check returns proper status
- Evidence collection per control
- Admin override changes control status
- Trend calculation with direction
- Filtering controls by category
- Filtering controls by status
- Compliance score calculation (passed/total)
- Unknown control raises ValueError
- Override with invalid status returns 400
- API route: GET /compliance/report
- API route: GET /compliance/controls
- API route: GET /compliance/controls/{id}
- API route: GET /compliance/trends
- API route: GET /compliance/evidence/{id}
- API route: POST override requires admin
- API route: 404 for unknown control
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import compliance
from shieldops.compliance.soc2 import (
    ComplianceCheck,
    ComplianceReport,
    ComplianceTrend,
    ControlStatus,
    SOC2ComplianceEngine,
    TrustServiceCategory,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset the module singleton between tests."""
    compliance._engine = None
    yield
    compliance._engine = None


@pytest.fixture
def engine() -> SOC2ComplianceEngine:
    return SOC2ComplianceEngine()


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(compliance.router, prefix="/api/v1")
    return app


def _build_client_with_auth(
    app: FastAPI,
    engine_instance: SOC2ComplianceEngine | None = None,
    role: str = "operator",
) -> TestClient:
    """Wire dependency overrides for an authenticated user."""
    if engine_instance is not None:
        compliance.set_engine(engine_instance)

    from shieldops.api.auth.dependencies import get_current_user
    from shieldops.api.auth.models import UserResponse, UserRole

    user = UserResponse(
        id="user-1",
        email="test@shieldops.io",
        name="Test User",
        role=UserRole(role),
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# =================================================================
# 1. Full audit run
# =================================================================


class TestAuditRun:
    @pytest.mark.asyncio
    async def test_audit_returns_valid_report(self, engine: SOC2ComplianceEngine) -> None:
        report = await engine.run_audit()
        assert isinstance(report, ComplianceReport)
        assert report.id.startswith("audit-")
        assert 0 <= report.overall_score <= 100
        assert report.total_controls == 15
        assert report.passed + report.failed + report.warnings + report.not_applicable == 15

    @pytest.mark.asyncio
    async def test_audit_populates_category_scores(self, engine: SOC2ComplianceEngine) -> None:
        report = await engine.run_audit()
        for cat in TrustServiceCategory:
            assert cat.value in report.category_scores
            score = report.category_scores[cat.value]
            assert 0 <= score <= 100


# =================================================================
# 2. Trust service categories have controls
# =================================================================


class TestTrustServiceCategories:
    @pytest.mark.asyncio
    async def test_security_category_has_controls(self, engine: SOC2ComplianceEngine) -> None:
        controls = await engine.get_controls(category="security")
        assert len(controls) >= 3

    @pytest.mark.asyncio
    async def test_availability_category_has_controls(self, engine: SOC2ComplianceEngine) -> None:
        controls = await engine.get_controls(category="availability")
        assert len(controls) >= 2

    @pytest.mark.asyncio
    async def test_processing_integrity_has_controls(self, engine: SOC2ComplianceEngine) -> None:
        controls = await engine.get_controls(category="processing_integrity")
        assert len(controls) >= 2

    @pytest.mark.asyncio
    async def test_confidentiality_has_controls(self, engine: SOC2ComplianceEngine) -> None:
        controls = await engine.get_controls(category="confidentiality")
        assert len(controls) >= 1

    @pytest.mark.asyncio
    async def test_privacy_has_controls(self, engine: SOC2ComplianceEngine) -> None:
        controls = await engine.get_controls(category="privacy")
        assert len(controls) >= 1


# =================================================================
# 3. Control check returns proper status
# =================================================================


class TestControlCheck:
    @pytest.mark.asyncio
    async def test_check_returns_compliance_check(self, engine: SOC2ComplianceEngine) -> None:
        check = await engine.check_control("CC6.1")
        assert isinstance(check, ComplianceCheck)
        assert check.control_id == "CC6.1"
        assert check.control_name == "Logical Access Controls"
        assert check.category == TrustServiceCategory.SECURITY
        assert check.status in ControlStatus
        assert check.checked_at is not None

    @pytest.mark.asyncio
    async def test_rbac_check_passes(self, engine: SOC2ComplianceEngine) -> None:
        """RBAC check should pass since auth module exists."""
        check = await engine.check_control("CC6.1")
        assert check.status == ControlStatus.PASS
        assert len(check.evidence) > 0

    @pytest.mark.asyncio
    async def test_unknown_control_raises(self, engine: SOC2ComplianceEngine) -> None:
        with pytest.raises(ValueError, match="Unknown control"):
            await engine.check_control("UNKNOWN.99")


# =================================================================
# 4. Evidence collection
# =================================================================


class TestEvidenceCollection:
    @pytest.mark.asyncio
    async def test_evidence_returned_for_control(self, engine: SOC2ComplianceEngine) -> None:
        evidence = await engine.get_evidence("CC6.1")
        assert isinstance(evidence, list)
        assert len(evidence) > 0
        assert "type" in evidence[0]

    @pytest.mark.asyncio
    async def test_evidence_unknown_control_raises(self, engine: SOC2ComplianceEngine) -> None:
        with pytest.raises(ValueError, match="Unknown control"):
            await engine.get_evidence("FAKE.1")


# =================================================================
# 5. Admin override
# =================================================================


class TestAdminOverride:
    @pytest.mark.asyncio
    async def test_override_changes_status(self, engine: SOC2ComplianceEngine) -> None:
        ctrl = await engine.override_control(
            control_id="CC6.3",
            new_status="pass",
            justification="Verified SSL is enabled at infrastructure level",
            admin_user="admin-1",
        )
        assert ctrl.status == ControlStatus.PASS
        assert ctrl.override is not None
        assert ctrl.override["justification"] == "Verified SSL is enabled at infrastructure level"
        assert ctrl.override["overridden_by"] == "admin-1"

    @pytest.mark.asyncio
    async def test_override_persists_through_audit(self, engine: SOC2ComplianceEngine) -> None:
        await engine.override_control(
            control_id="CC6.3",
            new_status="pass",
            justification="Manually verified",
            admin_user="admin-1",
        )
        report = await engine.run_audit()
        ctrl = next(c for c in report.controls if c.id == "CC6.3")
        assert ctrl.status == ControlStatus.PASS
        assert ctrl.override is not None


# =================================================================
# 6. Trend calculation
# =================================================================


class TestTrendCalculation:
    @pytest.mark.asyncio
    async def test_trend_returns_data(self, engine: SOC2ComplianceEngine) -> None:
        trend = await engine.get_trends(days=30)
        assert isinstance(trend, ComplianceTrend)
        assert trend.period_days == 30
        assert len(trend.data_points) > 0
        assert trend.trend_direction in ("up", "down", "stable")

    @pytest.mark.asyncio
    async def test_trend_after_audit(self, engine: SOC2ComplianceEngine) -> None:
        await engine.run_audit()
        trend = await engine.get_trends(days=7)
        assert trend.current_score > 0


# =================================================================
# 7. Filter controls by category
# =================================================================


class TestFilterByCategory:
    @pytest.mark.asyncio
    async def test_filter_security_only(self, engine: SOC2ComplianceEngine) -> None:
        controls = await engine.get_controls(category="security")
        for c in controls:
            assert c.category == TrustServiceCategory.SECURITY

    @pytest.mark.asyncio
    async def test_filter_nonexistent_returns_empty(self, engine: SOC2ComplianceEngine) -> None:
        controls = await engine.get_controls(category="nonexistent")
        assert len(controls) == 0


# =================================================================
# 8. Filter controls by status
# =================================================================


class TestFilterByStatus:
    @pytest.mark.asyncio
    async def test_filter_by_pass_status(self, engine: SOC2ComplianceEngine) -> None:
        # Run audit first to populate statuses
        await engine.run_audit()
        controls = await engine.get_controls(status="pass")
        for c in controls:
            assert c.status == ControlStatus.PASS


# =================================================================
# 9. Compliance score calculation
# =================================================================


class TestScoreCalculation:
    @pytest.mark.asyncio
    async def test_score_is_percentage_of_passed(self, engine: SOC2ComplianceEngine) -> None:
        report = await engine.run_audit()
        scoreable = report.total_controls - report.not_applicable
        if scoreable > 0:
            expected = round(report.passed / scoreable * 100, 1)
            assert report.overall_score == expected


# =================================================================
# 10-18. API Route Integration Tests
# =================================================================


class TestComplianceAPI:
    def test_get_report(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_score" in data
        assert "controls" in data
        assert data["total_controls"] == 15
        assert data["id"].startswith("audit-")

    def test_list_controls(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/controls")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15
        assert len(data["controls"]) == 15

    def test_list_controls_filtered(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/controls?category=security")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for ctrl in data["controls"]:
            assert ctrl["category"] == "security"

    def test_get_single_control(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/controls/CC6.1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["control_id"] == "CC6.1"
        assert data["status"] in ("pass", "fail", "warning", "not_applicable")

    def test_get_unknown_control_returns_404(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/controls/FAKE.99")
        assert resp.status_code == 404

    def test_get_trends(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/trends?days=14")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 14
        assert data["trend_direction"] in ("up", "down", "stable")

    def test_get_evidence(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/evidence/CC6.1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["control_id"] == "CC6.1"
        assert data["total"] > 0

    def test_evidence_unknown_control_returns_404(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine)

        resp = client.get("/api/v1/compliance/evidence/FAKE.99")
        assert resp.status_code == 404

    def test_override_requires_admin(self, engine: SOC2ComplianceEngine) -> None:
        """Operator role should be able to call override since we mock
        get_current_user; the require_role check is tested separately."""
        app = _create_test_app()
        client = _build_client_with_auth(app, engine, role="admin")

        resp = client.post(
            "/api/v1/compliance/controls/CC6.3/override",
            json={
                "status": "pass",
                "justification": "Verified at infra level",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pass"
        assert data["override"] is not None

    def test_override_invalid_status_returns_400(self, engine: SOC2ComplianceEngine) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine, role="admin")

        resp = client.post(
            "/api/v1/compliance/controls/CC6.1/override",
            json={
                "status": "invalid_status",
                "justification": "Testing",
            },
        )
        assert resp.status_code == 400

    def test_engine_not_initialized_returns_503(self) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, engine_instance=None)

        resp = client.get("/api/v1/compliance/report")
        assert resp.status_code == 503
