"""Tests for ProvisioningPipelineOptimizer."""

from __future__ import annotations

from shieldops.operations.provisioning_pipeline_optimizer import (
    OptimizationType,
    PipelineStage,
    ProvisioningPipelineOptimizer,
    StageStatus,
)


def _engine(**kw) -> ProvisioningPipelineOptimizer:
    return ProvisioningPipelineOptimizer(**kw)


class TestEnums:
    def test_pipeline_stage_values(self):
        for v in PipelineStage:
            assert isinstance(v.value, str)

    def test_stage_status_values(self):
        for v in StageStatus:
            assert isinstance(v.value, str)

    def test_optimization_type_values(self):
        for v in OptimizationType:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(pipeline_id="p1")
        assert r.pipeline_id == "p1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(pipeline_id=f"p-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            pipeline_id="p1",
            stage_name="plan",
            duration_seconds=30.0,
            efficiency_score=85.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "pipeline_id")
        assert a.pipeline_id == "p1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(pipeline_id="p1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(pipeline_id="p1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(pipeline_id="p1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputePipelineEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            pipeline_id="p1",
            efficiency_score=90.0,
            duration_seconds=30.0,
        )
        result = eng.compute_pipeline_efficiency()
        assert len(result) == 1
        assert result[0]["avg_efficiency"] == 90.0

    def test_empty(self):
        r = _engine().compute_pipeline_efficiency()
        assert r == []


class TestDetectPipelineBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            pipeline_id="p1",
            stage_name="apply",
            stage_status=StageStatus.SLOW,
            duration_seconds=120.0,
        )
        result = eng.detect_pipeline_bottlenecks()
        assert len(result) == 1
        assert result[0]["status"] == "slow"

    def test_empty(self):
        r = _engine().detect_pipeline_bottlenecks()
        assert r == []


class TestRankStagesByOptimizationPotential:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            pipeline_id="p1",
            stage_name="plan",
            duration_seconds=60.0,
        )
        eng.record_item(
            pipeline_id="p1",
            stage_name="apply",
            duration_seconds=120.0,
        )
        result = eng.rank_stages_by_optimization_potential()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_stages_by_optimization_potential()
        assert r == []
