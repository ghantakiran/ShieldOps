"""Tests for shieldops.analytics.technical_debt_predictor."""

from __future__ import annotations

from shieldops.analytics.technical_debt_predictor import (
    DebtAnalysis,
    DebtCategory,
    DebtRecord,
    DebtReport,
    DebtSeverity,
    PayoffStrategy,
    TechnicalDebtPredictor,
)


def _engine(**kw) -> TechnicalDebtPredictor:
    return TechnicalDebtPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_code_quality(self):
        assert DebtCategory.CODE_QUALITY == "code_quality"

    def test_category_architecture(self):
        assert DebtCategory.ARCHITECTURE == "architecture"

    def test_category_testing(self):
        assert DebtCategory.TESTING == "testing"

    def test_category_documentation(self):
        assert DebtCategory.DOCUMENTATION == "documentation"

    def test_category_dependency(self):
        assert DebtCategory.DEPENDENCY == "dependency"

    def test_severity_critical(self):
        assert DebtSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert DebtSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert DebtSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert DebtSeverity.LOW == "low"

    def test_severity_trivial(self):
        assert DebtSeverity.TRIVIAL == "trivial"

    def test_strategy_immediate(self):
        assert PayoffStrategy.IMMEDIATE == "immediate"

    def test_strategy_incremental(self):
        assert PayoffStrategy.INCREMENTAL == "incremental"

    def test_strategy_planned(self):
        assert PayoffStrategy.PLANNED == "planned"

    def test_strategy_deferred(self):
        assert PayoffStrategy.DEFERRED == "deferred"

    def test_strategy_accepted(self):
        assert PayoffStrategy.ACCEPTED == "accepted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_debt_record_defaults(self):
        r = DebtRecord()
        assert r.id
        assert r.service == ""
        assert r.team == ""
        assert r.debt_category == DebtCategory.CODE_QUALITY
        assert r.debt_severity == DebtSeverity.LOW
        assert r.payoff_strategy == PayoffStrategy.PLANNED
        assert r.debt_score == 0.0
        assert r.estimated_hours == 0.0
        assert r.created_at > 0

    def test_debt_analysis_defaults(self):
        a = DebtAnalysis()
        assert a.id
        assert a.service == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_debt_report_defaults(self):
        r = DebtReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_debt_score == 0.0
        assert r.by_category == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_debt / get_debt
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_debt(
            service="auth-svc",
            team="platform",
            debt_category=DebtCategory.ARCHITECTURE,
            debt_severity=DebtSeverity.CRITICAL,
            payoff_strategy=PayoffStrategy.IMMEDIATE,
            debt_score=90.0,
            estimated_hours=40.0,
        )
        assert r.service == "auth-svc"
        assert r.debt_category == DebtCategory.ARCHITECTURE
        assert r.debt_score == 90.0
        assert r.estimated_hours == 40.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_debt(service="api-gw", debt_score=65.0)
        found = eng.get_debt(r.id)
        assert found is not None
        assert found.debt_score == 65.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_debt("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_debt(service=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_debts
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_debt(service="auth-svc")
        eng.record_debt(service="api-gw")
        assert len(eng.list_debts()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_debt(service="auth-svc", debt_category=DebtCategory.ARCHITECTURE)
        eng.record_debt(service="api-gw", debt_category=DebtCategory.TESTING)
        results = eng.list_debts(debt_category=DebtCategory.ARCHITECTURE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_debt(service="auth-svc", team="platform")
        eng.record_debt(service="api-gw", team="sre")
        results = eng.list_debts(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_debt(service=f"svc-{i}")
        assert len(eng.list_debts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            service="auth-svc",
            debt_category=DebtCategory.CODE_QUALITY,
            analysis_score=75.0,
            threshold=50.0,
            breached=True,
            description="code quality debt",
        )
        assert a.service == "auth-svc"
        assert a.analysis_score == 75.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(service=f"svc-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(service="auth-svc")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_debt(
            service="auth-svc",
            debt_category=DebtCategory.ARCHITECTURE,
            debt_score=80.0,
        )
        eng.record_debt(
            service="api-gw",
            debt_category=DebtCategory.ARCHITECTURE,
            debt_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "architecture" in result
        assert result["architecture"]["count"] == 2
        assert result["architecture"]["avg_debt_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_debt_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_debt(service="auth-svc", debt_score=80.0)
        eng.record_debt(service="api-gw", debt_score=40.0)
        results = eng.identify_debt_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "auth-svc"

    def test_sorted_descending(self):
        eng = _engine(threshold=50.0)
        eng.record_debt(service="auth-svc", debt_score=90.0)
        eng.record_debt(service="api-gw", debt_score=70.0)
        results = eng.identify_debt_gaps()
        assert results[0]["debt_score"] == 90.0


# ---------------------------------------------------------------------------
# rank_by_debt
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_debt(service="auth-svc", debt_score=30.0)
        eng.record_debt(service="api-gw", debt_score=80.0)
        results = eng.rank_by_debt()
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_debt() == []


# ---------------------------------------------------------------------------
# detect_debt_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(service="auth-svc", analysis_score=50.0)
        result = eng.detect_debt_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(service="a", analysis_score=20.0)
        eng.add_analysis(service="b", analysis_score=20.0)
        eng.add_analysis(service="c", analysis_score=80.0)
        eng.add_analysis(service="d", analysis_score=80.0)
        result = eng.detect_debt_trends()
        assert result["trend"] == "worsening"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_debt_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_debt(
            service="auth-svc",
            debt_category=DebtCategory.ARCHITECTURE,
            debt_severity=DebtSeverity.CRITICAL,
            debt_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DebtReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_debt(service="auth-svc")
        eng.add_analysis(service="auth-svc")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_debt(service="auth-svc", team="platform", debt_category=DebtCategory.TESTING)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "testing" in stats["category_distribution"]
        assert stats["unique_services"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(service=f"svc-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
