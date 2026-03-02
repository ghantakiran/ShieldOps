"""Tests for shieldops.analytics.behavioral_risk_aggregator — BehavioralRiskAggregator."""

from __future__ import annotations

from shieldops.analytics.behavioral_risk_aggregator import (
    AggregatedRiskAnalysis,
    AggregatedRiskRecord,
    AggregationMethod,
    BehavioralRiskAggregator,
    BehavioralRiskReport,
    RiskSource,
    RiskTier,
)


def _engine(**kw) -> BehavioralRiskAggregator:
    return BehavioralRiskAggregator(**kw)


class TestEnums:
    def test_source_ueba(self):
        assert RiskSource.UEBA == "ueba"

    def test_source_dlp(self):
        assert RiskSource.DLP == "dlp"

    def test_source_iam(self):
        assert RiskSource.IAM == "iam"

    def test_source_network(self):
        assert RiskSource.NETWORK == "network"

    def test_source_endpoint(self):
        assert RiskSource.ENDPOINT == "endpoint"

    def test_method_weighted_average(self):
        assert AggregationMethod.WEIGHTED_AVERAGE == "weighted_average"

    def test_method_maximum(self):
        assert AggregationMethod.MAXIMUM == "maximum"

    def test_method_bayesian(self):
        assert AggregationMethod.BAYESIAN == "bayesian"

    def test_method_ensemble(self):
        assert AggregationMethod.ENSEMBLE == "ensemble"

    def test_method_custom(self):
        assert AggregationMethod.CUSTOM == "custom"

    def test_tier_low(self):
        assert RiskTier.LOW == "low"

    def test_tier_normal(self):
        assert RiskTier.NORMAL == "normal"

    def test_tier_elevated(self):
        assert RiskTier.ELEVATED == "elevated"

    def test_tier_high(self):
        assert RiskTier.HIGH == "high"

    def test_tier_critical(self):
        assert RiskTier.CRITICAL == "critical"


class TestModels:
    def test_record_defaults(self):
        r = AggregatedRiskRecord()
        assert r.id
        assert r.entity_name == ""
        assert r.risk_source == RiskSource.UEBA
        assert r.aggregation_method == AggregationMethod.WEIGHTED_AVERAGE
        assert r.risk_tier == RiskTier.NORMAL
        assert r.aggregated_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AggregatedRiskAnalysis()
        assert a.id
        assert a.entity_name == ""
        assert a.risk_source == RiskSource.UEBA
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = BehavioralRiskReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_aggregated_score == 0.0
        assert r.by_risk_source == {}
        assert r.by_aggregation_method == {}
        assert r.by_risk_tier == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_risk(
            entity_name="agg-risk-001",
            risk_source=RiskSource.DLP,
            aggregation_method=AggregationMethod.BAYESIAN,
            risk_tier=RiskTier.HIGH,
            aggregated_score=85.0,
            service="risk-engine",
            team="security",
        )
        assert r.entity_name == "agg-risk-001"
        assert r.risk_source == RiskSource.DLP
        assert r.aggregated_score == 85.0
        assert r.service == "risk-engine"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_risk(entity_name=f"risk-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_risk(entity_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_risk(entity_name="a")
        eng.record_risk(entity_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_risk_source(self):
        eng = _engine()
        eng.record_risk(entity_name="a", risk_source=RiskSource.UEBA)
        eng.record_risk(entity_name="b", risk_source=RiskSource.DLP)
        assert len(eng.list_records(risk_source=RiskSource.UEBA)) == 1

    def test_filter_by_aggregation_method(self):
        eng = _engine()
        eng.record_risk(entity_name="a", aggregation_method=AggregationMethod.WEIGHTED_AVERAGE)
        eng.record_risk(entity_name="b", aggregation_method=AggregationMethod.MAXIMUM)
        assert len(eng.list_records(aggregation_method=AggregationMethod.WEIGHTED_AVERAGE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_risk(entity_name="a", team="sec")
        eng.record_risk(entity_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_risk(entity_name=f"r-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            entity_name="test",
            analysis_score=88.5,
            breached=True,
            description="aggregated risk",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(entity_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk(entity_name="a", risk_source=RiskSource.UEBA, aggregated_score=90.0)
        eng.record_risk(entity_name="b", risk_source=RiskSource.UEBA, aggregated_score=70.0)
        result = eng.analyze_distribution()
        assert "ueba" in result
        assert result["ueba"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_risk(entity_name="a", aggregated_score=60.0)
        eng.record_risk(entity_name="b", aggregated_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_risk(entity_name="a", aggregated_score=50.0)
        eng.record_risk(entity_name="b", aggregated_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["aggregated_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_risk(entity_name="a", service="auth", aggregated_score=90.0)
        eng.record_risk(entity_name="b", service="api", aggregated_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(entity_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(entity_name="a", analysis_score=20.0)
        eng.add_analysis(entity_name="b", analysis_score=20.0)
        eng.add_analysis(entity_name="c", analysis_score=80.0)
        eng.add_analysis(entity_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_risk(entity_name="test", aggregated_score=50.0)
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
        eng.record_risk(entity_name="test")
        eng.add_analysis(entity_name="test")
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
        eng.record_risk(entity_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
