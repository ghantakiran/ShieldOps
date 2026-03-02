"""Tests for shieldops.security.threat_actor_ttp_profiler — ThreatActorTTPProfiler."""

from __future__ import annotations

from shieldops.security.threat_actor_ttp_profiler import (
    ActorSophistication,
    ProfileConfidence,
    ThreatActorTTPProfiler,
    TTPAnalysis,
    TTPCategory,
    TTPProfileReport,
    TTPRecord,
)


def _engine(**kw) -> ThreatActorTTPProfiler:
    return ThreatActorTTPProfiler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_ttpcategory_val1(self):
        assert TTPCategory.INITIAL_ACCESS == "initial_access"

    def test_ttpcategory_val2(self):
        assert TTPCategory.EXECUTION == "execution"

    def test_ttpcategory_val3(self):
        assert TTPCategory.PERSISTENCE == "persistence"

    def test_ttpcategory_val4(self):
        assert TTPCategory.LATERAL_MOVEMENT == "lateral_movement"

    def test_ttpcategory_val5(self):
        assert TTPCategory.EXFILTRATION == "exfiltration"

    def test_actorsophistication_val1(self):
        assert ActorSophistication.ADVANCED == "advanced"

    def test_actorsophistication_val2(self):
        assert ActorSophistication.INTERMEDIATE == "intermediate"

    def test_actorsophistication_val3(self):
        assert ActorSophistication.BASIC == "basic"

    def test_actorsophistication_val4(self):
        assert ActorSophistication.SCRIPT_KIDDIE == "script_kiddie"

    def test_actorsophistication_val5(self):
        assert ActorSophistication.UNKNOWN == "unknown"

    def test_profileconfidence_val1(self):
        assert ProfileConfidence.HIGH == "high"

    def test_profileconfidence_val2(self):
        assert ProfileConfidence.MEDIUM == "medium"

    def test_profileconfidence_val3(self):
        assert ProfileConfidence.LOW == "low"

    def test_profileconfidence_val4(self):
        assert ProfileConfidence.SPECULATIVE == "speculative"

    def test_profileconfidence_val5(self):
        assert ProfileConfidence.UNVERIFIED == "unverified"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = TTPRecord()
        assert r.id
        assert r.actor_name == ""
        assert r.ttp_category == TTPCategory.INITIAL_ACCESS
        assert r.technique_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = TTPAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = TTPProfileReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_technique_score == 0.0
        assert r.by_category == {}
        assert r.by_sophistication == {}
        assert r.by_confidence == {}
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
        r = eng.record_ttp(
            actor_name="test",
            ttp_category=TTPCategory.EXECUTION,
            technique_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.actor_name == "test"
        assert r.ttp_category == TTPCategory.EXECUTION
        assert r.technique_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_ttp(actor_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_ttp(actor_name="test")
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
        eng.record_ttp(actor_name="a")
        eng.record_ttp(actor_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_ttp(actor_name="a", ttp_category=TTPCategory.INITIAL_ACCESS)
        eng.record_ttp(actor_name="b", ttp_category=TTPCategory.EXECUTION)
        results = eng.list_records(ttp_category=TTPCategory.INITIAL_ACCESS)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_ttp(actor_name="a", actor_sophistication=ActorSophistication.ADVANCED)
        eng.record_ttp(actor_name="b", actor_sophistication=ActorSophistication.INTERMEDIATE)
        results = eng.list_records(actor_sophistication=ActorSophistication.ADVANCED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_ttp(actor_name="a", team="sec")
        eng.record_ttp(actor_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_ttp(actor_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            actor_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(actor_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_ttp(
            actor_name="a",
            ttp_category=TTPCategory.INITIAL_ACCESS,
            technique_score=90.0,
        )
        eng.record_ttp(
            actor_name="b",
            ttp_category=TTPCategory.INITIAL_ACCESS,
            technique_score=70.0,
        )
        result = eng.analyze_category_distribution()
        assert "initial_access" in result
        assert result["initial_access"]["count"] == 2
        assert result["initial_access"]["avg_technique_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_category_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_ttp(actor_name="a", technique_score=60.0)
        eng.record_ttp(actor_name="b", technique_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["actor_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_ttp(actor_name="a", technique_score=50.0)
        eng.record_ttp(actor_name="b", technique_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["technique_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_ttp(actor_name="a", service="auth-svc", technique_score=90.0)
        eng.record_ttp(actor_name="b", service="api-gw", technique_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_technique_score"] == 50.0

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
            eng.add_analysis(actor_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(actor_name="t1", analysis_score=20.0)
        eng.add_analysis(actor_name="t2", analysis_score=20.0)
        eng.add_analysis(actor_name="t3", analysis_score=80.0)
        eng.add_analysis(actor_name="t4", analysis_score=80.0)
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
        eng = _engine(quality_threshold=80.0)
        eng.record_ttp(
            actor_name="test",
            ttp_category=TTPCategory.EXECUTION,
            technique_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, TTPProfileReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_ttp(actor_name="test")
        eng.add_analysis(actor_name="test")
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
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_ttp(
            actor_name="test",
            ttp_category=TTPCategory.INITIAL_ACCESS,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "initial_access" in stats["category_distribution"]
