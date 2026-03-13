"""Tests for LatencyDistributionAnalyzer."""

from __future__ import annotations

from shieldops.analytics.latency_distribution_analyzer import (
    AnalysisWindow,
    LatencyDistributionAnalyzer,
    LatencyTrend,
    PercentileBucket,
)


def _engine(**kw) -> LatencyDistributionAnalyzer:
    return LatencyDistributionAnalyzer(**kw)


class TestEnums:
    def test_percentile_bucket_values(self):
        for v in PercentileBucket:
            assert isinstance(v.value, str)

    def test_latency_trend_values(self):
        for v in LatencyTrend:
            assert isinstance(v.value, str)

    def test_analysis_window_values(self):
        for v in AnalysisWindow:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(endpoint_id="e1")
        assert r.endpoint_id == "e1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(endpoint_id=f"e-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            endpoint_id="e1",
            percentile_bucket=PercentileBucket.P99,
            latency_trend=LatencyTrend.DEGRADING,
            value_ms=800.0,
            baseline_ms=200.0,
            threshold_ms=500.0,
        )
        assert r.value_ms == 800.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(endpoint_id="e1", value_ms=100.0, baseline_ms=50.0)
        a = eng.process(r.id)
        assert hasattr(a, "endpoint_id")
        assert a.endpoint_id == "e1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_spike_detected(self):
        eng = _engine()
        r = eng.add_record(endpoint_id="e1", value_ms=600.0, threshold_ms=500.0)
        a = eng.process(r.id)
        assert a.spike_detected is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(endpoint_id="e1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(endpoint_id="e1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(endpoint_id="e1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputePercentileShifts:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(endpoint_id="e1", value_ms=300.0, baseline_ms=200.0)
        result = eng.compute_percentile_shifts()
        assert len(result) == 1
        assert result[0]["avg_shift_ms"] == 100.0

    def test_empty(self):
        assert _engine().compute_percentile_shifts() == []


class TestDetectTailLatencySpikes:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(endpoint_id="e1", value_ms=600.0, threshold_ms=500.0)
        result = eng.detect_tail_latency_spikes()
        assert len(result) == 1
        assert result[0]["excess_ms"] == 100.0

    def test_empty(self):
        assert _engine().detect_tail_latency_spikes() == []


class TestRankEndpointsByLatencyRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(endpoint_id="e1", value_ms=300.0)
        eng.add_record(endpoint_id="e2", value_ms=600.0)
        result = eng.rank_endpoints_by_latency_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_endpoints_by_latency_risk() == []
