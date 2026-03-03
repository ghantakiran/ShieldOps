"""Tests for shieldops.observability.otel_pipeline_optimizer — OtelPipelineOptimizer."""

from __future__ import annotations

from shieldops.observability.otel_pipeline_optimizer import (
    OptimizationTarget,
    OtelPipelineOptimizer,
    OtelPipelineReport,
    PipelineAnalysis,
    PipelineComponent,
    PipelineHealth,
    PipelineRecord,
)


def _engine(**kw) -> OtelPipelineOptimizer:
    return OtelPipelineOptimizer(**kw)


class TestEnums:
    def test_pipeline_component_collector(self):
        assert PipelineComponent.COLLECTOR == "collector"

    def test_pipeline_component_processor(self):
        assert PipelineComponent.PROCESSOR == "processor"

    def test_pipeline_component_exporter(self):
        assert PipelineComponent.EXPORTER == "exporter"

    def test_pipeline_component_receiver(self):
        assert PipelineComponent.RECEIVER == "receiver"

    def test_pipeline_component_connector(self):
        assert PipelineComponent.CONNECTOR == "connector"

    def test_optimization_target_throughput(self):
        assert OptimizationTarget.THROUGHPUT == "throughput"

    def test_optimization_target_latency(self):
        assert OptimizationTarget.LATENCY == "latency"

    def test_optimization_target_resource_usage(self):
        assert OptimizationTarget.RESOURCE_USAGE == "resource_usage"

    def test_optimization_target_data_quality(self):
        assert OptimizationTarget.DATA_QUALITY == "data_quality"

    def test_optimization_target_cost(self):
        assert OptimizationTarget.COST == "cost"

    def test_pipeline_health_optimal(self):
        assert PipelineHealth.OPTIMAL == "optimal"

    def test_pipeline_health_acceptable(self):
        assert PipelineHealth.ACCEPTABLE == "acceptable"

    def test_pipeline_health_degraded(self):
        assert PipelineHealth.DEGRADED == "degraded"

    def test_pipeline_health_critical(self):
        assert PipelineHealth.CRITICAL == "critical"

    def test_pipeline_health_unknown(self):
        assert PipelineHealth.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = PipelineRecord()
        assert r.id
        assert r.name == ""
        assert r.pipeline_component == PipelineComponent.COLLECTOR
        assert r.optimization_target == OptimizationTarget.THROUGHPUT
        assert r.pipeline_health == PipelineHealth.UNKNOWN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PipelineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.pipeline_component == PipelineComponent.COLLECTOR
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = OtelPipelineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_pipeline_component == {}
        assert r.by_optimization_target == {}
        assert r.by_pipeline_health == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            pipeline_component=PipelineComponent.COLLECTOR,
            optimization_target=OptimizationTarget.LATENCY,
            pipeline_health=PipelineHealth.OPTIMAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.pipeline_component == PipelineComponent.COLLECTOR
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_pipeline_component(self):
        eng = _engine()
        eng.record_entry(name="a", pipeline_component=PipelineComponent.COLLECTOR)
        eng.record_entry(name="b", pipeline_component=PipelineComponent.PROCESSOR)
        assert len(eng.list_records(pipeline_component=PipelineComponent.COLLECTOR)) == 1

    def test_filter_by_optimization_target(self):
        eng = _engine()
        eng.record_entry(name="a", optimization_target=OptimizationTarget.THROUGHPUT)
        eng.record_entry(name="b", optimization_target=OptimizationTarget.LATENCY)
        assert len(eng.list_records(optimization_target=OptimizationTarget.THROUGHPUT)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
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
        eng.record_entry(name="a", pipeline_component=PipelineComponent.PROCESSOR, score=90.0)
        eng.record_entry(name="b", pipeline_component=PipelineComponent.PROCESSOR, score=70.0)
        result = eng.analyze_distribution()
        assert "processor" in result
        assert result["processor"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
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
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
