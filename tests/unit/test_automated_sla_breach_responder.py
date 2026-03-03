"""Tests for shieldops.sla.automated_sla_breach_responder — AutomatedSlaBreachResponder."""

from __future__ import annotations

from shieldops.sla.automated_sla_breach_responder import (
    AutomatedSlaBreachReport,
    AutomatedSlaBreachResponder,
    BreachAnalysis,
    BreachRecord,
    BreachSeverity,
    BreachType,
    ResponseStrategy,
)


def _engine(**kw) -> AutomatedSlaBreachResponder:
    return AutomatedSlaBreachResponder(**kw)


class TestEnums:
    def test_breach_type_availability(self):
        assert BreachType.AVAILABILITY == "availability"

    def test_breach_type_latency(self):
        assert BreachType.LATENCY == "latency"

    def test_breach_type_error_rate(self):
        assert BreachType.ERROR_RATE == "error_rate"

    def test_breach_type_throughput(self):
        assert BreachType.THROUGHPUT == "throughput"

    def test_breach_type_response_time(self):
        assert BreachType.RESPONSE_TIME == "response_time"

    def test_response_strategy_scaling(self):
        assert ResponseStrategy.SCALING == "scaling"

    def test_response_strategy_failover(self):
        assert ResponseStrategy.FAILOVER == "failover"

    def test_response_strategy_traffic_shift(self):
        assert ResponseStrategy.TRAFFIC_SHIFT == "traffic_shift"

    def test_response_strategy_degradation(self):
        assert ResponseStrategy.DEGRADATION == "degradation"

    def test_response_strategy_notification(self):
        assert ResponseStrategy.NOTIFICATION == "notification"

    def test_breach_severity_critical(self):
        assert BreachSeverity.CRITICAL == "critical"

    def test_breach_severity_major(self):
        assert BreachSeverity.MAJOR == "major"

    def test_breach_severity_minor(self):
        assert BreachSeverity.MINOR == "minor"

    def test_breach_severity_warning(self):
        assert BreachSeverity.WARNING == "warning"

    def test_breach_severity_informational(self):
        assert BreachSeverity.INFORMATIONAL == "informational"


class TestModels:
    def test_record_defaults(self):
        r = BreachRecord()
        assert r.id
        assert r.name == ""
        assert r.breach_type == BreachType.AVAILABILITY
        assert r.response_strategy == ResponseStrategy.SCALING
        assert r.breach_severity == BreachSeverity.INFORMATIONAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = BreachAnalysis()
        assert a.id
        assert a.name == ""
        assert a.breach_type == BreachType.AVAILABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AutomatedSlaBreachReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_breach_type == {}
        assert r.by_response_strategy == {}
        assert r.by_breach_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            breach_type=BreachType.AVAILABILITY,
            response_strategy=ResponseStrategy.FAILOVER,
            breach_severity=BreachSeverity.CRITICAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.breach_type == BreachType.AVAILABILITY
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_breach_type(self):
        eng = _engine()
        eng.record_entry(name="a", breach_type=BreachType.AVAILABILITY)
        eng.record_entry(name="b", breach_type=BreachType.LATENCY)
        assert len(eng.list_records(breach_type=BreachType.AVAILABILITY)) == 1

    def test_filter_by_response_strategy(self):
        eng = _engine()
        eng.record_entry(name="a", response_strategy=ResponseStrategy.SCALING)
        eng.record_entry(name="b", response_strategy=ResponseStrategy.FAILOVER)
        assert len(eng.list_records(response_strategy=ResponseStrategy.SCALING)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", breach_type=BreachType.LATENCY, score=90.0)
        eng.record_entry(name="b", breach_type=BreachType.LATENCY, score=70.0)
        result = eng.analyze_distribution()
        assert "latency" in result
        assert result["latency"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
