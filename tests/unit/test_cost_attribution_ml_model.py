"""Tests for shieldops.billing.cost_attribution_ml_model."""

from __future__ import annotations

from shieldops.billing.cost_attribution_ml_model import (
    AttributionAnalysis,
    AttributionMethod,
    AttributionRecord,
    CostAttributionMLModel,
    CostAttributionMLReport,
    CostDimension,
    ModelAccuracy,
)


def _engine(**kw) -> CostAttributionMLModel:
    return CostAttributionMLModel(**kw)


class TestEnums:
    def test_attributionmethod_rule_based(self):
        assert AttributionMethod.RULE_BASED == "rule_based"

    def test_attributionmethod_ml_classification(self):
        assert AttributionMethod.ML_CLASSIFICATION == "ml_classification"

    def test_attributionmethod_proportional(self):
        assert AttributionMethod.PROPORTIONAL == "proportional"

    def test_attributionmethod_tag_based(self):
        assert AttributionMethod.TAG_BASED == "tag_based"

    def test_attributionmethod_hybrid(self):
        assert AttributionMethod.HYBRID == "hybrid"

    def test_costdimension_service(self):
        assert CostDimension.SERVICE == "service"

    def test_costdimension_team(self):
        assert CostDimension.TEAM == "team"

    def test_costdimension_project(self):
        assert CostDimension.PROJECT == "project"

    def test_costdimension_environment(self):
        assert CostDimension.ENVIRONMENT == "environment"

    def test_costdimension_customer(self):
        assert CostDimension.CUSTOMER == "customer"

    def test_modelaccuracy_high(self):
        assert ModelAccuracy.HIGH == "high"

    def test_modelaccuracy_medium(self):
        assert ModelAccuracy.MEDIUM == "medium"

    def test_modelaccuracy_low(self):
        assert ModelAccuracy.LOW == "low"

    def test_modelaccuracy_training(self):
        assert ModelAccuracy.TRAINING == "training"

    def test_modelaccuracy_unvalidated(self):
        assert ModelAccuracy.UNVALIDATED == "unvalidated"


class TestModels:
    def test_attribution_record_defaults(self):
        r = AttributionRecord()
        assert r.id
        assert r.attribution_method == AttributionMethod.HYBRID
        assert r.cost_dimension == CostDimension.TEAM
        assert r.model_accuracy == ModelAccuracy.UNVALIDATED
        assert r.attributed_cost == 0.0
        assert r.accuracy_score == 0.0
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_attribution_analysis_defaults(self):
        a = AttributionAnalysis()
        assert a.id
        assert a.attribution_method == AttributionMethod.HYBRID
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_cost_attribution_ml_report_defaults(self):
        r = CostAttributionMLReport()
        assert r.id
        assert r.total_records == 0
        assert r.high_accuracy_count == 0
        assert r.avg_accuracy_score == 0.0
        assert r.by_attribution_method == {}
        assert r.top_attributions == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordAttribution:
    def test_basic(self):
        eng = _engine()
        r = eng.record_attribution(
            attribution_method=AttributionMethod.ML_CLASSIFICATION,
            cost_dimension=CostDimension.TEAM,
            model_accuracy=ModelAccuracy.HIGH,
            attributed_cost=5000.0,
            accuracy_score=92.0,
            confidence_score=88.0,
            service="billing-svc",
            team="finops",
        )
        assert r.attribution_method == AttributionMethod.ML_CLASSIFICATION
        assert r.accuracy_score == 92.0
        assert r.team == "finops"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_attribution(attribution_method=AttributionMethod.HYBRID)
        assert len(eng._records) == 3


class TestGetAttribution:
    def test_found(self):
        eng = _engine()
        r = eng.record_attribution(accuracy_score=87.0)
        result = eng.get_attribution(r.id)
        assert result is not None
        assert result.accuracy_score == 87.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_attribution("nonexistent") is None


class TestListAttributions:
    def test_list_all(self):
        eng = _engine()
        eng.record_attribution(attribution_method=AttributionMethod.HYBRID)
        eng.record_attribution(attribution_method=AttributionMethod.TAG_BASED)
        assert len(eng.list_attributions()) == 2

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_attribution(attribution_method=AttributionMethod.HYBRID)
        eng.record_attribution(attribution_method=AttributionMethod.RULE_BASED)
        results = eng.list_attributions(attribution_method=AttributionMethod.HYBRID)
        assert len(results) == 1

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_attribution(cost_dimension=CostDimension.TEAM)
        eng.record_attribution(cost_dimension=CostDimension.PROJECT)
        results = eng.list_attributions(cost_dimension=CostDimension.TEAM)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_attribution(team="finops")
        eng.record_attribution(team="platform")
        results = eng.list_attributions(team="finops")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_attribution(attribution_method=AttributionMethod.HYBRID)
        assert len(eng.list_attributions(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            attribution_method=AttributionMethod.ML_CLASSIFICATION,
            analysis_score=94.0,
            threshold=85.0,
            breached=True,
            description="high accuracy model validated",
        )
        assert a.attribution_method == AttributionMethod.ML_CLASSIFICATION
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(attribution_method=AttributionMethod.HYBRID)
        assert len(eng._analyses) == 2


class TestAnalyzeMethodDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_attribution(attribution_method=AttributionMethod.HYBRID, accuracy_score=90.0)
        eng.record_attribution(attribution_method=AttributionMethod.HYBRID, accuracy_score=80.0)
        result = eng.analyze_method_distribution()
        assert "hybrid" in result
        assert result["hybrid"]["count"] == 2
        assert result["hybrid"]["avg_accuracy_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_method_distribution() == {}


class TestIdentifyHighAccuracyAttributions:
    def test_detects_above_threshold(self):
        eng = _engine(accuracy_threshold=80.0)
        eng.record_attribution(accuracy_score=90.0)
        eng.record_attribution(accuracy_score=50.0)
        results = eng.identify_high_accuracy_attributions()
        assert len(results) == 1

    def test_sorted_descending(self):
        eng = _engine(accuracy_threshold=70.0)
        eng.record_attribution(accuracy_score=95.0)
        eng.record_attribution(accuracy_score=80.0)
        results = eng.identify_high_accuracy_attributions()
        assert results[0]["accuracy_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_accuracy_attributions() == []


class TestRankByAttributedCost:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_attribution(team="platform", attributed_cost=50000.0)
        eng.record_attribution(team="data", attributed_cost=10000.0)
        results = eng.rank_by_attributed_cost()
        assert results[0]["team"] == "platform"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_attributed_cost() == []


class TestDetectAccuracyTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_accuracy_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_accuracy_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_accuracy_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(accuracy_threshold=80.0)
        eng.record_attribution(
            attribution_method=AttributionMethod.ML_CLASSIFICATION,
            cost_dimension=CostDimension.TEAM,
            model_accuracy=ModelAccuracy.HIGH,
            accuracy_score=90.0,
            attributed_cost=5000.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CostAttributionMLReport)
        assert report.total_records == 1
        assert report.high_accuracy_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "performing" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_attribution(attribution_method=AttributionMethod.HYBRID)
        eng.add_analysis(attribution_method=AttributionMethod.HYBRID)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["attribution_method_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_attribution(
            attribution_method=AttributionMethod.HYBRID,
            service="billing-svc",
            team="finops",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "hybrid" in stats["attribution_method_distribution"]
