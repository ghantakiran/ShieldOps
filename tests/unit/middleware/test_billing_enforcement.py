"""Tests for the billing enforcement middleware and PlanEnforcementService.

Covers plan limit checks, 402 responses, exempt paths, API quota
tracking, and the upgrade-usage endpoint integration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from starlette.applications import Starlette
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from shieldops.api.middleware.billing_enforcement import (
    BillingEnforcementMiddleware,
    _is_exempt,
)
from shieldops.api.middleware.usage_tracker import UsageTracker
from shieldops.billing.enforcement import PlanEnforcementService
from shieldops.integrations.billing.stripe_billing import PLANS

# ── Helpers ──────────────────────────────────────────────────────────


async def _ok_endpoint(request: Request) -> Response:
    """Minimal endpoint that returns 200."""
    return JSONResponse({"status": "ok"})


class OrgSetter(BaseHTTPMiddleware):
    """Test helper -- injects organization_id onto request.state."""

    def __init__(self, app: object, org_id: str | None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._org_id = org_id

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.organization_id = self._org_id
        return await call_next(request)


def _build_app(
    org_id: str | None = "org-test",
    enforcement: PlanEnforcementService | None = None,
) -> Starlette:
    """Build a minimal Starlette app with the billing middleware."""
    app = Starlette(
        routes=[
            Route("/health", _ok_endpoint),
            Route("/ready", _ok_endpoint),
            Route("/metrics", _ok_endpoint),
            Route("/api/v1/docs", _ok_endpoint),
            Route(
                "/api/v1/agents",
                _ok_endpoint,
                methods=["GET", "POST"],
            ),
            Route(
                "/api/v1/investigations",
                _ok_endpoint,
                methods=["GET"],
            ),
            Route(
                "/api/v1/billing/plans",
                _ok_endpoint,
                methods=["GET"],
            ),
            Route(
                "/api/v1/billing/usage",
                _ok_endpoint,
                methods=["GET"],
            ),
            Route(
                "/api/v1/auth/login",
                _ok_endpoint,
                methods=["POST"],
            ),
        ],
    )
    # Wire enforcement BEFORE adding middleware (class-level attr)
    BillingEnforcementMiddleware._enforcement = enforcement
    app.add_middleware(BillingEnforcementMiddleware)
    if org_id is not None:
        app.add_middleware(OrgSetter, org_id=org_id)
    return app


def _make_enforcement(
    plan: str = "free",
    agent_count: int = 0,
    api_used: int = 0,
) -> PlanEnforcementService:
    """Build a PlanEnforcementService with mocked DB and usage."""
    svc = PlanEnforcementService(session_factory=None)
    svc.get_org_plan = AsyncMock(return_value=plan)  # type: ignore[method-assign]
    plan_def = PLANS.get(plan, PLANS["free"])
    agent_limit = plan_def["agent_limit"]
    api_limit = plan_def["api_calls_limit"]

    # Agent limit check
    if agent_limit == -1:
        svc.check_agent_limit = AsyncMock(  # type: ignore[method-assign]
            return_value=(True, agent_count, -1)
        )
    else:
        allowed = agent_count < agent_limit
        svc.check_agent_limit = AsyncMock(  # type: ignore[method-assign]
            return_value=(allowed, agent_count, agent_limit)
        )

    # API quota check
    if api_limit == -1:
        svc.check_api_quota = AsyncMock(  # type: ignore[method-assign]
            return_value=(True, api_used, -1)
        )
    else:
        allowed = api_used < api_limit
        svc.check_api_quota = AsyncMock(  # type: ignore[method-assign]
            return_value=(allowed, api_used, api_limit)
        )

    return svc


@pytest.fixture(autouse=True)
def _cleanup_enforcement() -> None:
    """Reset the class-level enforcement service between tests."""
    BillingEnforcementMiddleware._enforcement = None
    UsageTracker.reset_instance()


# ── Test: _is_exempt helper ─────────────────────────────────────────


class TestIsExempt:
    """Verify exempt path detection logic."""

    def test_health_is_exempt(self) -> None:
        assert _is_exempt("/health") is True

    def test_ready_is_exempt(self) -> None:
        assert _is_exempt("/ready") is True

    def test_metrics_is_exempt(self) -> None:
        assert _is_exempt("/metrics") is True

    def test_docs_is_exempt(self) -> None:
        assert _is_exempt("/docs") is True

    def test_billing_endpoint_is_exempt(self) -> None:
        assert _is_exempt("/api/v1/billing/plans") is True
        assert _is_exempt("/api/v1/billing/usage") is True

    def test_auth_endpoint_is_exempt(self) -> None:
        assert _is_exempt("/api/v1/auth/login") is True

    def test_webhook_is_exempt(self) -> None:
        assert _is_exempt("/api/v1/webhooks/stripe") is True

    def test_agents_is_not_exempt(self) -> None:
        assert _is_exempt("/api/v1/agents") is False

    def test_investigations_is_not_exempt(self) -> None:
        assert _is_exempt("/api/v1/investigations") is False


# ── Test: Free plan blocks at 5 agents ──────────────────────────────


class TestFreePlanAgentLimit:
    """Free plan allows up to 5 agents."""

    def test_free_plan_allows_below_limit(self) -> None:
        """POST /api/v1/agents succeeds with 3 agents on free."""
        enforcement = _make_enforcement(plan="free", agent_count=3)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 200

    def test_free_plan_blocks_at_limit(self) -> None:
        """POST /api/v1/agents returns 402 with 5 agents on free."""
        enforcement = _make_enforcement(plan="free", agent_count=5)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 402
        body = resp.json()
        assert body["plan"] == "free"
        assert body["usage"] == 5
        assert body["limit"] == 5
        assert "upgrade" in body["detail"].lower()

    def test_free_plan_blocks_above_limit(self) -> None:
        """POST /api/v1/agents returns 402 with 7 agents on free."""
        enforcement = _make_enforcement(plan="free", agent_count=7)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 402


# ── Test: Pro plan allows up to 25 agents ───────────────────────────


class TestProPlanAgentLimit:
    """Pro plan allows up to 25 agents."""

    def test_pro_plan_allows_below_limit(self) -> None:
        """POST /api/v1/agents succeeds with 10 agents on pro."""
        enforcement = _make_enforcement(plan="pro", agent_count=10)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 200

    def test_pro_plan_allows_24_agents(self) -> None:
        """POST /api/v1/agents succeeds with 24 agents on pro."""
        enforcement = _make_enforcement(plan="pro", agent_count=24)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 200

    def test_pro_plan_blocks_at_25(self) -> None:
        """POST /api/v1/agents returns 402 with 25 agents on pro."""
        enforcement = _make_enforcement(plan="pro", agent_count=25)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 402
        body = resp.json()
        assert body["limit"] == 25


# ── Test: Enterprise unlimited ──────────────────────────────────────


class TestEnterprisePlan:
    """Enterprise plan has no limits (agent_limit == -1)."""

    def test_enterprise_allows_unlimited_agents(self) -> None:
        """POST /api/v1/agents succeeds with 100 agents on enterprise."""
        enforcement = _make_enforcement(plan="enterprise", agent_count=100)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 200

    def test_enterprise_allows_unlimited_api_calls(self) -> None:
        """GET requests succeed with 999999 API calls on enterprise."""
        enforcement = _make_enforcement(plan="enterprise", api_used=999_999)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200


# ── Test: 402 response format ───────────────────────────────────────


class TestPaymentRequiredFormat:
    """Verify the 402 response body and headers."""

    def test_402_contains_plan_info(self) -> None:
        enforcement = _make_enforcement(plan="free", agent_count=5)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 402
        body = resp.json()
        assert "detail" in body
        assert "plan" in body
        assert "usage" in body
        assert "limit" in body
        assert "upgrade_url" in body

    def test_402_includes_plan_headers(self) -> None:
        enforcement = _make_enforcement(plan="free", agent_count=5)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 402
        assert resp.headers["X-Plan-Name"] == "free"
        assert resp.headers["X-Plan-Usage"] == "5"
        assert resp.headers["X-Plan-Limit"] == "5"


# ── Test: Exempt paths skip enforcement ─────────────────────────────


class TestExemptPaths:
    """Requests to exempt paths bypass billing checks."""

    def test_health_bypasses_enforcement(self) -> None:
        enforcement = _make_enforcement(plan="free", api_used=9999)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200

    def test_billing_plans_bypasses_enforcement(self) -> None:
        enforcement = _make_enforcement(plan="free", api_used=9999)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/billing/plans")
        assert resp.status_code == 200

    def test_billing_usage_bypasses_enforcement(self) -> None:
        enforcement = _make_enforcement(plan="free", api_used=9999)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/billing/usage")
        assert resp.status_code == 200

    def test_auth_login_bypasses_enforcement(self) -> None:
        enforcement = _make_enforcement(plan="free", api_used=9999)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/auth/login")
        assert resp.status_code == 200


# ── Test: API quota tracking ────────────────────────────────────────


class TestAPIQuota:
    """API call quota enforcement."""

    def test_free_plan_blocks_over_api_limit(self) -> None:
        """GET requests return 402 when API calls exceed 1000."""
        enforcement = _make_enforcement(plan="free", api_used=1001)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/investigations")
        assert resp.status_code == 402
        body = resp.json()
        assert "quota exceeded" in body["detail"].lower()

    def test_free_plan_allows_under_api_limit(self) -> None:
        """GET requests succeed when under API call limit."""
        enforcement = _make_enforcement(plan="free", api_used=500)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/investigations")
        assert resp.status_code == 200

    def test_pro_plan_has_higher_api_limit(self) -> None:
        """Pro plan allows 50,000 API calls."""
        enforcement = _make_enforcement(plan="pro", api_used=49_000)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/investigations")
        assert resp.status_code == 200


# ── Test: Response headers on success ───────────────────────────────


class TestSuccessHeaders:
    """Successful requests include plan info headers."""

    def test_success_includes_plan_headers(self) -> None:
        enforcement = _make_enforcement(plan="pro", api_used=100)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        assert resp.headers["X-Plan-Name"] == "pro"
        assert resp.headers["X-Plan-Usage"] == "100"
        assert resp.headers["X-Plan-Limit"] == "50000"


# ── Test: No enforcement service means pass-through ────────────────


class TestNoEnforcement:
    """When no enforcement service is set, all requests pass."""

    def test_no_enforcement_passes_all(self) -> None:
        app = _build_app(enforcement=None)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 200

    def test_no_org_id_passes(self) -> None:
        """Requests without org_id pass when enforcement is active."""
        enforcement = _make_enforcement(plan="free", agent_count=99)
        app = _build_app(org_id=None, enforcement=enforcement)
        client = TestClient(app)

        resp = client.post("/api/v1/agents")
        assert resp.status_code == 200


# ── Test: GET /agents does NOT check agent limit ────────────────────


class TestGetAgentsNotBlocked:
    """GET requests to agents endpoint check only API quota."""

    def test_get_agents_not_blocked_by_agent_limit(self) -> None:
        """GET /agents works even when agent limit is reached."""
        enforcement = _make_enforcement(plan="free", agent_count=5)
        app = _build_app(enforcement=enforcement)
        client = TestClient(app)

        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200


# ── Test: PlanEnforcementService unit tests ─────────────────────────


class TestPlanEnforcementService:
    """Unit tests for the enforcement service internals."""

    @pytest.mark.asyncio
    async def test_get_org_plan_defaults_free(self) -> None:
        """Unknown org returns 'free' plan."""
        svc = PlanEnforcementService(session_factory=None)
        plan = await svc.get_org_plan("org-unknown")
        assert plan == "free"

    @pytest.mark.asyncio
    async def test_check_agent_limit_free(self) -> None:
        """Free plan has agent_limit of 5."""
        svc = PlanEnforcementService(session_factory=None)
        svc._count_agents = AsyncMock(return_value=3)  # type: ignore[method-assign]

        allowed, current, limit = await svc.check_agent_limit("org-1", plan="free")
        assert allowed is True
        assert current == 3
        assert limit == 5

    @pytest.mark.asyncio
    async def test_check_agent_limit_enterprise_unlimited(self) -> None:
        """Enterprise plan has agent_limit of -1 (unlimited)."""
        svc = PlanEnforcementService(session_factory=None)
        svc._count_agents = AsyncMock(return_value=100)  # type: ignore[method-assign]

        allowed, current, limit = await svc.check_agent_limit("org-1", plan="enterprise")
        assert allowed is True
        assert limit == -1

    @pytest.mark.asyncio
    async def test_check_api_quota_uses_tracker(self) -> None:
        """API quota check uses the UsageTracker singleton."""
        svc = PlanEnforcementService(session_factory=None)

        tracker = UsageTracker.get_instance()
        for _ in range(50):
            tracker.record("org-1", "GET", "/api/v1/agents")

        allowed, used, limit = await svc.check_api_quota("org-1", plan="free")
        assert used == 50
        assert limit == 1000
        assert allowed is True

    @pytest.mark.asyncio
    async def test_get_usage_summary_structure(self) -> None:
        """get_usage_summary returns all expected keys."""
        svc = PlanEnforcementService(session_factory=None)
        svc._count_agents = AsyncMock(return_value=2)  # type: ignore[method-assign]

        summary = await svc.get_usage_summary("org-1")
        expected_keys = {
            "plan",
            "plan_name",
            "agent_count",
            "agent_limit",
            "agent_limit_reached",
            "api_calls_used",
            "api_calls_limit",
            "api_quota_exceeded",
            "upgrade_available",
        }
        assert expected_keys == set(summary.keys())

    @pytest.mark.asyncio
    async def test_upgrade_available_free_to_pro(self) -> None:
        """Free plan shows 'pro' as upgrade."""
        svc = PlanEnforcementService(session_factory=None)
        svc._count_agents = AsyncMock(return_value=0)  # type: ignore[method-assign]

        summary = await svc.get_usage_summary("org-1")
        assert summary["upgrade_available"] == "pro"

    @pytest.mark.asyncio
    async def test_upgrade_available_pro_to_enterprise(self) -> None:
        """Pro plan shows 'enterprise' as upgrade."""
        svc = PlanEnforcementService(session_factory=None)
        svc.get_org_plan = AsyncMock(return_value="pro")  # type: ignore[method-assign]
        svc._count_agents = AsyncMock(return_value=0)  # type: ignore[method-assign]

        summary = await svc.get_usage_summary("org-1")
        assert summary["upgrade_available"] == "enterprise"

    @pytest.mark.asyncio
    async def test_upgrade_not_available_enterprise(self) -> None:
        """Enterprise plan has no upgrade available."""
        svc = PlanEnforcementService(session_factory=None)
        svc.get_org_plan = AsyncMock(return_value="enterprise")  # type: ignore[method-assign]
        svc._count_agents = AsyncMock(return_value=0)  # type: ignore[method-assign]

        summary = await svc.get_usage_summary("org-1")
        assert summary["upgrade_available"] is None


# ── Test: Plan cache behavior ───────────────────────────────────────


class TestPlanCache:
    """Verify that plan lookups are cached and invalidated."""

    @pytest.mark.asyncio
    async def test_cache_avoids_second_db_call(self) -> None:
        """Second call to get_org_plan uses cached value."""
        svc = PlanEnforcementService(session_factory=None)
        svc._fetch_plan_from_db = AsyncMock(return_value="pro")  # type: ignore[method-assign]

        plan1 = await svc.get_org_plan("org-1")
        plan2 = await svc.get_org_plan("org-1")

        assert plan1 == "pro"
        assert plan2 == "pro"
        # Should only call DB once due to caching
        svc._fetch_plan_from_db.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_cache_forces_refresh(self) -> None:
        """invalidate_cache causes the next call to hit DB."""
        svc = PlanEnforcementService(session_factory=None)
        svc._fetch_plan_from_db = AsyncMock(return_value="pro")  # type: ignore[method-assign]

        await svc.get_org_plan("org-1")
        svc.invalidate_cache("org-1")
        await svc.get_org_plan("org-1")

        assert svc._fetch_plan_from_db.await_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_all_cache(self) -> None:
        """invalidate_cache(None) clears all entries."""
        svc = PlanEnforcementService(session_factory=None)
        svc._fetch_plan_from_db = AsyncMock(return_value="free")  # type: ignore[method-assign]

        await svc.get_org_plan("org-1")
        await svc.get_org_plan("org-2")
        svc.invalidate_cache()  # flush all

        await svc.get_org_plan("org-1")
        await svc.get_org_plan("org-2")

        # Initial 2 + 2 after invalidation = 4 total
        assert svc._fetch_plan_from_db.await_count == 4
