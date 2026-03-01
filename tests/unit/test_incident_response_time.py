"""Tests for shieldops.incidents.incident_response_time — IncidentResponseTimeTracker."""

from __future__ import annotations

from shieldops.incidents.incident_response_time import (
    IncidentResponseTimeReport,
    IncidentResponseTimeTracker,
    ResponseBenchmark,
    ResponseChannel,
    ResponsePhase,
    ResponseSpeed,
    ResponseTimeRecord,
)


def _engine(**kw) -> IncidentResponseTimeTracker:
    return IncidentResponseTimeTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_phase_detection(self):
        assert ResponsePhase.DETECTION == "detection"

    def test_phase_triage(self):
        assert ResponsePhase.TRIAGE == "triage"

    def test_phase_investigation(self):
        assert ResponsePhase.INVESTIGATION == "investigation"

    def test_phase_mitigation(self):
        assert ResponsePhase.MITIGATION == "mitigation"

    def test_phase_resolution(self):
        assert ResponsePhase.RESOLUTION == "resolution"

    def test_speed_excellent(self):
        assert ResponseSpeed.EXCELLENT == "excellent"

    def test_speed_good(self):
        assert ResponseSpeed.GOOD == "good"

    def test_speed_acceptable(self):
        assert ResponseSpeed.ACCEPTABLE == "acceptable"

    def test_speed_slow(self):
        assert ResponseSpeed.SLOW == "slow"

    def test_speed_critical(self):
        assert ResponseSpeed.CRITICAL == "critical"

    def test_channel_automated(self):
        assert ResponseChannel.AUTOMATED == "automated"

    def test_channel_pager(self):
        assert ResponseChannel.PAGER == "pager"

    def test_channel_slack(self):
        assert ResponseChannel.SLACK == "slack"

    def test_channel_email(self):
        assert ResponseChannel.EMAIL == "email"

    def test_channel_manual(self):
        assert ResponseChannel.MANUAL == "manual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_response_time_record_defaults(self):
        r = ResponseTimeRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.response_phase == ResponsePhase.DETECTION
        assert r.response_speed == ResponseSpeed.ACCEPTABLE
        assert r.response_channel == ResponseChannel.AUTOMATED
        assert r.response_time_minutes == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_response_benchmark_defaults(self):
        b = ResponseBenchmark()
        assert b.id
        assert b.incident_id == ""
        assert b.response_phase == ResponsePhase.DETECTION
        assert b.benchmark_score == 0.0
        assert b.threshold == 0.0
        assert b.breached is False
        assert b.description == ""
        assert b.created_at > 0

    def test_report_defaults(self):
        r = IncidentResponseTimeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_benchmarks == 0
        assert r.slow_responses == 0
        assert r.avg_response_time_minutes == 0.0
        assert r.by_phase == {}
        assert r.by_speed == {}
        assert r.by_channel == {}
        assert r.top_slow_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_response
# ---------------------------------------------------------------------------


class TestRecordResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            response_speed=ResponseSpeed.SLOW,
            response_channel=ResponseChannel.PAGER,
            response_time_minutes=45.0,
            service="api-gateway",
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.response_phase == ResponsePhase.TRIAGE
        assert r.response_speed == ResponseSpeed.SLOW
        assert r.response_channel == ResponseChannel.PAGER
        assert r.response_time_minutes == 45.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_response(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_response
# ---------------------------------------------------------------------------


class TestGetResponse:
    def test_found(self):
        eng = _engine()
        r = eng.record_response(
            incident_id="INC-001",
            response_speed=ResponseSpeed.EXCELLENT,
        )
        result = eng.get_response(r.id)
        assert result is not None
        assert result.response_speed == ResponseSpeed.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_response("nonexistent") is None


# ---------------------------------------------------------------------------
# list_responses
# ---------------------------------------------------------------------------


class TestListResponses:
    def test_list_all(self):
        eng = _engine()
        eng.record_response(incident_id="INC-001")
        eng.record_response(incident_id="INC-002")
        assert len(eng.list_responses()) == 2

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
        )
        eng.record_response(
            incident_id="INC-002",
            response_phase=ResponsePhase.RESOLUTION,
        )
        results = eng.list_responses(
            response_phase=ResponsePhase.TRIAGE,
        )
        assert len(results) == 1

    def test_filter_by_speed(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_speed=ResponseSpeed.SLOW,
        )
        eng.record_response(
            incident_id="INC-002",
            response_speed=ResponseSpeed.EXCELLENT,
        )
        results = eng.list_responses(
            response_speed=ResponseSpeed.SLOW,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_response(incident_id="INC-001", team="sre")
        eng.record_response(incident_id="INC-002", team="platform")
        results = eng.list_responses(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_response(incident_id=f"INC-{i}")
        assert len(eng.list_responses(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_benchmark
# ---------------------------------------------------------------------------


class TestAddBenchmark:
    def test_basic(self):
        eng = _engine()
        b = eng.add_benchmark(
            incident_id="INC-001",
            response_phase=ResponsePhase.MITIGATION,
            benchmark_score=85.0,
            threshold=70.0,
            breached=False,
            description="Within threshold",
        )
        assert b.incident_id == "INC-001"
        assert b.response_phase == ResponsePhase.MITIGATION
        assert b.benchmark_score == 85.0
        assert b.threshold == 70.0
        assert b.breached is False

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_benchmark(incident_id=f"INC-{i}")
        assert len(eng._benchmarks) == 2


# ---------------------------------------------------------------------------
# analyze_response_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeResponseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            response_time_minutes=10.0,
        )
        eng.record_response(
            incident_id="INC-002",
            response_phase=ResponsePhase.TRIAGE,
            response_time_minutes=20.0,
        )
        result = eng.analyze_response_distribution()
        assert "triage" in result
        assert result["triage"]["count"] == 2
        assert result["triage"]["avg_response_time"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_response_distribution() == {}


# ---------------------------------------------------------------------------
# identify_slow_responses
# ---------------------------------------------------------------------------


class TestIdentifySlowResponses:
    def test_detects_slow(self):
        eng = _engine(max_response_time_minutes=30.0)
        eng.record_response(
            incident_id="INC-001",
            response_time_minutes=45.0,
            service="api",
        )
        eng.record_response(
            incident_id="INC-002",
            response_time_minutes=10.0,
            service="web",
        )
        results = eng.identify_slow_responses()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_responses() == []


# ---------------------------------------------------------------------------
# rank_by_response_time
# ---------------------------------------------------------------------------


class TestRankByResponseTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            service="slow-svc",
            response_time_minutes=60.0,
        )
        eng.record_response(
            incident_id="INC-002",
            service="fast-svc",
            response_time_minutes=5.0,
        )
        results = eng.rank_by_response_time()
        assert len(results) == 2
        assert results[0]["service"] == "slow-svc"
        assert results[0]["avg_response_time"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_response_time() == []


# ---------------------------------------------------------------------------
# detect_response_trends
# ---------------------------------------------------------------------------


class TestDetectResponseTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_benchmark(incident_id="INC-001", benchmark_score=50.0)
        result = eng.detect_response_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_benchmark(incident_id="INC-001", benchmark_score=30.0)
        eng.add_benchmark(incident_id="INC-002", benchmark_score=30.0)
        eng.add_benchmark(incident_id="INC-003", benchmark_score=80.0)
        eng.add_benchmark(incident_id="INC-004", benchmark_score=80.0)
        result = eng.detect_response_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_response_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_response_time_minutes=30.0)
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            response_speed=ResponseSpeed.SLOW,
            response_channel=ResponseChannel.PAGER,
            response_time_minutes=45.0,
            service="api-gateway",
        )
        report = eng.generate_report()
        assert isinstance(report, IncidentResponseTimeReport)
        assert report.total_records == 1
        assert report.slow_responses == 1
        assert len(report.top_slow_services) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_response(incident_id="INC-001")
        eng.add_benchmark(incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._benchmarks) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_benchmarks"] == 0
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_incidents"] == 1
        assert "triage" in stats["phase_distribution"]
