"""Tests for SreGoldenSignalEngine."""

from __future__ import annotations

from shieldops.analytics.sre_golden_signal_engine import (
    GoldenSignal,
    ServiceTier,
    SignalStatus,
    SreGoldenSignalEngine,
)


def _engine(**kw) -> SreGoldenSignalEngine:
    return SreGoldenSignalEngine(**kw)


class TestEnums:
    def test_golden_signal_values(self):
        for v in GoldenSignal:
            assert isinstance(v.value, str)

    def test_signal_status_values(self):
        for v in SignalStatus:
            assert isinstance(v.value, str)

    def test_service_tier_values(self):
        for v in ServiceTier:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(service_id="s1")
        assert r.service_id == "s1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(service_id=f"s-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            service_id="s1",
            golden_signal=GoldenSignal.ERRORS,
            signal_status=SignalStatus.CRITICAL,
            service_tier=ServiceTier.TIER1,
            value=50.0,
            baseline=10.0,
        )
        assert r.value == 50.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(service_id="s1", value=50.0, baseline=10.0)
        a = eng.process(r.id)
        assert hasattr(a, "service_id")
        assert a.service_id == "s1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_anomaly_detected(self):
        eng = _engine()
        r = eng.add_record(
            service_id="s1",
            signal_status=SignalStatus.CRITICAL,
        )
        a = eng.process(r.id)
        assert a.anomaly_detected is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(service_id="s1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeGoldenSignalHealth:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", value=10.0, baseline=10.0)
        result = eng.compute_golden_signal_health()
        assert len(result) == 1
        assert result[0]["service_id"] == "s1"

    def test_empty(self):
        assert _engine().compute_golden_signal_health() == []


class TestDetectSignalAnomalies:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            service_id="s1",
            signal_status=SignalStatus.DEGRADED,
            value=50.0,
            baseline=10.0,
        )
        result = eng.detect_signal_anomalies()
        assert len(result) == 1
        assert result[0]["deviation"] == 40.0

    def test_empty(self):
        assert _engine().detect_signal_anomalies() == []


class TestRankServicesBySignalDegradation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(service_id="s1", value=50.0, baseline=10.0)
        eng.add_record(service_id="s2", value=20.0, baseline=10.0)
        result = eng.rank_services_by_signal_degradation()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_services_by_signal_degradation() == []
