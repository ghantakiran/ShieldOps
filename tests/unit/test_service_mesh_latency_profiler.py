"""Tests for ServiceMeshLatencyProfiler."""

from __future__ import annotations

from shieldops.analytics.service_mesh_latency_profiler import (
    HopType,
    LatencySource,
    RegressionSeverity,
    ServiceMeshLatencyProfiler,
)


def _engine(**kw) -> ServiceMeshLatencyProfiler:
    return ServiceMeshLatencyProfiler(**kw)


class TestEnums:
    def test_latency_source_values(self):
        for v in LatencySource:
            assert isinstance(v.value, str)

    def test_hop_type_values(self):
        for v in HopType:
            assert isinstance(v.value, str)

    def test_regression_severity_values(self):
        for v in RegressionSeverity:
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
            hop_name="hop-1",
            latency_ms=50.0,
            baseline_ms=30.0,
            proxy_overhead_ms=10.0,
        )
        assert r.latency_ms == 50.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(hop_name="hop-1", latency_ms=100.0)
        a = eng.process(r.id)
        assert a.hop_name == "hop-1"

    def test_regression(self):
        eng = _engine()
        r = eng.add_record(
            regression_severity=(RegressionSeverity.CRITICAL),
        )
        a = eng.process(r.id)
        assert a.has_regression is True

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

    def test_regression_hops(self):
        eng = _engine()
        eng.add_record(
            hop_name="hop-1",
            regression_severity=(RegressionSeverity.CRITICAL),
        )
        rpt = eng.generate_report()
        assert len(rpt.regression_hops) == 1


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


class TestProfileHopLatency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(hop_name="hop-1", latency_ms=50.0)
        result = eng.profile_hop_latency()
        assert len(result) == 1
        assert result[0]["avg_latency_ms"] == 50.0

    def test_empty(self):
        assert _engine().profile_hop_latency() == []


class TestIdentifyProxyOverhead:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service="svc-a",
            proxy_overhead_ms=15.0,
        )
        result = eng.identify_proxy_overhead()
        assert len(result) == 1
        assert result[0]["avg_overhead_ms"] == 15.0

    def test_empty(self):
        assert _engine().identify_proxy_overhead() == []


class TestDetectLatencyRegression:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            hop_name="hop-1",
            latency_ms=100.0,
            baseline_ms=50.0,
            regression_severity=(RegressionSeverity.MAJOR),
        )
        result = eng.detect_latency_regression()
        assert len(result) == 1
        assert result[0]["delta_ms"] == 50.0

    def test_empty(self):
        assert _engine().detect_latency_regression() == []
