"""Tests for shieldops.security.attack_path_analyzer — AttackPathAnalyzer."""

from __future__ import annotations

from shieldops.security.attack_path_analyzer import (
    AttackPathAnalysis,
    AttackPathAnalyzer,
    AttackPathRecord,
    AttackPathReport,
    PathComplexity,
    PathRisk,
    PathType,
)


def _engine(**kw) -> AttackPathAnalyzer:
    return AttackPathAnalyzer(**kw)


class TestEnums:
    def test_pathtype_val1(self):
        assert PathType.NETWORK == "network"

    def test_pathtype_val2(self):
        assert PathType.IDENTITY == "identity"

    def test_pathtype_val3(self):
        assert PathType.APPLICATION == "application"

    def test_pathtype_val4(self):
        assert PathType.CLOUD == "cloud"

    def test_pathtype_val5(self):
        assert PathType.HYBRID == "hybrid"

    def test_pathcomplexity_val1(self):
        assert PathComplexity.TRIVIAL == "trivial"

    def test_pathcomplexity_val2(self):
        assert PathComplexity.SIMPLE == "simple"

    def test_pathcomplexity_val3(self):
        assert PathComplexity.MODERATE == "moderate"

    def test_pathcomplexity_val4(self):
        assert PathComplexity.COMPLEX == "complex"

    def test_pathcomplexity_val5(self):
        assert PathComplexity.EXPERT == "expert"

    def test_pathrisk_val1(self):
        assert PathRisk.CRITICAL == "critical"

    def test_pathrisk_val2(self):
        assert PathRisk.HIGH == "high"

    def test_pathrisk_val3(self):
        assert PathRisk.MEDIUM == "medium"

    def test_pathrisk_val4(self):
        assert PathRisk.LOW == "low"

    def test_pathrisk_val5(self):
        assert PathRisk.THEORETICAL == "theoretical"


class TestModels:
    def test_record_defaults(self):
        r = AttackPathRecord()
        assert r.id
        assert r.path_name == ""

    def test_analysis_defaults(self):
        a = AttackPathAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = AttackPathReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_path(
            path_name="test",
            path_type=PathType.IDENTITY,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.path_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_path(path_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_path(path_name="test")
        assert eng.get_path(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_path("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_path(path_name="a")
        eng.record_path(path_name="b")
        assert len(eng.list_paths()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_path(path_name="a", path_type=PathType.NETWORK)
        eng.record_path(path_name="b", path_type=PathType.IDENTITY)
        assert len(eng.list_paths(path_type=PathType.NETWORK)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_path(path_name="a", path_complexity=PathComplexity.TRIVIAL)
        eng.record_path(path_name="b", path_complexity=PathComplexity.SIMPLE)
        assert len(eng.list_paths(path_complexity=PathComplexity.TRIVIAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_path(path_name="a", team="sec")
        eng.record_path(path_name="b", team="ops")
        assert len(eng.list_paths(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_path(path_name=f"t-{i}")
        assert len(eng.list_paths(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            path_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(path_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_path(path_name="a", path_type=PathType.NETWORK, risk_score=90.0)
        eng.record_path(path_name="b", path_type=PathType.NETWORK, risk_score=70.0)
        result = eng.analyze_distribution()
        assert PathType.NETWORK.value in result
        assert result[PathType.NETWORK.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_path(path_name="a", risk_score=60.0)
        eng.record_path(path_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_path(path_name="a", risk_score=50.0)
        eng.record_path(path_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_path(path_name="a", service="auth", risk_score=90.0)
        eng.record_path(path_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(path_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(path_name="a", analysis_score=20.0)
        eng.add_analysis(path_name="b", analysis_score=20.0)
        eng.add_analysis(path_name="c", analysis_score=80.0)
        eng.add_analysis(path_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_path(path_name="test", risk_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_path(path_name="test")
        eng.add_analysis(path_name="test")
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
        eng.record_path(path_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
