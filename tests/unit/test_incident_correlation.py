"""Tests for incident correlation engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shieldops.agents.investigation.correlation import (
    CorrelationEngine,
)
from shieldops.api.auth.models import UserResponse, UserRole


def _make_investigation(
    inv_id: str = "inv-test001",
    alert_name: str = "HighCPU",
    alert_id: str = "alert-001",
    severity: str = "warning",
    service: str = "api-server",
    environment: str = "production",
    created_at: datetime | None = None,
) -> dict:
    return {
        "investigation_id": inv_id,
        "alert_name": alert_name,
        "alert_id": alert_id,
        "severity": severity,
        "alert_context": {
            "service": service,
            "environment": environment,
        },
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
    }


class TestCorrelationEngine:
    def test_first_investigation_creates_incident(self) -> None:
        engine = CorrelationEngine()
        inv = _make_investigation()
        incident = engine.correlate(inv)
        assert incident.id.startswith("cid-")
        assert len(incident.investigation_ids) == 1
        assert incident.title == "HighCPU"

    def test_same_service_correlates(self) -> None:
        engine = CorrelationEngine()
        now = datetime.now(UTC)
        inv1 = _make_investigation(inv_id="inv-1", created_at=now)
        inv2 = _make_investigation(
            inv_id="inv-2",
            alert_name="HighMemory",
            alert_id="alert-002",
            created_at=now + timedelta(minutes=5),
        )
        i1 = engine.correlate(inv1)
        i2 = engine.correlate(inv2)
        assert i1.id == i2.id
        assert len(i2.investigation_ids) == 2

    def test_different_service_no_correlation(self) -> None:
        engine = CorrelationEngine()
        now = datetime.now(UTC)
        inv1 = _make_investigation(inv_id="inv-1", service="api-server", created_at=now)
        inv2 = _make_investigation(
            inv_id="inv-2",
            service="database",
            alert_name="DiskFull",
            alert_id="alert-999",
            created_at=now + timedelta(minutes=5),
        )
        i1 = engine.correlate(inv1)
        i2 = engine.correlate(inv2)
        assert i1.id != i2.id

    def test_outside_time_window_no_correlation(self) -> None:
        engine = CorrelationEngine(time_window_minutes=10)
        now = datetime.now(UTC)
        inv1 = _make_investigation(inv_id="inv-1", created_at=now)
        inv2 = _make_investigation(
            inv_id="inv-2",
            created_at=now + timedelta(minutes=20),
        )
        i1 = engine.correlate(inv1)
        i2 = engine.correlate(inv2)
        assert i1.id != i2.id

    def test_exact_dedup(self) -> None:
        engine = CorrelationEngine()
        now = datetime.now(UTC)
        inv1 = _make_investigation(inv_id="inv-1", created_at=now)
        engine._store_investigation_data("inv-1", inv1)
        engine.correlate(inv1)

        inv2 = _make_investigation(
            inv_id="inv-2",
            alert_id="alert-001",  # Same alert_id
            created_at=now + timedelta(minutes=5),
        )
        i2 = engine.correlate(inv2)
        assert len(i2.investigation_ids) == 2

    def test_already_correlated_returns_same(self) -> None:
        engine = CorrelationEngine()
        inv = _make_investigation()
        i1 = engine.correlate(inv)
        i2 = engine.correlate(inv)
        assert i1.id == i2.id
        assert len(i2.investigation_ids) == 1

    def test_merge_incidents(self) -> None:
        engine = CorrelationEngine()
        now = datetime.now(UTC)
        inv1 = _make_investigation(inv_id="inv-1", service="svc-a", created_at=now)
        inv2 = _make_investigation(
            inv_id="inv-2",
            service="svc-b",
            alert_name="OtherAlert",
            alert_id="alert-other",
            created_at=now + timedelta(minutes=5),
        )
        i1 = engine.correlate(inv1)
        i2 = engine.correlate(inv2)
        assert i1.id != i2.id

        merged = engine.merge(i2.id, i1.id)
        assert merged is not None
        assert "inv-2" in merged.investigation_ids
        assert engine.get_incident(i2.id).status == "merged"

    def test_merge_invalid_ids(self) -> None:
        engine = CorrelationEngine()
        assert engine.merge("fake", "also-fake") is None

    def test_merge_same_id(self) -> None:
        engine = CorrelationEngine()
        inv = _make_investigation()
        i = engine.correlate(inv)
        assert engine.merge(i.id, i.id) is None

    def test_list_incidents_with_filters(self) -> None:
        engine = CorrelationEngine()
        now = datetime.now(UTC)
        for i in range(5):
            inv = _make_investigation(
                inv_id=f"inv-{i}",
                service=f"svc-{i}",
                alert_name=f"Alert-{i}",
                alert_id=f"alert-{i}",
                created_at=now + timedelta(minutes=i * 60),
            )
            engine.correlate(inv)

        all_incidents = engine.list_incidents()
        assert len(all_incidents) == 5

        engine.update_status(all_incidents[0].id, "resolved")
        open_incidents = engine.list_incidents(status="open")
        assert len(open_incidents) == 4

    def test_severity_escalation(self) -> None:
        engine = CorrelationEngine()
        now = datetime.now(UTC)
        inv1 = _make_investigation(inv_id="inv-1", severity="warning", created_at=now)
        inv2 = _make_investigation(
            inv_id="inv-2",
            severity="critical",
            alert_id="alert-002",
            created_at=now + timedelta(minutes=2),
        )
        engine.correlate(inv1)
        result = engine.correlate(inv2)
        assert result.severity == "critical"

    def test_update_status(self) -> None:
        engine = CorrelationEngine()
        inv = _make_investigation()
        incident = engine.correlate(inv)
        assert engine.update_status(incident.id, "investigating")
        assert engine.get_incident(incident.id).status == "investigating"
        assert not engine.update_status("nonexistent", "resolved")

    def test_get_incident_for_investigation(self) -> None:
        engine = CorrelationEngine()
        inv = _make_investigation()
        incident = engine.correlate(inv)
        found = engine.get_incident_for_investigation("inv-test001")
        assert found is not None
        assert found.id == incident.id
        assert engine.get_incident_for_investigation("nonexistent") is None

    def test_pagination(self) -> None:
        engine = CorrelationEngine()
        now = datetime.now(UTC)
        for i in range(10):
            inv = _make_investigation(
                inv_id=f"inv-{i}",
                service=f"svc-{i}",
                alert_name=f"Alert-{i}",
                alert_id=f"alert-{i}",
                created_at=now + timedelta(hours=i),
            )
            engine.correlate(inv)

        page1 = engine.list_incidents(limit=3, offset=0)
        page2 = engine.list_incidents(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].id != page2[0].id


class TestIncidentRoutes:
    """Tests for the /incidents API routes."""

    def test_list_incidents_empty(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.routes import incidents as incidents_mod

        app = FastAPI()
        app.include_router(incidents_mod.router, prefix="/api/v1")

        mock_user = UserResponse(
            id="usr-test",
            email="test@test.com",
            name="Test",
            role=UserRole.ADMIN,
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        engine = CorrelationEngine()
        incidents_mod.set_engine(engine)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["incidents"] == []
        assert data["total"] == 0

    def test_merge_endpoint(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.routes import incidents as incidents_mod

        app = FastAPI()
        app.include_router(incidents_mod.router, prefix="/api/v1")

        mock_user = UserResponse(
            id="usr-test",
            email="test@test.com",
            name="Test",
            role=UserRole.ADMIN,
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        engine = CorrelationEngine()
        now = datetime.now(UTC)
        engine.correlate(_make_investigation(inv_id="inv-1", service="svc-a", created_at=now))
        engine.correlate(
            _make_investigation(
                inv_id="inv-2",
                service="svc-b",
                alert_name="Other",
                alert_id="alert-x",
                created_at=now,
            )
        )
        incidents = engine.list_incidents()
        incidents_mod.set_engine(engine)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/incidents/merge",
            json={
                "source_id": incidents[0].id,
                "target_id": incidents[1].id,
            },
        )
        assert resp.status_code == 200

    def test_update_status_endpoint(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.routes import incidents as incidents_mod

        app = FastAPI()
        app.include_router(incidents_mod.router, prefix="/api/v1")

        mock_user = UserResponse(
            id="usr-test",
            email="test@test.com",
            name="Test",
            role=UserRole.ADMIN,
            is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        engine = CorrelationEngine()
        engine.correlate(_make_investigation())
        incidents = engine.list_incidents()
        incidents_mod.set_engine(engine)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(
            f"/api/v1/incidents/{incidents[0].id}/status", json={"status": "investigating"}
        )
        assert resp.status_code == 200
        assert resp.json()["incident"]["status"] == "investigating"
