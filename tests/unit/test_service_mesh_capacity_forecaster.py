"""Tests for ServiceMeshCapacityForecaster."""

from __future__ import annotations

from shieldops.analytics.service_mesh_capacity_forecaster import (
    BottleneckSeverity,
    ResourceType,
    ScalingTrigger,
    ServiceMeshCapacityForecaster,
)


def _engine(**kw) -> ServiceMeshCapacityForecaster:
    return ServiceMeshCapacityForecaster(**kw)


class TestEnums:
    def test_resource_type_values(self):
        for v in ResourceType:
            assert isinstance(v.value, str)

    def test_scaling_trigger_values(self):
        for v in ScalingTrigger:
            assert isinstance(v.value, str)

    def test_bottleneck_severity_values(self):
        for v in BottleneckSeverity:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(service="svc-a")
        assert r.service == "svc-a"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(service=f"svc-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            service="svc-a",
            proxy_name="envoy-1",
            resource_type=ResourceType.MEMORY,
            utilization_pct=85.0,
        )
        assert r.utilization_pct == 85.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            proxy_name="envoy-1",
            utilization_pct=60.0,
        )
        a = eng.process(r.id)
        assert a.proxy_name == "envoy-1"

    def test_bottleneck(self):
        eng = _engine()
        r = eng.add_record(
            bottleneck_severity=(BottleneckSeverity.CRITICAL),
        )
        a = eng.process(r.id)
        assert a.is_bottleneck is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service="svc-a")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_bottleneck_proxies(self):
        eng = _engine()
        eng.add_record(
            proxy_name="envoy-1",
            bottleneck_severity=(BottleneckSeverity.HIGH),
        )
        rpt = eng.generate_report()
        assert len(rpt.bottleneck_proxies) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(service="svc-a")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(service="svc-a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestForecastProxyResourceNeeds:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            proxy_name="envoy-1",
            utilization_pct=70.0,
        )
        result = eng.forecast_proxy_resource_needs()
        assert len(result) == 1
        assert result[0]["avg_utilization"] == 70.0

    def test_empty(self):
        assert _engine().forecast_proxy_resource_needs() == []


class TestModelMeshScalingScenarios:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            scaling_trigger=(ScalingTrigger.TRAFFIC_GROWTH),
            utilization_pct=80.0,
        )
        result = eng.model_mesh_scaling_scenarios()
        assert len(result) == 1
        assert result[0]["trigger"] == ("traffic_growth")

    def test_empty(self):
        assert _engine().model_mesh_scaling_scenarios() == []


class TestDetectCapacityBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            proxy_name="envoy-1",
            bottleneck_severity=(BottleneckSeverity.CRITICAL),
            utilization_pct=95.0,
        )
        result = eng.detect_capacity_bottlenecks()
        assert len(result) == 1
        assert result[0]["utilization_pct"] == 95.0

    def test_empty(self):
        assert _engine().detect_capacity_bottlenecks() == []
