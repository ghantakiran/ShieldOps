"""Tests for shieldops.security.automated_containment_engine — AutomatedContainmentEngine."""

from __future__ import annotations

from shieldops.security.automated_containment_engine import (
    AutomatedContainmentEngine,
    ContainmentAnalysis,
    ContainmentRecord,
    ContainmentReport,
    ContainmentScope,
    ContainmentStatus,
    ContainmentType,
)


def _engine(**kw) -> AutomatedContainmentEngine:
    return AutomatedContainmentEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_containmenttype_val1(self):
        assert ContainmentType.NETWORK_ISOLATION == "network_isolation"

    def test_containmenttype_val2(self):
        assert ContainmentType.PROCESS_KILL == "process_kill"

    def test_containmenttype_val3(self):
        assert ContainmentType.ACCOUNT_DISABLE == "account_disable"

    def test_containmenttype_val4(self):
        assert ContainmentType.DNS_SINKHOLE == "dns_sinkhole"

    def test_containmenttype_val5(self):
        assert ContainmentType.FIREWALL_BLOCK == "firewall_block"

    def test_containmentscope_val1(self):
        assert ContainmentScope.HOST == "host"

    def test_containmentscope_val2(self):
        assert ContainmentScope.NETWORK == "network"

    def test_containmentscope_val3(self):
        assert ContainmentScope.ACCOUNT == "account"

    def test_containmentscope_val4(self):
        assert ContainmentScope.APPLICATION == "application"

    def test_containmentscope_val5(self):
        assert ContainmentScope.SERVICE == "service"

    def test_containmentstatus_val1(self):
        assert ContainmentStatus.PENDING == "pending"

    def test_containmentstatus_val2(self):
        assert ContainmentStatus.EXECUTING == "executing"

    def test_containmentstatus_val3(self):
        assert ContainmentStatus.COMPLETED == "completed"

    def test_containmentstatus_val4(self):
        assert ContainmentStatus.FAILED == "failed"

    def test_containmentstatus_val5(self):
        assert ContainmentStatus.ROLLED_BACK == "rolled_back"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = ContainmentRecord()
        assert r.id
        assert r.name == ""
        assert r.containment_type == ContainmentType.NETWORK_ISOLATION
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ContainmentAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ContainmentReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_type == {}
        assert r.by_scope == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_containment(
            name="test",
            containment_type=ContainmentType.PROCESS_KILL,
            score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.name == "test"
        assert r.containment_type == ContainmentType.PROCESS_KILL
        assert r.score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_containment(name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_containment(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_containment(name="a")
        eng.record_containment(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_containment(name="a", containment_type=ContainmentType.NETWORK_ISOLATION)
        eng.record_containment(name="b", containment_type=ContainmentType.PROCESS_KILL)
        results = eng.list_records(containment_type=ContainmentType.NETWORK_ISOLATION)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_containment(name="a", containment_scope=ContainmentScope.HOST)
        eng.record_containment(name="b", containment_scope=ContainmentScope.NETWORK)
        results = eng.list_records(containment_scope=ContainmentScope.HOST)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_containment(name="a", team="sec")
        eng.record_containment(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_containment(name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_containment(
            name="a",
            containment_type=ContainmentType.NETWORK_ISOLATION,
            score=90.0,
        )
        eng.record_containment(
            name="b",
            containment_type=ContainmentType.NETWORK_ISOLATION,
            score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "network_isolation" in result
        assert result["network_isolation"]["count"] == 2
        assert result["network_isolation"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(score_threshold=80.0)
        eng.record_containment(name="a", score=60.0)
        eng.record_containment(name="b", score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(score_threshold=80.0)
        eng.record_containment(name="a", score=50.0)
        eng.record_containment(name="b", score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_containment(name="a", service="auth-svc", score=90.0)
        eng.record_containment(name="b", service="api-gw", score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="t1", analysis_score=20.0)
        eng.add_analysis(name="t2", analysis_score=20.0)
        eng.add_analysis(name="t3", analysis_score=80.0)
        eng.add_analysis(name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.record_containment(
            name="test",
            containment_type=ContainmentType.PROCESS_KILL,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ContainmentReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy range" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_containment(name="test")
        eng.add_analysis(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_containment(
            name="test",
            containment_type=ContainmentType.NETWORK_ISOLATION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "network_isolation" in stats["type_distribution"]
