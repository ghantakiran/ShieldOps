"""Tests for shieldops.analytics.latency_profiler — ServiceLatencyProfiler."""

from __future__ import annotations

from shieldops.analytics.latency_profiler import (
    LatencyProfile,
    LatencySample,
    PercentileBucket,
    ProfileWindow,
    RegressionAlert,
    RegressionSeverity,
    ServiceLatencyProfiler,
)


def _engine(**kw) -> ServiceLatencyProfiler:
    return ServiceLatencyProfiler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_p50(self):
        assert PercentileBucket.P50 == "p50"

    def test_p75(self):
        assert PercentileBucket.P75 == "p75"

    def test_p90(self):
        assert PercentileBucket.P90 == "p90"

    def test_p95(self):
        assert PercentileBucket.P95 == "p95"

    def test_p99(self):
        assert PercentileBucket.P99 == "p99"

    def test_severity_none(self):
        assert RegressionSeverity.NONE == "none"

    def test_severity_minor(self):
        assert RegressionSeverity.MINOR == "minor"

    def test_severity_moderate(self):
        assert RegressionSeverity.MODERATE == "moderate"

    def test_severity_major(self):
        assert RegressionSeverity.MAJOR == "major"

    def test_severity_critical(self):
        assert RegressionSeverity.CRITICAL == "critical"

    def test_window_hourly(self):
        assert ProfileWindow.HOURLY == "hourly"

    def test_window_daily(self):
        assert ProfileWindow.DAILY == "daily"

    def test_window_weekly(self):
        assert ProfileWindow.WEEKLY == "weekly"

    def test_window_monthly(self):
        assert ProfileWindow.MONTHLY == "monthly"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_sample_required_fields(self):
        s = LatencySample(service="svc-a", endpoint="/api/v1", latency_ms=10.5)
        assert s.id
        assert s.service == "svc-a"
        assert s.endpoint == "/api/v1"
        assert s.latency_ms == 10.5
        assert s.timestamp > 0

    def test_sample_id_unique(self):
        s1 = LatencySample(service="svc-a", endpoint="/api", latency_ms=1.0)
        s2 = LatencySample(service="svc-a", endpoint="/api", latency_ms=2.0)
        assert s1.id != s2.id

    def test_profile_defaults(self):
        p = LatencyProfile(service="svc-a", endpoint="/api")
        assert p.p50 == 0.0
        assert p.p75 == 0.0
        assert p.p90 == 0.0
        assert p.p95 == 0.0
        assert p.p99 == 0.0
        assert p.sample_count == 0
        assert p.window == ProfileWindow.DAILY

    def test_regression_alert_defaults(self):
        a = RegressionAlert(
            service="svc-a",
            endpoint="/api",
            percentile=PercentileBucket.P99,
            baseline_ms=10.0,
            current_ms=20.0,
        )
        assert a.severity == RegressionSeverity.NONE
        assert a.regression_pct == 0.0


# ---------------------------------------------------------------------------
# record_sample
# ---------------------------------------------------------------------------


class TestRecordSample:
    def test_basic_record(self):
        eng = _engine()
        sample = eng.record_sample("svc-a", "/api", 50.0)
        assert sample.service == "svc-a"
        assert sample.latency_ms == 50.0

    def test_evicts_at_max(self):
        eng = _engine(max_samples=3)
        for i in range(5):
            eng.record_sample("svc-a", "/api", float(i))
        assert len(eng._samples) == 3

    def test_preserves_most_recent_after_eviction(self):
        eng = _engine(max_samples=3)
        for i in range(5):
            eng.record_sample("svc-a", "/api", float(i))
        latencies = [s.latency_ms for s in eng._samples]
        assert latencies == [2.0, 3.0, 4.0]

    def test_multiple_endpoints(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api/v1", 10.0)
        eng.record_sample("svc-a", "/api/v2", 20.0)
        assert len(eng._samples) == 2


# ---------------------------------------------------------------------------
# compute_profile
# ---------------------------------------------------------------------------


class TestComputeProfile:
    def test_basic_profile(self):
        eng = _engine()
        for i in range(100):
            eng.record_sample("svc-a", "/api", float(i))
        profile = eng.compute_profile("svc-a", "/api")
        assert profile.sample_count == 100
        assert profile.p50 > 0
        assert profile.p99 > profile.p50

    def test_empty_profile(self):
        eng = _engine()
        profile = eng.compute_profile("svc-a", "/api")
        assert profile.sample_count == 0
        assert profile.p50 == 0.0

    def test_stored_in_profiles(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        profiles = eng.list_profiles()
        assert len(profiles) == 1

    def test_custom_window(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        profile = eng.compute_profile("svc-a", "/api", window=ProfileWindow.WEEKLY)
        assert profile.window == ProfileWindow.WEEKLY


# ---------------------------------------------------------------------------
# set_baseline / get_baseline
# ---------------------------------------------------------------------------


class TestBaseline:
    def test_set_baseline(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        baseline = eng.set_baseline("svc-a", "/api")
        assert baseline is not None

    def test_set_baseline_no_profile(self):
        eng = _engine()
        assert eng.set_baseline("svc-a", "/api") is None

    def test_get_baseline(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        eng.set_baseline("svc-a", "/api")
        baseline = eng.get_baseline("svc-a", "/api")
        assert baseline is not None

    def test_get_baseline_not_set(self):
        eng = _engine()
        assert eng.get_baseline("svc-a", "/api") is None


# ---------------------------------------------------------------------------
# detect_regressions
# ---------------------------------------------------------------------------


class TestDetectRegressions:
    def test_no_regression(self):
        eng = _engine()
        for _ in range(20):
            eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        eng.set_baseline("svc-a", "/api")
        alerts = eng.detect_regressions("svc-a", "/api")
        assert len(alerts) == 0

    def test_regression_detected(self):
        eng = _engine(regression_threshold=0.1)
        # Create baseline with low latencies
        for _ in range(20):
            eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        eng.set_baseline("svc-a", "/api")
        # Clear and add high latency samples
        eng._samples.clear()
        for _ in range(20):
            eng.record_sample("svc-a", "/api", 50.0)
        eng.compute_profile("svc-a", "/api")
        alerts = eng.detect_regressions("svc-a", "/api")
        assert len(alerts) > 0

    def test_regression_severity_critical(self):
        eng = _engine(regression_threshold=0.1)
        for _ in range(20):
            eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        eng.set_baseline("svc-a", "/api")
        eng._samples.clear()
        # >100% increase => critical
        for _ in range(20):
            eng.record_sample("svc-a", "/api", 100.0)
        eng.compute_profile("svc-a", "/api")
        alerts = eng.detect_regressions("svc-a", "/api")
        severities = {a.severity for a in alerts}
        assert RegressionSeverity.CRITICAL in severities

    def test_no_baseline(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        alerts = eng.detect_regressions("svc-a", "/api")
        assert len(alerts) == 0

    def test_no_current_profile(self):
        eng = _engine()
        # Only baseline set, no current profile (edge case: baseline is also the profile)
        eng.record_sample("svc-a", "/api", 10.0)
        eng.compute_profile("svc-a", "/api")
        eng.set_baseline("svc-a", "/api")
        # Since baseline == current, no regression
        alerts = eng.detect_regressions("svc-a", "/api")
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# list_profiles / ranking / samples / clear / stats
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_filter_by_service(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.record_sample("svc-b", "/api", 20.0)
        eng.compute_profile("svc-a", "/api")
        eng.compute_profile("svc-b", "/api")
        profiles = eng.list_profiles(service="svc-a")
        assert len(profiles) == 1

    def test_list_all(self):
        eng = _engine()
        eng.record_sample("svc-a", "/v1", 10.0)
        eng.record_sample("svc-b", "/v2", 20.0)
        eng.compute_profile("svc-a", "/v1")
        eng.compute_profile("svc-b", "/v2")
        profiles = eng.list_profiles()
        assert len(profiles) == 2


class TestEndpointRanking:
    def test_ranking(self):
        eng = _engine()
        eng.record_sample("svc-a", "/fast", 5.0)
        eng.record_sample("svc-a", "/slow", 100.0)
        eng.compute_profile("svc-a", "/fast")
        eng.compute_profile("svc-a", "/slow")
        ranking = eng.get_endpoint_ranking("svc-a")
        assert len(ranking) == 2
        assert ranking[0]["endpoint"] == "/slow"

    def test_ranking_empty_service(self):
        eng = _engine()
        ranking = eng.get_endpoint_ranking("nonexistent")
        assert ranking == []


class TestListSamples:
    def test_list_all(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.record_sample("svc-a", "/api", 20.0)
        samples = eng.list_samples()
        assert len(samples) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.record_sample("svc-b", "/api", 20.0)
        samples = eng.list_samples(service="svc-a")
        assert len(samples) == 1

    def test_filter_by_endpoint(self):
        eng = _engine()
        eng.record_sample("svc-a", "/v1", 10.0)
        eng.record_sample("svc-a", "/v2", 20.0)
        samples = eng.list_samples(endpoint="/v1")
        assert len(samples) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_sample("svc-a", "/api", float(i))
        samples = eng.list_samples(limit=3)
        assert len(samples) == 3


class TestClearSamples:
    def test_clear(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        count = eng.clear_samples()
        assert count == 1
        assert len(eng._samples) == 0

    def test_clear_empty(self):
        eng = _engine()
        count = eng.clear_samples()
        assert count == 0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_samples"] == 0
        assert stats["total_profiles"] == 0
        assert stats["total_baselines"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.record_sample("svc-a", "/api", 10.0)
        eng.record_sample("svc-b", "/api", 20.0)
        stats = eng.get_stats()
        assert stats["total_samples"] == 2
        assert stats["unique_services"] == 2

    def test_unique_endpoints(self):
        eng = _engine()
        eng.record_sample("svc-a", "/v1", 10.0)
        eng.record_sample("svc-a", "/v2", 20.0)
        stats = eng.get_stats()
        assert stats["unique_endpoints"] == 2
