"""Tests for shieldops.changes.impact_predictor — DeploymentImpactPredictor."""

from __future__ import annotations

from shieldops.changes.impact_predictor import (
    DeploymentImpactPredictor,
    ImpactCategory,
    ImpactDetail,
    ImpactPredictionRecord,
    ImpactPredictorReport,
    ImpactScope,
    PredictionBasis,
)


def _engine(**kw) -> DeploymentImpactPredictor:
    return DeploymentImpactPredictor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ImpactScope (5)
    def test_scope_global(self):
        assert ImpactScope.GLOBAL == "global"

    def test_scope_regional(self):
        assert ImpactScope.REGIONAL == "regional"

    def test_scope_service_level(self):
        assert ImpactScope.SERVICE_LEVEL == "service_level"

    def test_scope_component(self):
        assert ImpactScope.COMPONENT == "component"

    def test_scope_minimal(self):
        assert ImpactScope.MINIMAL == "minimal"

    # ImpactCategory (5)
    def test_category_performance(self):
        assert ImpactCategory.PERFORMANCE == "performance"

    def test_category_availability(self):
        assert ImpactCategory.AVAILABILITY == "availability"

    def test_category_security(self):
        assert ImpactCategory.SECURITY == "security"

    def test_category_data_integrity(self):
        assert ImpactCategory.DATA_INTEGRITY == "data_integrity"

    def test_category_user_experience(self):
        assert ImpactCategory.USER_EXPERIENCE == "user_experience"

    # PredictionBasis (5)
    def test_basis_historical_data(self):
        assert PredictionBasis.HISTORICAL_DATA == "historical_data"

    def test_basis_dependency_analysis(self):
        assert PredictionBasis.DEPENDENCY_ANALYSIS == "dependency_analysis"

    def test_basis_code_analysis(self):
        assert PredictionBasis.CODE_ANALYSIS == "code_analysis"

    def test_basis_ml_model(self):
        assert PredictionBasis.ML_MODEL == "ml_model"

    def test_basis_expert_judgment(self):
        assert PredictionBasis.EXPERT_JUDGMENT == "expert_judgment"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_impact_prediction_record_defaults(self):
        r = ImpactPredictionRecord()
        assert r.id
        assert r.deployment_name == ""
        assert r.scope == ImpactScope.MINIMAL
        assert r.category == ImpactCategory.PERFORMANCE
        assert r.basis == PredictionBasis.HISTORICAL_DATA
        assert r.impact_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_impact_detail_defaults(self):
        r = ImpactDetail()
        assert r.id
        assert r.detail_name == ""
        assert r.scope == ImpactScope.MINIMAL
        assert r.category == ImpactCategory.PERFORMANCE
        assert r.impact_score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_impact_predictor_report_defaults(self):
        r = ImpactPredictorReport()
        assert r.total_predictions == 0
        assert r.total_details == 0
        assert r.avg_impact_score_pct == 0.0
        assert r.by_scope == {}
        assert r.by_category == {}
        assert r.high_impact_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_prediction
# -------------------------------------------------------------------


class TestRecordPrediction:
    def test_basic(self):
        eng = _engine()
        r = eng.record_prediction(
            "deploy-v2.1.0",
            scope=ImpactScope.REGIONAL,
            category=ImpactCategory.AVAILABILITY,
            basis=PredictionBasis.ML_MODEL,
            impact_score=65.0,
            details="ML predicted regional outage risk",
        )
        assert r.deployment_name == "deploy-v2.1.0"
        assert r.impact_score == 65.0
        assert r.id

    def test_stored(self):
        eng = _engine()
        eng.record_prediction("deploy-v2.1.0")
        assert len(eng._records) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_prediction(f"deploy-v{i}")
        assert len(eng._records) == 2

    def test_multiple_deployments(self):
        eng = _engine()
        eng.record_prediction("deploy-v1")
        eng.record_prediction("deploy-v2")
        assert len(eng._records) == 2


# -------------------------------------------------------------------
# get_prediction
# -------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction("deploy-v2.1.0")
        result = eng.get_prediction(r.id)
        assert result is not None
        assert result.id == r.id

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# -------------------------------------------------------------------
# list_predictions
# -------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction("deploy-v1")
        eng.record_prediction("deploy-v2")
        assert len(eng.list_predictions()) == 2

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_prediction("deploy-v1", scope=ImpactScope.GLOBAL)
        eng.record_prediction("deploy-v2", scope=ImpactScope.MINIMAL)
        results = eng.list_predictions(scope=ImpactScope.GLOBAL)
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_prediction("deploy-v1", category=ImpactCategory.SECURITY)
        eng.record_prediction("deploy-v2", category=ImpactCategory.PERFORMANCE)
        results = eng.list_predictions(category=ImpactCategory.SECURITY)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_detail
# -------------------------------------------------------------------


class TestAddDetail:
    def test_basic(self):
        eng = _engine()
        d = eng.add_detail(
            "db-migration-risk",
            scope=ImpactScope.SERVICE_LEVEL,
            category=ImpactCategory.DATA_INTEGRITY,
            impact_score=70.0,
            description="Schema migration may cause brief downtime",
        )
        assert d.detail_name == "db-migration-risk"
        assert d.impact_score == 70.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_detail(f"detail-{i}")
        assert len(eng._details) == 2


# -------------------------------------------------------------------
# analyze_prediction_accuracy
# -------------------------------------------------------------------


class TestAnalyzePredictionAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction("deploy-v2.1.0", impact_score=80.0, scope=ImpactScope.GLOBAL)
        eng.record_prediction("deploy-v2.1.0", impact_score=60.0, scope=ImpactScope.MINIMAL)
        result = eng.analyze_prediction_accuracy("deploy-v2.1.0")
        assert result["deployment_name"] == "deploy-v2.1.0"
        assert result["total_records"] == 2
        assert result["avg_impact_score"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_prediction_accuracy("ghost-deploy")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_high_impact_deploys
# -------------------------------------------------------------------


class TestIdentifyHighImpactDeploys:
    def test_with_high_impact(self):
        eng = _engine()
        eng.record_prediction("deploy-v2.1.0", scope=ImpactScope.GLOBAL)
        eng.record_prediction("deploy-v2.1.0", scope=ImpactScope.REGIONAL)
        eng.record_prediction("deploy-v1.0.0", scope=ImpactScope.MINIMAL)
        results = eng.identify_high_impact_deploys()
        assert len(results) == 1
        assert results[0]["deployment_name"] == "deploy-v2.1.0"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_deploys() == []


# -------------------------------------------------------------------
# rank_by_impact_score
# -------------------------------------------------------------------


class TestRankByImpactScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction("deploy-v2.1.0", impact_score=90.0)
        eng.record_prediction("deploy-v2.1.0", impact_score=80.0)
        eng.record_prediction("deploy-v1.0.0", impact_score=20.0)
        results = eng.rank_by_impact_score()
        assert results[0]["deployment_name"] == "deploy-v2.1.0"
        assert results[0]["avg_impact_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# -------------------------------------------------------------------
# detect_impact_patterns
# -------------------------------------------------------------------


class TestDetectImpactPatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_prediction("deploy-v2.1.0")
        eng.record_prediction("deploy-v1.0.0")
        results = eng.detect_impact_patterns()
        assert len(results) == 1
        assert results[0]["deployment_name"] == "deploy-v2.1.0"
        assert results[0]["pattern_detected"] is True

    def test_no_patterns(self):
        eng = _engine()
        eng.record_prediction("deploy-v2.1.0")
        assert eng.detect_impact_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_prediction("deploy-v2.1.0", scope=ImpactScope.GLOBAL, impact_score=90.0)
        eng.record_prediction("deploy-v1.0.0", scope=ImpactScope.MINIMAL, impact_score=10.0)
        eng.add_detail("detail-1")
        report = eng.generate_report()
        assert report.total_predictions == 2
        assert report.total_details == 1
        assert report.by_scope != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_predictions == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction("deploy-v2.1.0")
        eng.add_detail("detail-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._details) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_predictions"] == 0
        assert stats["total_details"] == 0
        assert stats["scope_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_prediction("deploy-v1", scope=ImpactScope.GLOBAL)
        eng.record_prediction("deploy-v2", scope=ImpactScope.MINIMAL)
        eng.add_detail("detail-1")
        stats = eng.get_stats()
        assert stats["total_predictions"] == 2
        assert stats["total_details"] == 1
        assert stats["unique_deployments"] == 2
