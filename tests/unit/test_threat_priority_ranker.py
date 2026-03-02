"""Tests for shieldops.security.threat_priority_ranker — ThreatPriorityRanker."""

from __future__ import annotations

from shieldops.security.threat_priority_ranker import (
    PriorityAnalysis,
    PriorityLevel,
    PriorityRankingReport,
    PriorityRecord,
    RankingMethod,
    ThreatPriorityRanker,
    ThreatType,
)


def _engine(**kw) -> ThreatPriorityRanker:
    return ThreatPriorityRanker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_threattype_val1(self):
        assert ThreatType.MALWARE == "malware"

    def test_threattype_val2(self):
        assert ThreatType.RANSOMWARE == "ransomware"

    def test_threattype_val3(self):
        assert ThreatType.PHISHING == "phishing"

    def test_threattype_val4(self):
        assert ThreatType.APT == "apt"

    def test_threattype_val5(self):
        assert ThreatType.INSIDER == "insider"

    def test_prioritylevel_val1(self):
        assert PriorityLevel.CRITICAL == "critical"

    def test_prioritylevel_val2(self):
        assert PriorityLevel.HIGH == "high"

    def test_prioritylevel_val3(self):
        assert PriorityLevel.MEDIUM == "medium"

    def test_prioritylevel_val4(self):
        assert PriorityLevel.LOW == "low"

    def test_prioritylevel_val5(self):
        assert PriorityLevel.INFORMATIONAL == "informational"

    def test_rankingmethod_val1(self):
        assert RankingMethod.RISK_BASED == "risk_based"

    def test_rankingmethod_val2(self):
        assert RankingMethod.IMPACT_BASED == "impact_based"

    def test_rankingmethod_val3(self):
        assert RankingMethod.LIKELIHOOD_BASED == "likelihood_based"

    def test_rankingmethod_val4(self):
        assert RankingMethod.COMPOSITE == "composite"

    def test_rankingmethod_val5(self):
        assert RankingMethod.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = PriorityRecord()
        assert r.id
        assert r.threat_name == ""
        assert r.threat_type == ThreatType.MALWARE
        assert r.priority_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PriorityAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PriorityRankingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_priority_score == 0.0
        assert r.by_type == {}
        assert r.by_level == {}
        assert r.by_method == {}
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
        r = eng.record_priority(
            threat_name="test",
            threat_type=ThreatType.RANSOMWARE,
            priority_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.threat_name == "test"
        assert r.threat_type == ThreatType.RANSOMWARE
        assert r.priority_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_priority(threat_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_priority(threat_name="test")
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
        eng.record_priority(threat_name="a")
        eng.record_priority(threat_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_priority(threat_name="a", threat_type=ThreatType.MALWARE)
        eng.record_priority(threat_name="b", threat_type=ThreatType.RANSOMWARE)
        results = eng.list_records(threat_type=ThreatType.MALWARE)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_priority(threat_name="a", priority_level=PriorityLevel.CRITICAL)
        eng.record_priority(threat_name="b", priority_level=PriorityLevel.HIGH)
        results = eng.list_records(priority_level=PriorityLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_priority(threat_name="a", team="sec")
        eng.record_priority(threat_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_priority(threat_name=f"t-{i}")
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
        eng.record_priority(
            threat_name="a",
            threat_type=ThreatType.MALWARE,
            priority_score=90.0,
        )
        eng.record_priority(
            threat_name="b",
            threat_type=ThreatType.MALWARE,
            priority_score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "malware" in result
        assert result["malware"]["count"] == 2
        assert result["malware"]["avg_priority_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_priority(threat_name="a", priority_score=60.0)
        eng.record_priority(threat_name="b", priority_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["threat_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_priority(threat_name="a", priority_score=50.0)
        eng.record_priority(threat_name="b", priority_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["priority_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_priority(threat_name="a", service="auth-svc", priority_score=90.0)
        eng.record_priority(threat_name="b", service="api-gw", priority_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_priority_score"] == 50.0

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
        eng.record_priority(
            threat_name="test",
            threat_type=ThreatType.RANSOMWARE,
            priority_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PriorityRankingReport)
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
        eng.record_priority(threat_name="test")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_priority(
            threat_name="test",
            threat_type=ThreatType.MALWARE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "malware" in stats["type_distribution"]
