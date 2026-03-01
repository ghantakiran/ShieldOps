"""Tests for shieldops.observability.alert_correlation_opt — AlertCorrelationOptimizer."""

from __future__ import annotations

from shieldops.observability.alert_correlation_opt import (
    AlertCorrelationOptimizer,
    CorrelationOptReport,
    CorrelationRecord,
    CorrelationRule,
    CorrelationStrength,
    CorrelationType,
    OptimizationStatus,
)


def _engine(**kw) -> AlertCorrelationOptimizer:
    return AlertCorrelationOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_temporal(self):
        assert CorrelationType.TEMPORAL == "temporal"

    def test_type_causal(self):
        assert CorrelationType.CAUSAL == "causal"

    def test_type_symptom(self):
        assert CorrelationType.SYMPTOM == "symptom"

    def test_type_topological(self):
        assert CorrelationType.TOPOLOGICAL == "topological"

    def test_type_statistical(self):
        assert CorrelationType.STATISTICAL == "statistical"

    def test_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_strength_tentative(self):
        assert CorrelationStrength.TENTATIVE == "tentative"

    def test_strength_none(self):
        assert CorrelationStrength.NONE == "none"

    def test_status_pending(self):
        assert OptimizationStatus.PENDING == "pending"

    def test_status_optimized(self):
        assert OptimizationStatus.OPTIMIZED == "optimized"

    def test_status_validated(self):
        assert OptimizationStatus.VALIDATED == "validated"

    def test_status_rejected(self):
        assert OptimizationStatus.REJECTED == "rejected"

    def test_status_expired(self):
        assert OptimizationStatus.EXPIRED == "expired"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_correlation_record_defaults(self):
        r = CorrelationRecord()
        assert r.id
        assert r.alert_pair == ""
        assert r.correlation_type == CorrelationType.TEMPORAL
        assert r.correlation_strength == CorrelationStrength.NONE
        assert r.optimization_status == OptimizationStatus.PENDING
        assert r.confidence_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_correlation_rule_defaults(self):
        ru = CorrelationRule()
        assert ru.id
        assert ru.alert_pattern == ""
        assert ru.correlation_type == CorrelationType.TEMPORAL
        assert ru.min_confidence == 0.0
        assert ru.auto_merge is False
        assert ru.description == ""
        assert ru.created_at > 0

    def test_correlation_opt_report_defaults(self):
        r = CorrelationOptReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.optimized_count == 0
        assert r.avg_confidence == 0.0
        assert r.by_type == {}
        assert r.by_strength == {}
        assert r.by_status == {}
        assert r.weak_correlations == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_correlation
# ---------------------------------------------------------------------------


class TestRecordCorrelation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_correlation(
            alert_pair="cpu-high:mem-high",
            correlation_type=CorrelationType.CAUSAL,
            correlation_strength=CorrelationStrength.STRONG,
            optimization_status=OptimizationStatus.OPTIMIZED,
            confidence_score=92.5,
            team="sre",
        )
        assert r.alert_pair == "cpu-high:mem-high"
        assert r.correlation_type == CorrelationType.CAUSAL
        assert r.correlation_strength == CorrelationStrength.STRONG
        assert r.optimization_status == OptimizationStatus.OPTIMIZED
        assert r.confidence_score == 92.5
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_correlation(alert_pair=f"pair-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_correlation
# ---------------------------------------------------------------------------


class TestGetCorrelation:
    def test_found(self):
        eng = _engine()
        r = eng.record_correlation(
            alert_pair="cpu-high:mem-high",
            correlation_strength=CorrelationStrength.STRONG,
        )
        result = eng.get_correlation(r.id)
        assert result is not None
        assert result.correlation_strength == CorrelationStrength.STRONG

    def test_not_found(self):
        eng = _engine()
        assert eng.get_correlation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_correlations
# ---------------------------------------------------------------------------


class TestListCorrelations:
    def test_list_all(self):
        eng = _engine()
        eng.record_correlation(alert_pair="pair-a")
        eng.record_correlation(alert_pair="pair-b")
        assert len(eng.list_correlations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_correlation(
            alert_pair="pair-a",
            correlation_type=CorrelationType.CAUSAL,
        )
        eng.record_correlation(
            alert_pair="pair-b",
            correlation_type=CorrelationType.TEMPORAL,
        )
        results = eng.list_correlations(correlation_type=CorrelationType.CAUSAL)
        assert len(results) == 1

    def test_filter_by_strength(self):
        eng = _engine()
        eng.record_correlation(
            alert_pair="pair-a",
            correlation_strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            alert_pair="pair-b",
            correlation_strength=CorrelationStrength.WEAK,
        )
        results = eng.list_correlations(strength=CorrelationStrength.STRONG)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_correlation(alert_pair="pair-a", team="sre")
        eng.record_correlation(alert_pair="pair-b", team="platform")
        results = eng.list_correlations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_correlation(alert_pair=f"pair-{i}")
        assert len(eng.list_correlations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            alert_pattern="cpu-*:mem-*",
            correlation_type=CorrelationType.CAUSAL,
            min_confidence=80.0,
            auto_merge=True,
            description="Auto-merge cpu-mem correlations",
        )
        assert ru.alert_pattern == "cpu-*:mem-*"
        assert ru.correlation_type == CorrelationType.CAUSAL
        assert ru.min_confidence == 80.0
        assert ru.auto_merge is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(alert_pattern=f"pat-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_correlation_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeCorrelationPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation(
            alert_pair="pair-a",
            correlation_type=CorrelationType.CAUSAL,
            confidence_score=80.0,
        )
        eng.record_correlation(
            alert_pair="pair-b",
            correlation_type=CorrelationType.CAUSAL,
            confidence_score=60.0,
        )
        result = eng.analyze_correlation_patterns()
        assert "causal" in result
        assert result["causal"]["count"] == 2
        assert result["causal"]["avg_confidence"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_correlation_patterns() == {}


# ---------------------------------------------------------------------------
# identify_weak_correlations
# ---------------------------------------------------------------------------


class TestIdentifyWeakCorrelations:
    def test_detects_weak(self):
        eng = _engine()
        eng.record_correlation(
            alert_pair="pair-a",
            correlation_strength=CorrelationStrength.WEAK,
        )
        eng.record_correlation(
            alert_pair="pair-b",
            correlation_strength=CorrelationStrength.STRONG,
        )
        results = eng.identify_weak_correlations()
        assert len(results) == 1
        assert results[0]["alert_pair"] == "pair-a"

    def test_detects_tentative(self):
        eng = _engine()
        eng.record_correlation(
            alert_pair="pair-a",
            correlation_strength=CorrelationStrength.TENTATIVE,
        )
        results = eng.identify_weak_correlations()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_weak_correlations() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_correlation(alert_pair="pair-a", team="sre", confidence_score=90.0)
        eng.record_correlation(alert_pair="pair-b", team="sre", confidence_score=80.0)
        eng.record_correlation(alert_pair="pair-c", team="platform", confidence_score=50.0)
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_confidence"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_correlation_trends
# ---------------------------------------------------------------------------


class TestDetectCorrelationTrends:
    def test_stable(self):
        eng = _engine()
        for c in [10.0, 10.0, 10.0, 10.0]:
            eng.add_rule(alert_pattern="p", min_confidence=c)
        result = eng.detect_correlation_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for c in [5.0, 5.0, 20.0, 20.0]:
            eng.add_rule(alert_pattern="p", min_confidence=c)
        result = eng.detect_correlation_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_correlation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            alert_pair="cpu-high:mem-high",
            correlation_type=CorrelationType.CAUSAL,
            correlation_strength=CorrelationStrength.WEAK,
            confidence_score=30.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, CorrelationOptReport)
        assert report.total_records == 1
        assert report.avg_confidence == 30.0
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
        eng.record_correlation(alert_pair="pair-a")
        eng.add_rule(alert_pattern="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            alert_pair="cpu-high:mem-high",
            correlation_type=CorrelationType.CAUSAL,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_alert_pairs"] == 1
        assert "causal" in stats["type_distribution"]
