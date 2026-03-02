"""Tests for shieldops.security.strategic_threat_landscape — StrategicThreatLandscape."""

from __future__ import annotations

from shieldops.security.strategic_threat_landscape import (
    LandscapeAnalysis,
    LandscapeRecord,
    LandscapeReport,
    LandscapeScope,
    StrategicThreatLandscape,
    ThreatCategory,
    ThreatLevel,
)


def _engine(**kw) -> StrategicThreatLandscape:
    return StrategicThreatLandscape(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_threatcategory_val1(self):
        assert ThreatCategory.NATION_STATE == "nation_state"

    def test_threatcategory_val2(self):
        assert ThreatCategory.CYBERCRIME == "cybercrime"

    def test_threatcategory_val3(self):
        assert ThreatCategory.HACKTIVISM == "hacktivism"

    def test_threatcategory_val4(self):
        assert ThreatCategory.INSIDER_THREAT == "insider_threat"

    def test_threatcategory_val5(self):
        assert ThreatCategory.SUPPLY_CHAIN == "supply_chain"

    def test_threatlevel_val1(self):
        assert ThreatLevel.CRITICAL == "critical"

    def test_threatlevel_val2(self):
        assert ThreatLevel.HIGH == "high"

    def test_threatlevel_val3(self):
        assert ThreatLevel.ELEVATED == "elevated"

    def test_threatlevel_val4(self):
        assert ThreatLevel.GUARDED == "guarded"

    def test_threatlevel_val5(self):
        assert ThreatLevel.LOW == "low"

    def test_landscapescope_val1(self):
        assert LandscapeScope.GLOBAL_SCOPE == "global_scope"

    def test_landscapescope_val2(self):
        assert LandscapeScope.REGIONAL == "regional"

    def test_landscapescope_val3(self):
        assert LandscapeScope.SECTOR == "sector"

    def test_landscapescope_val4(self):
        assert LandscapeScope.ORGANIZATION == "organization"

    def test_landscapescope_val5(self):
        assert LandscapeScope.ASSET == "asset"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = LandscapeRecord()
        assert r.id
        assert r.threat_name == ""
        assert r.threat_category == ThreatCategory.CYBERCRIME
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = LandscapeAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = LandscapeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_category == {}
        assert r.by_level == {}
        assert r.by_scope == {}
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
        r = eng.record_threat(
            threat_name="test",
            threat_category=ThreatCategory.CYBERCRIME,
            risk_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.threat_name == "test"
        assert r.threat_category == ThreatCategory.CYBERCRIME
        assert r.risk_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_threat(threat_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_threat(threat_name="test")
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
        eng.record_threat(threat_name="a")
        eng.record_threat(threat_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_threat(threat_name="a", threat_category=ThreatCategory.NATION_STATE)
        eng.record_threat(threat_name="b", threat_category=ThreatCategory.CYBERCRIME)
        results = eng.list_records(threat_category=ThreatCategory.NATION_STATE)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_threat(threat_name="a", threat_level=ThreatLevel.CRITICAL)
        eng.record_threat(threat_name="b", threat_level=ThreatLevel.HIGH)
        results = eng.list_records(threat_level=ThreatLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_threat(threat_name="a", team="sec")
        eng.record_threat(threat_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_threat(threat_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            threat_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(threat_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_threat(
            threat_name="a",
            threat_category=ThreatCategory.NATION_STATE,
            risk_score=90.0,
        )
        eng.record_threat(
            threat_name="b",
            threat_category=ThreatCategory.NATION_STATE,
            risk_score=70.0,
        )
        result = eng.analyze_category_distribution()
        assert "nation_state" in result
        assert result["nation_state"]["count"] == 2
        assert result["nation_state"]["avg_risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_category_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_threat(threat_name="a", risk_score=60.0)
        eng.record_threat(threat_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["threat_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_threat(threat_name="a", risk_score=50.0)
        eng.record_threat(threat_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_threat(threat_name="a", service="auth-svc", risk_score=90.0)
        eng.record_threat(threat_name="b", service="api-gw", risk_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_risk_score"] == 50.0

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
            eng.add_analysis(threat_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(threat_name="t1", analysis_score=20.0)
        eng.add_analysis(threat_name="t2", analysis_score=20.0)
        eng.add_analysis(threat_name="t3", analysis_score=80.0)
        eng.add_analysis(threat_name="t4", analysis_score=80.0)
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
        eng.record_threat(
            threat_name="test",
            threat_category=ThreatCategory.CYBERCRIME,
            risk_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, LandscapeReport)
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
        eng.record_threat(threat_name="test")
        eng.add_analysis(threat_name="test")
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
        eng.record_threat(
            threat_name="test",
            threat_category=ThreatCategory.NATION_STATE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "nation_state" in stats["category_distribution"]
