"""Tests for EventProcessingLatencyProfiler."""

from __future__ import annotations

from shieldops.analytics.event_processing_latency_profiler import (
    EventProcessingLatencyProfiler,
    LatencyProfile,
    OutlierType,
    ProcessingStage,
)


def _engine(**kw) -> EventProcessingLatencyProfiler:
    return EventProcessingLatencyProfiler(**kw)


class TestEnums:
    def test_processing_stage_values(self):
        for v in ProcessingStage:
            assert isinstance(v.value, str)

    def test_latency_profile_values(self):
        for v in LatencyProfile:
            assert isinstance(v.value, str)

    def test_outlier_type_values(self):
        for v in OutlierType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(pipeline_id="p1")
        assert r.pipeline_id == "p1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(pipeline_id=f"p-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.processing_stage == (ProcessingStage.PROCESSING)


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            pipeline_id="p1",
            latency_ms=50.0,
            p99_latency_ms=200.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "pipeline_id")
        assert a.pipeline_id == "p1"
        assert a.outlier_detected is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_no_outlier(self):
        eng = _engine()
        r = eng.add_record(
            pipeline_id="p1",
            latency_ms=50.0,
            p99_latency_ms=100.0,
        )
        a = eng.process(r.id)
        assert a.outlier_detected is False


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(pipeline_id="p1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_high_latency_pipelines(self):
        eng = _engine()
        eng.add_record(
            pipeline_id="p1",
            latency_profile=LatencyProfile.DELAYED,
        )
        rpt = eng.generate_report()
        assert len(rpt.high_latency_pipelines) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(pipeline_id="p1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(pipeline_id="p1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestProfileEndToEndLatency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            pipeline_id="p1",
            latency_ms=50.0,
            p99_latency_ms=200.0,
        )
        result = eng.profile_end_to_end_latency()
        assert len(result) == 1
        assert result[0]["avg_latency_ms"] == 50.0

    def test_empty(self):
        r = _engine().profile_end_to_end_latency()
        assert r == []


class TestDetectLatencyOutliers:
    def test_with_outlier(self):
        eng = _engine()
        eng.add_record(
            pipeline_id="p1",
            latency_ms=10.0,
            p99_latency_ms=100.0,
        )
        result = eng.detect_latency_outliers()
        assert len(result) == 1

    def test_no_outlier(self):
        eng = _engine()
        eng.add_record(
            pipeline_id="p1",
            latency_ms=50.0,
            p99_latency_ms=100.0,
        )
        assert eng.detect_latency_outliers() == []


class TestRankPipelinesByLatencyRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            pipeline_id="p1",
            latency_ms=100.0,
            p99_latency_ms=500.0,
        )
        eng.add_record(
            pipeline_id="p2",
            latency_ms=10.0,
            p99_latency_ms=20.0,
        )
        result = eng.rank_pipelines_by_latency_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_pipelines_by_latency_risk()
        assert r == []
