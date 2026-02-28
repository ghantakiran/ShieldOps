"""Tests for shieldops.incidents.response_timer — IncidentResponseTimer."""

from __future__ import annotations

from shieldops.incidents.response_timer import (
    BenchmarkType,
    IncidentResponseTimer,
    ResponseBenchmark,
    ResponsePhase,
    ResponseSpeed,
    ResponseTimerRecord,
    ResponseTimerReport,
)


def _engine(**kw) -> IncidentResponseTimer:
    return IncidentResponseTimer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ResponsePhase (5)
    def test_phase_detection(self):
        assert ResponsePhase.DETECTION == "detection"

    def test_phase_acknowledgment(self):
        assert ResponsePhase.ACKNOWLEDGMENT == "acknowledgment"

    def test_phase_investigation(self):
        assert ResponsePhase.INVESTIGATION == "investigation"

    def test_phase_mitigation(self):
        assert ResponsePhase.MITIGATION == "mitigation"

    def test_phase_resolution(self):
        assert ResponsePhase.RESOLUTION == "resolution"

    # ResponseSpeed (5)
    def test_speed_excellent(self):
        assert ResponseSpeed.EXCELLENT == "excellent"

    def test_speed_fast(self):
        assert ResponseSpeed.FAST == "fast"

    def test_speed_acceptable(self):
        assert ResponseSpeed.ACCEPTABLE == "acceptable"

    def test_speed_slow(self):
        assert ResponseSpeed.SLOW == "slow"

    def test_speed_critical(self):
        assert ResponseSpeed.CRITICAL == "critical"

    # BenchmarkType (5)
    def test_benchmark_industry(self):
        assert BenchmarkType.INDUSTRY == "industry"

    def test_benchmark_organizational(self):
        assert BenchmarkType.ORGANIZATIONAL == "organizational"

    def test_benchmark_team(self):
        assert BenchmarkType.TEAM == "team"

    def test_benchmark_service(self):
        assert BenchmarkType.SERVICE == "service"

    def test_benchmark_historical(self):
        assert BenchmarkType.HISTORICAL == "historical"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_response_timer_record_defaults(self):
        r = ResponseTimerRecord()
        assert r.id
        assert r.service_name == ""
        assert r.phase == ResponsePhase.DETECTION
        assert r.speed == ResponseSpeed.EXCELLENT
        assert r.benchmark_type == BenchmarkType.INDUSTRY
        assert r.duration_minutes == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_response_benchmark_defaults(self):
        r = ResponseBenchmark()
        assert r.id
        assert r.benchmark_name == ""
        assert r.phase == ResponsePhase.DETECTION
        assert r.speed == ResponseSpeed.ACCEPTABLE
        assert r.target_minutes == 30.0
        assert r.percentile == 95.0
        assert r.created_at > 0

    def test_response_timer_report_defaults(self):
        r = ResponseTimerReport()
        assert r.total_responses == 0
        assert r.total_benchmarks == 0
        assert r.on_target_rate_pct == 0.0
        assert r.by_phase == {}
        assert r.by_speed == {}
        assert r.slow_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_response_time
# -------------------------------------------------------------------


class TestRecordResponseTime:
    def test_basic(self):
        eng = _engine()
        r = eng.record_response_time("api-gateway", phase=ResponsePhase.DETECTION)
        assert r.service_name == "api-gateway"
        assert r.phase == ResponsePhase.DETECTION

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_response_time(
            "payment-service",
            phase=ResponsePhase.MITIGATION,
            speed=ResponseSpeed.SLOW,
            benchmark_type=BenchmarkType.ORGANIZATIONAL,
            duration_minutes=45.0,
            details="Slow mitigation due to complexity",
        )
        assert r.speed == ResponseSpeed.SLOW
        assert r.benchmark_type == BenchmarkType.ORGANIZATIONAL
        assert r.duration_minutes == 45.0
        assert r.details == "Slow mitigation due to complexity"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_response_time(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_response_time
# -------------------------------------------------------------------


class TestGetResponseTime:
    def test_found(self):
        eng = _engine()
        r = eng.record_response_time("api-gateway")
        assert eng.get_response_time(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_response_time("nonexistent") is None


# -------------------------------------------------------------------
# list_response_times
# -------------------------------------------------------------------


class TestListResponseTimes:
    def test_list_all(self):
        eng = _engine()
        eng.record_response_time("svc-a")
        eng.record_response_time("svc-b")
        assert len(eng.list_response_times()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_response_time("svc-a")
        eng.record_response_time("svc-b")
        results = eng.list_response_times(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_response_time("svc-a", phase=ResponsePhase.DETECTION)
        eng.record_response_time("svc-b", phase=ResponsePhase.RESOLUTION)
        results = eng.list_response_times(phase=ResponsePhase.RESOLUTION)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_benchmark
# -------------------------------------------------------------------


class TestAddBenchmark:
    def test_basic(self):
        eng = _engine()
        b = eng.add_benchmark(
            "fast-detection",
            phase=ResponsePhase.DETECTION,
            speed=ResponseSpeed.FAST,
            target_minutes=5.0,
            percentile=99.0,
        )
        assert b.benchmark_name == "fast-detection"
        assert b.phase == ResponsePhase.DETECTION
        assert b.target_minutes == 5.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_benchmark(f"bench-{i}")
        assert len(eng._benchmarks) == 2


# -------------------------------------------------------------------
# analyze_response_speed
# -------------------------------------------------------------------


class TestAnalyzeResponseSpeed:
    def test_with_data(self):
        eng = _engine(target_minutes=30.0)
        eng.record_response_time("svc-a", duration_minutes=20.0)
        eng.record_response_time("svc-a", duration_minutes=40.0)
        eng.record_response_time("svc-a", duration_minutes=30.0)
        result = eng.analyze_response_speed("svc-a")
        assert result["avg_duration"] == 30.0
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_response_speed("unknown-svc")
        assert result["status"] == "no_data"

    def test_meets_target(self):
        eng = _engine(target_minutes=30.0)
        eng.record_response_time("svc-a", duration_minutes=10.0)
        eng.record_response_time("svc-a", duration_minutes=20.0)
        result = eng.analyze_response_speed("svc-a")
        assert result["meets_target"] is True


# -------------------------------------------------------------------
# identify_slow_responses
# -------------------------------------------------------------------


class TestIdentifySlowResponses:
    def test_with_slow(self):
        eng = _engine()
        eng.record_response_time("svc-a", speed=ResponseSpeed.SLOW)
        eng.record_response_time("svc-a", speed=ResponseSpeed.CRITICAL)
        eng.record_response_time("svc-b", speed=ResponseSpeed.EXCELLENT)
        results = eng.identify_slow_responses()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["slow_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_responses() == []

    def test_single_slow_not_returned(self):
        eng = _engine()
        eng.record_response_time("svc-a", speed=ResponseSpeed.SLOW)
        assert eng.identify_slow_responses() == []


# -------------------------------------------------------------------
# rank_by_response_time
# -------------------------------------------------------------------


class TestRankByResponseTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_response_time("svc-a", duration_minutes=50.0)
        eng.record_response_time("svc-b", duration_minutes=10.0)
        results = eng.rank_by_response_time()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_duration_minutes"] == 10.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_response_time() == []


# -------------------------------------------------------------------
# detect_response_trends
# -------------------------------------------------------------------


class TestDetectResponseTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_response_time("svc-a")
        eng.record_response_time("svc-b")
        results = eng.detect_response_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_response_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_response_time("svc-a")
        assert eng.detect_response_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_response_time("svc-a", speed=ResponseSpeed.SLOW)
        eng.record_response_time("svc-b", speed=ResponseSpeed.EXCELLENT)
        eng.add_benchmark("bench-1")
        report = eng.generate_report()
        assert report.total_responses == 2
        assert report.total_benchmarks == 1
        assert report.by_phase != {}
        assert report.by_speed != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_responses == 0
        assert report.on_target_rate_pct == 0.0
        assert "meet targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_response_time("svc-a")
        eng.add_benchmark("bench-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._benchmarks) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_responses"] == 0
        assert stats["total_benchmarks"] == 0
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine(target_minutes=30.0)
        eng.record_response_time("svc-a", phase=ResponsePhase.DETECTION)
        eng.record_response_time("svc-b", phase=ResponsePhase.RESOLUTION)
        eng.add_benchmark("bench-1")
        stats = eng.get_stats()
        assert stats["total_responses"] == 2
        assert stats["total_benchmarks"] == 1
        assert stats["unique_services"] == 2
        assert stats["target_minutes"] == 30.0
