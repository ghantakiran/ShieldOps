"""Tests for MeshControlPlaneObserver."""

from __future__ import annotations

from shieldops.observability.mesh_control_plane_observer import (
    ControlPlaneHealth,
    MeshControlPlaneObserver,
    PropagationStatus,
    SyncState,
)


def _engine(**kw) -> MeshControlPlaneObserver:
    return MeshControlPlaneObserver(**kw)


class TestEnums:
    def test_propagation_status_values(self):
        for v in PropagationStatus:
            assert isinstance(v.value, str)

    def test_control_plane_health_values(self):
        for v in ControlPlaneHealth:
            assert isinstance(v.value, str)

    def test_sync_state_values(self):
        for v in SyncState:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(mesh_name="istio")
        assert r.mesh_name == "istio"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(mesh_name=f"mesh-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            mesh_name="istio",
            component="pilot",
            control_plane_health=(ControlPlaneHealth.DEGRADED),
            latency_ms=150.0,
        )
        assert r.latency_ms == 150.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            mesh_name="istio",
            component="pilot",
            latency_ms=100.0,
        )
        a = eng.process(r.id)
        assert a.propagation_lag_ms == 100.0

    def test_diverged(self):
        eng = _engine()
        r = eng.add_record(
            sync_state=SyncState.DIVERGED,
        )
        a = eng.process(r.id)
        assert a.is_diverged is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(mesh_name="istio")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_unhealthy(self):
        eng = _engine()
        eng.add_record(
            component="pilot",
            control_plane_health=(ControlPlaneHealth.CRITICAL),
        )
        rpt = eng.generate_report()
        assert len(rpt.unhealthy_components) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(mesh_name="istio")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(mesh_name="istio")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMonitorConfigPropagation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(component="pilot", latency_ms=50.0)
        result = eng.monitor_config_propagation()
        assert len(result) == 1
        assert result[0]["avg_latency_ms"] == 50.0

    def test_empty(self):
        assert _engine().monitor_config_propagation() == []


class TestAssessControlPlaneHealth:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            mesh_name="istio",
            control_plane_health=(ControlPlaneHealth.HEALTHY),
        )
        result = eng.assess_control_plane_health()
        assert len(result) == 1
        assert result[0]["healthy_pct"] == 100.0

    def test_empty(self):
        assert _engine().assess_control_plane_health() == []


class TestDetectSyncDivergence:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            component="pilot",
            sync_state=SyncState.DIVERGED,
            latency_ms=500.0,
        )
        result = eng.detect_sync_divergence()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_sync_divergence() == []
