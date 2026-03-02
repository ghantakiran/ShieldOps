"""Tests for shieldops.billing.model_inference_cost_tracker."""

from __future__ import annotations

from shieldops.billing.model_inference_cost_tracker import (
    CostAnalysis,
    CostCategory,
    InferenceCostRecord,
    InferenceCostReport,
    InferenceType,
    ModelInferenceCostTracker,
    OptimizationStatus,
)


def _engine(**kw) -> ModelInferenceCostTracker:
    return ModelInferenceCostTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_inference_batch(self):
        assert InferenceType.BATCH == "batch"

    def test_inference_realtime(self):
        assert InferenceType.REALTIME == "realtime"

    def test_inference_streaming(self):
        assert InferenceType.STREAMING == "streaming"

    def test_inference_edge(self):
        assert InferenceType.EDGE == "edge"

    def test_inference_serverless(self):
        assert InferenceType.SERVERLESS == "serverless"

    def test_cost_compute(self):
        assert CostCategory.COMPUTE == "compute"

    def test_cost_memory(self):
        assert CostCategory.MEMORY == "memory"

    def test_cost_network(self):
        assert CostCategory.NETWORK == "network"

    def test_cost_storage(self):
        assert CostCategory.STORAGE == "storage"

    def test_cost_api_calls(self):
        assert CostCategory.API_CALLS == "api_calls"

    def test_optimization_optimized(self):
        assert OptimizationStatus.OPTIMIZED == "optimized"

    def test_optimization_needs(self):
        assert OptimizationStatus.NEEDS_OPTIMIZATION == "needs_optimization"

    def test_optimization_in_progress(self):
        assert OptimizationStatus.IN_PROGRESS == "in_progress"

    def test_optimization_reviewed(self):
        assert OptimizationStatus.REVIEWED == "reviewed"

    def test_optimization_skipped(self):
        assert OptimizationStatus.SKIPPED == "skipped"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_inference_cost_record_defaults(self):
        r = InferenceCostRecord()
        assert r.id
        assert r.model_id == ""
        assert r.inference_type == InferenceType.REALTIME
        assert r.cost_category == CostCategory.COMPUTE
        assert r.optimization_status == OptimizationStatus.NEEDS_OPTIMIZATION
        assert r.cost_usd == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_cost_analysis_defaults(self):
        a = CostAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.inference_type == InferenceType.REALTIME
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_inference_cost_report_defaults(self):
        r = InferenceCostReport()
        assert r.id
        assert r.total_records == 0
        assert r.overspend_count == 0
        assert r.avg_cost_usd == 0.0
        assert r.by_type == {}
        assert r.by_category == {}
        assert r.by_status == {}
        assert r.top_costly == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_init(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._cost_threshold_usd == 100.0

    def test_custom_init(self):
        eng = _engine(max_records=100, cost_threshold_usd=50.0)
        assert eng._max_records == 100
        assert eng._cost_threshold_usd == 50.0

    def test_empty_stats(self):
        eng = _engine()
        assert eng.get_stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# record_cost / get_cost
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_cost(
            model_id="model-001",
            inference_type=InferenceType.BATCH,
            cost_category=CostCategory.COMPUTE,
            optimization_status=OptimizationStatus.NEEDS_OPTIMIZATION,
            cost_usd=150.0,
            service="ml-svc",
            team="finops-team",
        )
        assert r.model_id == "model-001"
        assert r.inference_type == InferenceType.BATCH
        assert r.cost_usd == 150.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_cost(model_id="m-001", cost_usd=200.0)
        assert eng.get_cost(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_cost("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_cost(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_costs
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_cost(model_id="m-001")
        eng.record_cost(model_id="m-002")
        assert len(eng.list_costs()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_cost(model_id="m-001", inference_type=InferenceType.BATCH)
        eng.record_cost(model_id="m-002", inference_type=InferenceType.EDGE)
        assert len(eng.list_costs(inference_type=InferenceType.BATCH)) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_cost(model_id="m-001", optimization_status=OptimizationStatus.OPTIMIZED)
        eng.record_cost(model_id="m-002", optimization_status=OptimizationStatus.SKIPPED)
        assert len(eng.list_costs(optimization_status=OptimizationStatus.OPTIMIZED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_cost(model_id="m-001", team="finops-team")
        eng.record_cost(model_id="m-002", team="ml-team")
        assert len(eng.list_costs(team="finops-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_cost(model_id=f"m-{i}")
        assert len(eng.list_costs(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            inference_type=InferenceType.REALTIME,
            analysis_score=200.0,
            threshold=100.0,
            breached=True,
            description="overspend detected",
        )
        assert a.model_id == "m-001"
        assert a.analysis_score == 200.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(model_id=f"m-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(model_id="m-test")
        assert a.inference_type == InferenceType.REALTIME
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_cost(model_id="m-001", inference_type=InferenceType.BATCH, cost_usd=100.0)
        eng.record_cost(model_id="m-002", inference_type=InferenceType.BATCH, cost_usd=200.0)
        result = eng.analyze_distribution()
        assert "batch" in result
        assert result["batch"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(cost_threshold_usd=100.0)
        eng.record_cost(model_id="m-001", cost_usd=250.0)
        eng.record_cost(model_id="m-002", cost_usd=50.0)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_descending(self):
        eng = _engine(cost_threshold_usd=50.0)
        eng.record_cost(model_id="m-001", cost_usd=150.0)
        eng.record_cost(model_id="m-002", cost_usd=300.0)
        results = eng.identify_severe_drifts()
        assert results[0]["cost_usd"] == 300.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_cost(model_id="m-001", cost_usd=50.0)
        eng.record_cost(model_id="m-002", cost_usd=500.0)
        results = eng.rank_by_severity()
        assert results[0]["model_id"] == "m-002"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(model_id="m-001", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        eng.add_analysis(model_id="m-001", analysis_score=20.0)
        eng.add_analysis(model_id="m-002", analysis_score=20.0)
        eng.add_analysis(model_id="m-003", analysis_score=80.0)
        eng.add_analysis(model_id="m-004", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "increasing"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(cost_threshold_usd=100.0)
        eng.record_cost(
            model_id="m-001",
            inference_type=InferenceType.REALTIME,
            cost_category=CostCategory.COMPUTE,
            optimization_status=OptimizationStatus.NEEDS_OPTIMIZATION,
            cost_usd=250.0,
        )
        report = eng.generate_report()
        assert isinstance(report, InferenceCostReport)
        assert report.total_records == 1
        assert report.overspend_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_cost(model_id="m-001")
        eng.add_analysis(model_id="m-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_cost(model_id="m-001", inference_type=InferenceType.REALTIME, team="finops-team")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_cost(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"
