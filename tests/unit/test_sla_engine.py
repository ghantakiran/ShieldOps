"""Tests for the SLA Management Engine.

Covers:
- SLO CRUD operations (create, get, list, update, delete)
- Error budget calculation for 99.9%, 99.95%, 99.99% targets
- Budget status transitions (healthy, warning, critical, exhausted)
- Burn rate computation (zero, normal, accelerated)
- Downtime recording (single, multiple, descriptions)
- Breach detection (within budget, exhausted)
- Auto-escalation triggers and escalation detail correctness
- Rolling window behavior (old downtimes excluded)
- Dashboard aggregation (overall health, budget summary, breach listing)
- API route endpoints (CRUD, budgets, dashboard, error cases)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import sla as sla_routes
from shieldops.sla.engine import (
    SLABreach,
    SLADashboard,
    SLAEngine,
    SLOCreateRequest,
    SLODefinition,
    SLOUpdateRequest,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_sla_route_engine() -> Any:
    """Reset the module-level engine singleton between tests."""
    sla_routes._engine = None
    yield
    sla_routes._engine = None


@pytest.fixture()
def engine() -> SLAEngine:
    """Return a fresh SLAEngine instance."""
    return SLAEngine()


def _make_slo(
    engine: SLAEngine,
    name: str = "API Availability",
    service: str = "api-gateway",
    target: float = 99.9,
    window_days: int = 30,
) -> SLODefinition:
    """Helper to create an SLO via the engine."""
    return engine.create_slo(
        SLOCreateRequest(
            name=name,
            service=service,
            target=target,
            window_days=window_days,
        )
    )


# ── SLO CRUD Tests ──────────────────────────────────────────────


class TestSLOCrud:
    def test_create_slo(self, engine: SLAEngine) -> None:
        """Creating an SLO should return an SLODefinition with a generated ID."""
        slo = _make_slo(engine)

        assert slo.id.startswith("slo-")
        assert slo.name == "API Availability"
        assert slo.service == "api-gateway"
        assert slo.target == 99.9
        assert slo.window_days == 30
        assert slo.metric_type == "availability"
        assert isinstance(slo.created_at, datetime)
        assert isinstance(slo.updated_at, datetime)

    def test_get_slo(self, engine: SLAEngine) -> None:
        """get_slo should return the SLO when it exists."""
        slo = _make_slo(engine)
        fetched = engine.get_slo(slo.id)

        assert fetched is not None
        assert fetched.id == slo.id
        assert fetched.name == slo.name

    def test_get_slo_not_found(self, engine: SLAEngine) -> None:
        """get_slo should return None for a non-existent ID."""
        assert engine.get_slo("slo-nonexistent") is None

    def test_list_slos(self, engine: SLAEngine) -> None:
        """list_slos should return all created SLOs."""
        _make_slo(engine, name="SLO-1", service="svc-1")
        _make_slo(engine, name="SLO-2", service="svc-2")

        slos = engine.list_slos()
        assert len(slos) == 2
        names = {s.name for s in slos}
        assert names == {"SLO-1", "SLO-2"}

    def test_update_slo(self, engine: SLAEngine) -> None:
        """update_slo should modify only the provided fields."""
        slo = _make_slo(engine, name="Original", target=99.9)
        original_created = slo.created_at

        updated = engine.update_slo(
            slo.id,
            SLOUpdateRequest(name="Updated", target=99.95),
        )

        assert updated is not None
        assert updated.name == "Updated"
        assert updated.target == 99.95
        assert updated.created_at == original_created
        assert updated.updated_at >= original_created

    def test_update_slo_partial(self, engine: SLAEngine) -> None:
        """update_slo should leave unchanged fields untouched."""
        slo = _make_slo(engine, name="API SLO", target=99.9)
        updated = engine.update_slo(slo.id, SLOUpdateRequest(description="New desc"))

        assert updated is not None
        assert updated.name == "API SLO"
        assert updated.target == 99.9
        assert updated.description == "New desc"

    def test_update_slo_not_found(self, engine: SLAEngine) -> None:
        """update_slo should return None for a non-existent SLO."""
        result = engine.update_slo("slo-bad", SLOUpdateRequest(name="X"))
        assert result is None

    def test_delete_slo(self, engine: SLAEngine) -> None:
        """delete_slo should remove the SLO and return True."""
        slo = _make_slo(engine)
        assert engine.delete_slo(slo.id) is True
        assert engine.get_slo(slo.id) is None

    def test_delete_slo_not_found(self, engine: SLAEngine) -> None:
        """delete_slo should return False when the SLO doesn't exist."""
        assert engine.delete_slo("slo-missing") is False


# ── Error Budget Tests ───────────────────────────────────────────


class TestErrorBudget:
    def test_budget_99_9_target(self, engine: SLAEngine) -> None:
        """99.9% target over 30 days should yield 43.2 minutes budget."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.total_minutes == pytest.approx(43.2, abs=0.01)
        assert budget.consumed_minutes == 0.0
        assert budget.remaining_minutes == pytest.approx(43.2, abs=0.01)
        assert budget.remaining_percentage == 100.0

    def test_budget_99_95_target(self, engine: SLAEngine) -> None:
        """99.95% target over 30 days should yield 21.6 minutes budget."""
        slo = _make_slo(engine, target=99.95, window_days=30)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.total_minutes == pytest.approx(21.6, abs=0.01)

    def test_budget_99_99_target(self, engine: SLAEngine) -> None:
        """99.99% target over 30 days should yield 4.32 minutes budget."""
        slo = _make_slo(engine, target=99.99, window_days=30)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.total_minutes == pytest.approx(4.32, abs=0.01)

    def test_budget_raises_for_unknown_slo(self, engine: SLAEngine) -> None:
        """calculate_error_budget should raise ValueError for unknown SLO."""
        with pytest.raises(ValueError, match="SLO not found"):
            engine.calculate_error_budget("slo-ghost")


# ── Budget Status Tests ──────────────────────────────────────────


class TestBudgetStatus:
    def test_healthy_when_fresh(self, engine: SLAEngine) -> None:
        """A new SLO with no downtime should be healthy."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.status == "healthy"

    def test_warning_at_50_percent(self, engine: SLAEngine) -> None:
        """Budget should be 'warning' when ~50% is consumed."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        # Total budget = 43.2 min; consume ~55% => 23.76 min
        engine.record_downtime(slo.id, 23.76)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.status == "warning"

    def test_critical_at_80_percent(self, engine: SLAEngine) -> None:
        """Budget should be 'critical' when ~85% is consumed."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        # Total budget = 43.2 min; consume 85% => 36.72 min
        engine.record_downtime(slo.id, 36.72)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.status == "critical"

    def test_exhausted_at_100_percent(self, engine: SLAEngine) -> None:
        """Budget should be 'exhausted' when >100% is consumed."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        # Total budget = 43.2 min; consume 50 min
        engine.record_downtime(slo.id, 50.0)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.status == "exhausted"
        assert budget.remaining_minutes == 0.0


# ── Burn Rate Tests ──────────────────────────────────────────────


class TestBurnRate:
    def test_zero_burn_rate_no_downtime(self, engine: SLAEngine) -> None:
        """Burn rate should be 0.0 when there is no downtime."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.burn_rate == 0.0

    def test_burn_rate_increases_with_downtime(self, engine: SLAEngine) -> None:
        """Burn rate should be positive after recording downtime."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        engine.record_downtime(slo.id, 10.0)
        budget = engine.calculate_error_budget(slo.id)

        assert budget.burn_rate > 0.0

    def test_accelerated_burn_rate(self, engine: SLAEngine) -> None:
        """Consuming most of the budget should produce a high burn rate."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        # Consume 40 of 43.2 min budget (92.6% of total budget)
        engine.record_downtime(slo.id, 40.0)
        budget = engine.calculate_error_budget(slo.id)

        # Burn rate of ~0.93 means at current pace, 93% of budget
        # would be consumed per window. This is a high rate.
        assert budget.burn_rate > 0.9


# ── Record Downtime Tests ────────────────────────────────────────


class TestRecordDowntime:
    def test_single_downtime(self, engine: SLAEngine) -> None:
        """Recording downtime should create a breach and reduce budget."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        breach = engine.record_downtime(slo.id, 5.0, "Disk full")

        assert isinstance(breach, SLABreach)
        assert breach.id.startswith("breach-")
        assert breach.slo_id == slo.id
        assert breach.duration_minutes == 5.0
        assert breach.description == "Disk full"
        assert breach.service == "api-gateway"

        budget = engine.calculate_error_budget(slo.id)
        assert budget.consumed_minutes == pytest.approx(5.0, abs=0.01)

    def test_multiple_downtimes_accumulate(self, engine: SLAEngine) -> None:
        """Multiple downtime events should accumulate in the budget."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        engine.record_downtime(slo.id, 5.0)
        engine.record_downtime(slo.id, 10.0)
        engine.record_downtime(slo.id, 3.0)

        budget = engine.calculate_error_budget(slo.id)
        assert budget.consumed_minutes == pytest.approx(18.0, abs=0.01)

    def test_downtime_description_captured(self, engine: SLAEngine) -> None:
        """Breach description should be captured from the downtime event."""
        slo = _make_slo(engine)
        breach = engine.record_downtime(slo.id, 2.0, "Network partition")

        assert breach.description == "Network partition"

    def test_downtime_raises_for_unknown_slo(self, engine: SLAEngine) -> None:
        """record_downtime should raise ValueError for unknown SLO."""
        with pytest.raises(ValueError, match="SLO not found"):
            engine.record_downtime("slo-nope", 5.0)


# ── Breach Detection Tests ───────────────────────────────────────


class TestBreachDetection:
    def test_no_breach_within_budget(self, engine: SLAEngine) -> None:
        """check_breach should return False when budget is not exhausted."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        engine.record_downtime(slo.id, 10.0)  # 10 of 43.2 min

        assert engine.check_breach(slo.id) is False

    def test_breach_when_exhausted(self, engine: SLAEngine) -> None:
        """check_breach should return True when budget is exhausted."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        engine.record_downtime(slo.id, 50.0)  # exceeds 43.2 min

        assert engine.check_breach(slo.id) is True

    def test_get_breaches_returns_all(self, engine: SLAEngine) -> None:
        """get_breaches should return all breaches across SLOs."""
        slo1 = _make_slo(engine, name="SLO-1", service="svc-1")
        slo2 = _make_slo(engine, name="SLO-2", service="svc-2")
        engine.record_downtime(slo1.id, 5.0)
        engine.record_downtime(slo2.id, 3.0)

        breaches = engine.get_breaches()
        assert len(breaches) == 2

    def test_get_breaches_filtered_by_slo(self, engine: SLAEngine) -> None:
        """get_breaches with slo_id filter should return only matching."""
        slo1 = _make_slo(engine, name="SLO-1", service="svc-1")
        slo2 = _make_slo(engine, name="SLO-2", service="svc-2")
        engine.record_downtime(slo1.id, 5.0)
        engine.record_downtime(slo2.id, 3.0)
        engine.record_downtime(slo1.id, 2.0)

        breaches = engine.get_breaches(slo_id=slo1.id)
        assert len(breaches) == 2
        assert all(b.slo_id == slo1.id for b in breaches)


# ── Auto-Escalation Tests ───────────────────────────────────────


class TestAutoEscalation:
    def test_escalation_on_critical_burn(self, engine: SLAEngine) -> None:
        """Recording downtime that pushes budget to critical should auto-escalate."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        # Push past 80% consumed => critical
        breach = engine.record_downtime(slo.id, 40.0)

        assert breach.auto_escalated is True

    def test_escalation_details_correct(self, engine: SLAEngine) -> None:
        """auto_escalate should return structured escalation details."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        engine.record_downtime(slo.id, 10.0)  # consume some budget first

        escalation = engine.auto_escalate(slo.id)

        assert escalation["slo_id"] == slo.id
        assert escalation["slo_name"] == slo.name
        assert escalation["service"] == slo.service
        assert escalation["target"] == slo.target
        assert "action" in escalation
        assert escalation["action"] == "page_oncall"
        assert "notification_targets" in escalation
        assert "oncall-sre" in escalation["notification_targets"]
        assert "message" in escalation
        assert slo.name in escalation["message"]

    def test_no_escalation_when_healthy(self, engine: SLAEngine) -> None:
        """Downtime within healthy budget should not trigger escalation."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        breach = engine.record_downtime(slo.id, 5.0)  # 5 of 43.2 min

        assert breach.auto_escalated is False

    def test_escalation_raises_for_unknown_slo(self, engine: SLAEngine) -> None:
        """auto_escalate should raise ValueError for unknown SLO."""
        with pytest.raises(ValueError, match="SLO not found"):
            engine.auto_escalate("slo-phantom")

    def test_escalation_priority_p1_when_exhausted(self, engine: SLAEngine) -> None:
        """Escalation priority should be P1 when budget is exhausted."""
        slo = _make_slo(engine, target=99.9, window_days=30)
        engine.record_downtime(slo.id, 50.0)  # exhaust budget

        escalation = engine.auto_escalate(slo.id)
        assert escalation["priority"] == "P1"


# ── Rolling Window Tests ─────────────────────────────────────────


class TestRollingWindow:
    def test_old_downtimes_excluded(self, engine: SLAEngine) -> None:
        """Downtime records older than the window should not count."""
        slo = _make_slo(engine, target=99.9, window_days=30)

        # Inject an old downtime record directly (outside window)
        old_time = datetime.now(UTC) - timedelta(days=31)
        engine._downtime_records.append(
            {
                "slo_id": slo.id,
                "duration_minutes": 40.0,
                "recorded_at": old_time,
                "description": "Old outage",
            }
        )

        budget = engine.calculate_error_budget(slo.id)

        # Old downtime should be excluded; budget should be full
        assert budget.consumed_minutes == 0.0
        assert budget.status == "healthy"

    def test_window_boundary_included(self, engine: SLAEngine) -> None:
        """Downtime just inside the window boundary should be included."""
        slo = _make_slo(engine, target=99.9, window_days=30)

        # Inject a record slightly inside the window (29.99 days ago)
        # to avoid microsecond-level timing differences between test
        # setup and the engine's now() call.
        inside_time = datetime.now(UTC) - timedelta(days=29, hours=23, minutes=50)
        engine._downtime_records.append(
            {
                "slo_id": slo.id,
                "duration_minutes": 20.0,
                "recorded_at": inside_time,
                "description": "Boundary outage",
            }
        )

        budget = engine.calculate_error_budget(slo.id)

        # Record inside the window should be counted
        assert budget.consumed_minutes == pytest.approx(20.0, abs=0.01)

    def test_mixed_old_and_new_downtimes(self, engine: SLAEngine) -> None:
        """Only downtimes within the window should contribute to budget."""
        slo = _make_slo(engine, target=99.9, window_days=30)

        # Old downtime (outside window)
        old_time = datetime.now(UTC) - timedelta(days=35)
        engine._downtime_records.append(
            {
                "slo_id": slo.id,
                "duration_minutes": 30.0,
                "recorded_at": old_time,
                "description": "Old",
            }
        )

        # Recent downtime (inside window)
        engine.record_downtime(slo.id, 10.0, "Recent")

        budget = engine.calculate_error_budget(slo.id)
        assert budget.consumed_minutes == pytest.approx(10.0, abs=0.01)


# ── Dashboard Tests ──────────────────────────────────────────────


class TestDashboard:
    def test_empty_dashboard(self, engine: SLAEngine) -> None:
        """Dashboard with no SLOs should be healthy with empty lists."""
        dashboard = engine.get_dashboard()

        assert isinstance(dashboard, SLADashboard)
        assert dashboard.overall_health == "healthy"
        assert dashboard.slos == []
        assert dashboard.breaches == []
        assert dashboard.budget_summary["total_slos"] == 0

    def test_dashboard_overall_health_aggregation(self, engine: SLAEngine) -> None:
        """Dashboard overall health should reflect worst SLO status."""
        _make_slo(engine, name="Healthy SLO", service="svc-ok")
        slo_bad = _make_slo(engine, name="Bad SLO", service="svc-bad")

        # Exhaust budget on slo_bad
        engine.record_downtime(slo_bad.id, 50.0)

        dashboard = engine.get_dashboard()
        assert dashboard.overall_health == "critical"

    def test_dashboard_budget_summary(self, engine: SLAEngine) -> None:
        """Budget summary should count SLOs in each status category."""
        _make_slo(engine, name="SLO-1", service="svc-1")
        slo2 = _make_slo(engine, name="SLO-2", service="svc-2")
        slo3 = _make_slo(engine, name="SLO-3", service="svc-3")

        # slo1: healthy (no downtime)
        # slo2: warning (~55% consumed)
        engine.record_downtime(slo2.id, 23.76)
        # slo3: exhausted
        engine.record_downtime(slo3.id, 50.0)

        dashboard = engine.get_dashboard()
        summary = dashboard.budget_summary

        assert summary["total_slos"] == 3
        assert summary["healthy"] == 1

    def test_dashboard_breach_listing(self, engine: SLAEngine) -> None:
        """Dashboard should include recent breaches."""
        slo = _make_slo(engine)
        engine.record_downtime(slo.id, 5.0, "Outage 1")
        engine.record_downtime(slo.id, 3.0, "Outage 2")

        dashboard = engine.get_dashboard()
        assert len(dashboard.breaches) == 2

    def test_dashboard_slo_entries(self, engine: SLAEngine) -> None:
        """Dashboard SLO entries should include budget state."""
        slo = _make_slo(engine, name="My SLO", service="my-svc", target=99.9)
        engine.record_downtime(slo.id, 5.0)

        dashboard = engine.get_dashboard()
        assert len(dashboard.slos) == 1
        entry = dashboard.slos[0]
        assert entry["name"] == "My SLO"
        assert entry["service"] == "my-svc"
        assert entry["target"] == 99.9
        assert entry["budget_status"] == "healthy"
        assert "remaining_pct" in entry
        assert "burn_rate" in entry


# ── API Route Tests ──────────────────────────────────────────────


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(sla_routes.router, prefix="/api/v1")
    return app


def _build_client(
    app: FastAPI,
    sla_engine: SLAEngine | None = None,
) -> TestClient:
    """Wire a mock SLA engine and override auth for an admin user."""
    if sla_engine is not None:
        sla_routes.set_engine(sla_engine)

    from shieldops.api.auth.dependencies import get_current_user
    from shieldops.api.auth.models import UserResponse, UserRole

    admin = UserResponse(
        id="u-admin",
        email="admin@test.com",
        name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return admin

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


class TestSLAAPIRoutes:
    def test_create_slo_endpoint(self) -> None:
        """POST /sla/slos should create an SLO."""
        app = _create_test_app()
        client = _build_client(app, SLAEngine())

        resp = client.post(
            "/api/v1/sla/slos",
            json={
                "name": "API Availability",
                "service": "api-gateway",
                "target": 99.9,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "API Availability"
        assert data["target"] == 99.9
        assert data["id"].startswith("slo-")

    def test_list_slos_endpoint(self) -> None:
        """GET /sla/slos should list SLOs."""
        eng = SLAEngine()
        _make_slo(eng, name="SLO-A")
        _make_slo(eng, name="SLO-B")

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.get("/api/v1/sla/slos")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_get_slo_endpoint(self) -> None:
        """GET /sla/slos/{slo_id} should return the SLO."""
        eng = SLAEngine()
        slo = _make_slo(eng)

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.get(f"/api/v1/sla/slos/{slo.id}")

        assert resp.status_code == 200
        assert resp.json()["id"] == slo.id

    def test_get_slo_not_found(self) -> None:
        """GET /sla/slos/{bad_id} should return 404."""
        app = _create_test_app()
        client = _build_client(app, SLAEngine())

        resp = client.get("/api/v1/sla/slos/slo-nonexistent")

        assert resp.status_code == 404

    def test_update_slo_endpoint(self) -> None:
        """PUT /sla/slos/{slo_id} should update the SLO."""
        eng = SLAEngine()
        slo = _make_slo(eng, name="Original")

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.put(
            f"/api/v1/sla/slos/{slo.id}",
            json={"name": "Updated"},
        )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    def test_delete_slo_endpoint(self) -> None:
        """DELETE /sla/slos/{slo_id} should delete the SLO."""
        eng = SLAEngine()
        slo = _make_slo(eng)

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.delete(f"/api/v1/sla/slos/{slo.id}")

        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_slo_not_found(self) -> None:
        """DELETE /sla/slos/{bad_id} should return 404."""
        app = _create_test_app()
        client = _build_client(app, SLAEngine())

        resp = client.delete("/api/v1/sla/slos/slo-nope")

        assert resp.status_code == 404

    def test_budgets_endpoint(self) -> None:
        """GET /sla/budgets should return budgets for all SLOs."""
        eng = SLAEngine()
        _make_slo(eng)

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.get("/api/v1/sla/budgets")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["budgets"][0]["status"] == "healthy"

    def test_budget_for_specific_slo(self) -> None:
        """GET /sla/budgets/{slo_id} should return the budget."""
        eng = SLAEngine()
        slo = _make_slo(eng, target=99.9)

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.get(f"/api/v1/sla/budgets/{slo.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["slo_id"] == slo.id
        assert data["total_minutes"] == pytest.approx(43.2, abs=0.1)

    def test_budget_not_found(self) -> None:
        """GET /sla/budgets/{bad_id} should return 404."""
        app = _create_test_app()
        client = _build_client(app, SLAEngine())

        resp = client.get("/api/v1/sla/budgets/slo-missing")

        assert resp.status_code == 404

    def test_record_downtime_endpoint(self) -> None:
        """POST /sla/downtime should record a downtime event."""
        eng = SLAEngine()
        slo = _make_slo(eng)

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.post(
            "/api/v1/sla/downtime",
            json={
                "slo_id": slo.id,
                "duration_minutes": 5.0,
                "description": "API outage",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["slo_id"] == slo.id
        assert data["duration_minutes"] == 5.0

    def test_record_downtime_slo_not_found(self) -> None:
        """POST /sla/downtime with unknown SLO should return 404."""
        app = _create_test_app()
        client = _build_client(app, SLAEngine())

        resp = client.post(
            "/api/v1/sla/downtime",
            json={
                "slo_id": "slo-unknown",
                "duration_minutes": 5.0,
            },
        )

        assert resp.status_code == 404

    def test_breaches_endpoint(self) -> None:
        """GET /sla/breaches should return breach history."""
        eng = SLAEngine()
        slo = _make_slo(eng)
        eng.record_downtime(slo.id, 5.0)

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.get("/api/v1/sla/breaches")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_dashboard_endpoint(self) -> None:
        """GET /sla/dashboard should return the aggregate dashboard."""
        eng = SLAEngine()
        slo = _make_slo(eng)
        eng.record_downtime(slo.id, 5.0)

        app = _create_test_app()
        client = _build_client(app, eng)

        resp = client.get("/api/v1/sla/dashboard")

        assert resp.status_code == 200
        data = resp.json()
        assert "slos" in data
        assert "breaches" in data
        assert "overall_health" in data
        assert "budget_summary" in data

    def test_503_without_engine(self) -> None:
        """All endpoints should return 503 when the engine is not set."""
        app = _create_test_app()
        client = _build_client(app, sla_engine=None)

        for path in [
            "/api/v1/sla/slos",
            "/api/v1/sla/budgets",
            "/api/v1/sla/breaches",
            "/api/v1/sla/dashboard",
        ]:
            resp = client.get(path)
            assert resp.status_code == 503, f"Expected 503 for {path}"
