"""Tests for shieldops.compliance.data_lineage_mapper — DataLineageMapper."""

from __future__ import annotations

from shieldops.compliance.data_lineage_mapper import (
    DataFlow,
    DataLineageMapper,
    LineageAnalysis,
    LineageNode,
    LineageRecord,
    LineageReport,
    TraceStatus,
)


def _engine(**kw) -> DataLineageMapper:
    return DataLineageMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_node_source(self):
        assert LineageNode.SOURCE == "source"

    def test_node_transform(self):
        assert LineageNode.TRANSFORM == "transform"

    def test_node_storage(self):
        assert LineageNode.STORAGE == "storage"

    def test_node_output(self):
        assert LineageNode.OUTPUT == "output"

    def test_node_archive(self):
        assert LineageNode.ARCHIVE == "archive"

    def test_flow_ingestion(self):
        assert DataFlow.INGESTION == "ingestion"

    def test_flow_processing(self):
        assert DataFlow.PROCESSING == "processing"

    def test_flow_sharing(self):
        assert DataFlow.SHARING == "sharing"

    def test_flow_deletion(self):
        assert DataFlow.DELETION == "deletion"

    def test_flow_backup(self):
        assert DataFlow.BACKUP == "backup"

    def test_trace_complete(self):
        assert TraceStatus.COMPLETE == "complete"

    def test_trace_partial(self):
        assert TraceStatus.PARTIAL == "partial"

    def test_trace_broken(self):
        assert TraceStatus.BROKEN == "broken"

    def test_trace_pending(self):
        assert TraceStatus.PENDING == "pending"

    def test_trace_unknown(self):
        assert TraceStatus.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_lineage_record_defaults(self):
        r = LineageRecord()
        assert r.id
        assert r.data_asset == ""
        assert r.lineage_node == LineageNode.SOURCE
        assert r.data_flow == DataFlow.INGESTION
        assert r.trace_status == TraceStatus.COMPLETE
        assert r.completeness_score == 0.0
        assert r.pipeline == ""
        assert r.data_owner == ""
        assert r.created_at > 0

    def test_lineage_analysis_defaults(self):
        a = LineageAnalysis()
        assert a.id
        assert a.data_asset == ""
        assert a.lineage_node == LineageNode.SOURCE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = LineageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_completeness_score == 0.0
        assert r.by_node == {}
        assert r.by_flow == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_lineage / get_lineage
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_lineage(
            data_asset="events-stream",
            lineage_node=LineageNode.TRANSFORM,
            data_flow=DataFlow.PROCESSING,
            trace_status=TraceStatus.COMPLETE,
            completeness_score=92.0,
            pipeline="etl-main",
            data_owner="data-eng",
        )
        assert r.data_asset == "events-stream"
        assert r.lineage_node == LineageNode.TRANSFORM
        assert r.completeness_score == 92.0
        assert r.pipeline == "etl-main"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_lineage(data_asset="asset-001", lineage_node=LineageNode.STORAGE)
        result = eng.get_lineage(r.id)
        assert result is not None
        assert result.lineage_node == LineageNode.STORAGE

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_lineage("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_lineage(data_asset=f"asset-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_lineages
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_lineage(data_asset="a-001")
        eng.record_lineage(data_asset="a-002")
        assert len(eng.list_lineages()) == 2

    def test_filter_by_node(self):
        eng = _engine()
        eng.record_lineage(data_asset="a-001", lineage_node=LineageNode.SOURCE)
        eng.record_lineage(data_asset="a-002", lineage_node=LineageNode.OUTPUT)
        results = eng.list_lineages(lineage_node=LineageNode.SOURCE)
        assert len(results) == 1

    def test_filter_by_flow(self):
        eng = _engine()
        eng.record_lineage(data_asset="a-001", data_flow=DataFlow.INGESTION)
        eng.record_lineage(data_asset="a-002", data_flow=DataFlow.SHARING)
        results = eng.list_lineages(data_flow=DataFlow.INGESTION)
        assert len(results) == 1

    def test_filter_by_owner(self):
        eng = _engine()
        eng.record_lineage(data_asset="a-001", data_owner="team-a")
        eng.record_lineage(data_asset="a-002", data_owner="team-b")
        results = eng.list_lineages(data_owner="team-a")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_lineage(data_asset=f"a-{i}")
        assert len(eng.list_lineages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            data_asset="events-stream",
            lineage_node=LineageNode.TRANSFORM,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="broken trace",
        )
        assert a.data_asset == "events-stream"
        assert a.lineage_node == LineageNode.TRANSFORM
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(data_asset=f"a-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(data_asset="asset-001", lineage_node=LineageNode.ARCHIVE)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_node_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_lineage(
            data_asset="a-001", lineage_node=LineageNode.SOURCE, completeness_score=90.0
        )
        eng.record_lineage(
            data_asset="a-002", lineage_node=LineageNode.SOURCE, completeness_score=70.0
        )
        result = eng.analyze_node_distribution()
        assert "source" in result
        assert result["source"]["count"] == 2
        assert result["source"]["avg_completeness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_node_distribution() == {}


# ---------------------------------------------------------------------------
# identify_lineage_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_lineage(data_asset="a-001", completeness_score=60.0)
        eng.record_lineage(data_asset="a-002", completeness_score=90.0)
        results = eng.identify_lineage_gaps()
        assert len(results) == 1
        assert results[0]["data_asset"] == "a-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_lineage(data_asset="a-001", completeness_score=50.0)
        eng.record_lineage(data_asset="a-002", completeness_score=30.0)
        results = eng.identify_lineage_gaps()
        assert results[0]["completeness_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_completeness
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_lineage(data_asset="a-001", pipeline="pipe-a", completeness_score=90.0)
        eng.record_lineage(data_asset="a-002", pipeline="pipe-b", completeness_score=50.0)
        results = eng.rank_by_completeness()
        assert results[0]["pipeline"] == "pipe-b"
        assert results[0]["avg_completeness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completeness() == []


# ---------------------------------------------------------------------------
# detect_lineage_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(data_asset="a-001", analysis_score=50.0)
        result = eng.detect_lineage_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(data_asset="a-001", analysis_score=20.0)
        eng.add_analysis(data_asset="a-002", analysis_score=20.0)
        eng.add_analysis(data_asset="a-003", analysis_score=80.0)
        eng.add_analysis(data_asset="a-004", analysis_score=80.0)
        result = eng.detect_lineage_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_lineage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_lineage(
            data_asset="events-stream",
            lineage_node=LineageNode.TRANSFORM,
            data_flow=DataFlow.PROCESSING,
            trace_status=TraceStatus.BROKEN,
            completeness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, LineageReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
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
        eng.record_lineage(data_asset="a-001")
        eng.add_analysis(data_asset="a-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["node_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(data_asset=f"a-{i}")
        assert len(eng._analyses) == 3
