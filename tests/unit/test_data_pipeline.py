"""Tests for shieldops.observability.data_pipeline — DataPipelineReliabilityMonitor."""

from __future__ import annotations

from shieldops.observability.data_pipeline import (
    DataPipelineReliabilityMonitor,
    DataPipelineReport,
    DataQualityIssue,
    DataQualityRecord,
    PipelineHealth,
    PipelineRunRecord,
    PipelineType,
)


def _engine(**kw) -> DataPipelineReliabilityMonitor:
    return DataPipelineReliabilityMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PipelineType (5)
    def test_type_batch(self):
        assert PipelineType.BATCH == "batch"

    def test_type_streaming(self):
        assert PipelineType.STREAMING == "streaming"

    def test_type_micro_batch(self):
        assert PipelineType.MICRO_BATCH == "micro_batch"

    def test_type_cdc(self):
        assert PipelineType.CDC == "cdc"

    def test_type_etl(self):
        assert PipelineType.ETL == "etl"

    # PipelineHealth (5)
    def test_health_healthy(self):
        assert PipelineHealth.HEALTHY == "healthy"

    def test_health_delayed(self):
        assert PipelineHealth.DELAYED == "delayed"

    def test_health_failing(self):
        assert PipelineHealth.FAILING == "failing"

    def test_health_stale(self):
        assert PipelineHealth.STALE == "stale"

    def test_health_unknown(self):
        assert PipelineHealth.UNKNOWN == "unknown"

    # DataQualityIssue (5)
    def test_issue_schema_drift(self):
        assert DataQualityIssue.SCHEMA_DRIFT == "schema_drift"

    def test_issue_missing_data(self):
        assert DataQualityIssue.MISSING_DATA == "missing_data"

    def test_issue_duplicate_records(self):
        assert DataQualityIssue.DUPLICATE_RECORDS == "duplicate_records"

    def test_issue_type_mismatch(self):
        assert DataQualityIssue.TYPE_MISMATCH == "type_mismatch"

    def test_issue_freshness_violation(self):
        assert DataQualityIssue.FRESHNESS_VIOLATION == "freshness_violation"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_pipeline_run_record_defaults(self):
        r = PipelineRunRecord()
        assert r.id
        assert r.pipeline_name == ""
        assert r.pipeline_type == PipelineType.BATCH
        assert r.health == PipelineHealth.HEALTHY
        assert r.records_processed == 0
        assert r.duration_seconds == 0.0
        assert r.freshness_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_data_quality_record_defaults(self):
        r = DataQualityRecord()
        assert r.id
        assert r.pipeline_name == ""
        assert r.issue_type == DataQualityIssue.SCHEMA_DRIFT
        assert r.affected_records == 0
        assert r.severity == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_data_pipeline_report_defaults(self):
        r = DataPipelineReport()
        assert r.total_runs == 0
        assert r.total_quality_issues == 0
        assert r.avg_duration_seconds == 0.0
        assert r.by_type == {}
        assert r.by_health == {}
        assert r.stale_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_run
# -------------------------------------------------------------------


class TestRecordRun:
    def test_basic(self):
        eng = _engine()
        r = eng.record_run("etl-users", records_processed=10000, duration_seconds=120.5)
        assert r.pipeline_name == "etl-users"
        assert r.records_processed == 10000
        assert r.duration_seconds == 120.5
        assert r.pipeline_type == PipelineType.BATCH

    def test_with_type_and_health(self):
        eng = _engine()
        r = eng.record_run(
            "stream-events",
            pipeline_type=PipelineType.STREAMING,
            health=PipelineHealth.DELAYED,
            freshness_seconds=7200.0,
        )
        assert r.pipeline_type == PipelineType.STREAMING
        assert r.health == PipelineHealth.DELAYED
        assert r.freshness_seconds == 7200.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_run(f"pipe-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_run
# -------------------------------------------------------------------


class TestGetRun:
    def test_found(self):
        eng = _engine()
        r = eng.record_run("etl-users")
        assert eng.get_run(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_run("nonexistent") is None


# -------------------------------------------------------------------
# list_runs
# -------------------------------------------------------------------


class TestListRuns:
    def test_list_all(self):
        eng = _engine()
        eng.record_run("pipe-a")
        eng.record_run("pipe-b")
        assert len(eng.list_runs()) == 2

    def test_filter_by_pipeline_name(self):
        eng = _engine()
        eng.record_run("pipe-a")
        eng.record_run("pipe-b")
        results = eng.list_runs(pipeline_name="pipe-a")
        assert len(results) == 1
        assert results[0].pipeline_name == "pipe-a"

    def test_filter_by_health(self):
        eng = _engine()
        eng.record_run("pipe-a", health=PipelineHealth.HEALTHY)
        eng.record_run("pipe-b", health=PipelineHealth.FAILING)
        results = eng.list_runs(health=PipelineHealth.FAILING)
        assert len(results) == 1
        assert results[0].pipeline_name == "pipe-b"


# -------------------------------------------------------------------
# record_quality_issue
# -------------------------------------------------------------------


class TestRecordQualityIssue:
    def test_basic(self):
        eng = _engine()
        q = eng.record_quality_issue("etl-users", affected_records=500, severity=0.8)
        assert q.pipeline_name == "etl-users"
        assert q.affected_records == 500
        assert q.severity == 0.8
        assert q.issue_type == DataQualityIssue.SCHEMA_DRIFT

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_quality_issue(f"pipe-{i}")
        assert len(eng._quality_issues) == 2


# -------------------------------------------------------------------
# analyze_pipeline_health
# -------------------------------------------------------------------


class TestAnalyzePipelineHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_run("pipe-a", duration_seconds=60.0, health=PipelineHealth.HEALTHY)
        eng.record_run("pipe-a", duration_seconds=120.0, health=PipelineHealth.FAILING)
        eng.record_quality_issue("pipe-a")
        result = eng.analyze_pipeline_health("pipe-a")
        assert result["pipeline_name"] == "pipe-a"
        assert result["total_runs"] == 2
        assert result["total_quality_issues"] == 1
        assert result["avg_duration_seconds"] == 90.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_pipeline_health("unknown")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_stale_pipelines
# -------------------------------------------------------------------


class TestIdentifyStalePipelines:
    def test_with_stale(self):
        eng = _engine(freshness_threshold_seconds=3600.0)
        eng.record_run("pipe-a", freshness_seconds=7200.0)
        eng.record_run("pipe-b", freshness_seconds=1800.0)
        results = eng.identify_stale_pipelines()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "pipe-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_stale_pipelines() == []


# -------------------------------------------------------------------
# rank_by_error_rate
# -------------------------------------------------------------------


class TestRankByErrorRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_run("pipe-a", health=PipelineHealth.FAILING)
        eng.record_run("pipe-a", health=PipelineHealth.HEALTHY)
        eng.record_run("pipe-b", health=PipelineHealth.FAILING)
        eng.record_run("pipe-b", health=PipelineHealth.FAILING)
        results = eng.rank_by_error_rate()
        assert len(results) == 2
        # pipe-b: 100% error, pipe-a: 50%
        assert results[0]["pipeline_name"] == "pipe-b"
        assert results[0]["error_rate_pct"] == 100.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_error_rate() == []


# -------------------------------------------------------------------
# detect_schema_drifts
# -------------------------------------------------------------------


class TestDetectSchemaDrifts:
    def test_with_drifts(self):
        eng = _engine()
        eng.record_quality_issue("pipe-a", issue_type=DataQualityIssue.SCHEMA_DRIFT, severity=0.9)
        eng.record_quality_issue("pipe-b", issue_type=DataQualityIssue.MISSING_DATA)
        results = eng.detect_schema_drifts()
        assert len(results) == 1
        assert results[0]["pipeline_name"] == "pipe-a"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_schema_drifts() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(freshness_threshold_seconds=3600.0)
        eng.record_run("pipe-a", duration_seconds=100.0, freshness_seconds=7200.0)
        eng.record_quality_issue("pipe-a", issue_type=DataQualityIssue.SCHEMA_DRIFT)
        report = eng.generate_report()
        assert report.total_runs == 1
        assert report.total_quality_issues == 1
        assert report.stale_count == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_runs == 0
        assert "good" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_run("pipe")
        eng.record_quality_issue("pipe")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._quality_issues) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_runs"] == 0
        assert stats["total_quality_issues"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_run("pipe-a")
        eng.record_run("pipe-b")
        eng.record_quality_issue("pipe-a")
        stats = eng.get_stats()
        assert stats["total_runs"] == 2
        assert stats["total_quality_issues"] == 1
        assert stats["unique_pipelines"] == 2
        assert stats["freshness_threshold_seconds"] == 3600.0
