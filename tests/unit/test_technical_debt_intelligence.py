"""Tests for shieldops.operations.technical_debt_intelligence — TechnicalDebtIntelligence."""

from __future__ import annotations

from shieldops.operations.technical_debt_intelligence import (
    DebtSeverity,
    DebtTrend,
    DebtType,
    TechnicalDebtIntelligence,
    TechnicalDebtIntelligenceAnalysis,
    TechnicalDebtIntelligenceRecord,
    TechnicalDebtIntelligenceReport,
)


def _engine(**kw) -> TechnicalDebtIntelligence:
    return TechnicalDebtIntelligence(**kw)


class TestEnums:
    def test_debt_type_first(self):
        assert DebtType.CODE == "code"

    def test_debt_type_second(self):
        assert DebtType.ARCHITECTURE == "architecture"

    def test_debt_type_third(self):
        assert DebtType.INFRASTRUCTURE == "infrastructure"

    def test_debt_type_fourth(self):
        assert DebtType.TESTING == "testing"

    def test_debt_type_fifth(self):
        assert DebtType.DOCUMENTATION == "documentation"

    def test_debt_severity_first(self):
        assert DebtSeverity.CRITICAL == "critical"

    def test_debt_severity_second(self):
        assert DebtSeverity.HIGH == "high"

    def test_debt_severity_third(self):
        assert DebtSeverity.MEDIUM == "medium"

    def test_debt_severity_fourth(self):
        assert DebtSeverity.LOW == "low"

    def test_debt_severity_fifth(self):
        assert DebtSeverity.ACCEPTABLE == "acceptable"

    def test_debt_trend_first(self):
        assert DebtTrend.INCREASING == "increasing"

    def test_debt_trend_second(self):
        assert DebtTrend.STABLE == "stable"

    def test_debt_trend_third(self):
        assert DebtTrend.DECREASING == "decreasing"

    def test_debt_trend_fourth(self):
        assert DebtTrend.VOLATILE == "volatile"

    def test_debt_trend_fifth(self):
        assert DebtTrend.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = TechnicalDebtIntelligenceRecord()
        assert r.id
        assert r.name == ""
        assert r.debt_type == DebtType.CODE
        assert r.debt_severity == DebtSeverity.CRITICAL
        assert r.debt_trend == DebtTrend.INCREASING
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = TechnicalDebtIntelligenceAnalysis()
        assert a.id
        assert a.name == ""
        assert a.debt_type == DebtType.CODE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = TechnicalDebtIntelligenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_debt_type == {}
        assert r.by_debt_severity == {}
        assert r.by_debt_trend == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            debt_type=DebtType.CODE,
            debt_severity=DebtSeverity.HIGH,
            debt_trend=DebtTrend.DECREASING,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.debt_type == DebtType.CODE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_debt_type(self):
        eng = _engine()
        eng.record_item(name="a", debt_type=DebtType.ARCHITECTURE)
        eng.record_item(name="b", debt_type=DebtType.CODE)
        assert len(eng.list_records(debt_type=DebtType.ARCHITECTURE)) == 1

    def test_filter_by_debt_severity(self):
        eng = _engine()
        eng.record_item(name="a", debt_severity=DebtSeverity.CRITICAL)
        eng.record_item(name="b", debt_severity=DebtSeverity.HIGH)
        assert len(eng.list_records(debt_severity=DebtSeverity.CRITICAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
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
        eng.record_item(name="a", debt_type=DebtType.ARCHITECTURE, score=90.0)
        eng.record_item(name="b", debt_type=DebtType.ARCHITECTURE, score=70.0)
        result = eng.analyze_distribution()
        assert "architecture" in result
        assert result["architecture"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
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
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
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
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
