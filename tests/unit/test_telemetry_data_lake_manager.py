"""Tests for shieldops.observability.telemetry_data_lake_manager — TelemetryDataLakeManager."""

from __future__ import annotations

from shieldops.observability.telemetry_data_lake_manager import (
    DataLakeFormat,
    DataLakePartition,
    DataLakeTier,
    TelemetryDataLakeManager,
    TelemetryDataLakeManagerAnalysis,
    TelemetryDataLakeManagerRecord,
    TelemetryDataLakeManagerReport,
)


def _engine(**kw) -> TelemetryDataLakeManager:
    return TelemetryDataLakeManager(**kw)


class TestEnums:
    def test_data_lake_partition_first(self):
        assert DataLakePartition.HOURLY == "hourly"

    def test_data_lake_partition_second(self):
        assert DataLakePartition.DAILY == "daily"

    def test_data_lake_partition_third(self):
        assert DataLakePartition.WEEKLY == "weekly"

    def test_data_lake_partition_fourth(self):
        assert DataLakePartition.MONTHLY == "monthly"

    def test_data_lake_partition_fifth(self):
        assert DataLakePartition.YEARLY == "yearly"

    def test_data_lake_format_first(self):
        assert DataLakeFormat.PARQUET == "parquet"

    def test_data_lake_format_second(self):
        assert DataLakeFormat.ORC == "orc"

    def test_data_lake_format_third(self):
        assert DataLakeFormat.AVRO == "avro"

    def test_data_lake_format_fourth(self):
        assert DataLakeFormat.JSON == "json"

    def test_data_lake_format_fifth(self):
        assert DataLakeFormat.CSV == "csv"

    def test_data_lake_tier_first(self):
        assert DataLakeTier.HOT == "hot"

    def test_data_lake_tier_second(self):
        assert DataLakeTier.WARM == "warm"

    def test_data_lake_tier_third(self):
        assert DataLakeTier.COLD == "cold"

    def test_data_lake_tier_fourth(self):
        assert DataLakeTier.ARCHIVE == "archive"

    def test_data_lake_tier_fifth(self):
        assert DataLakeTier.FROZEN == "frozen"


class TestModels:
    def test_record_defaults(self):
        r = TelemetryDataLakeManagerRecord()
        assert r.id
        assert r.name == ""
        assert r.data_lake_partition == DataLakePartition.HOURLY
        assert r.data_lake_format == DataLakeFormat.PARQUET
        assert r.data_lake_tier == DataLakeTier.HOT
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = TelemetryDataLakeManagerAnalysis()
        assert a.id
        assert a.name == ""
        assert a.data_lake_partition == DataLakePartition.HOURLY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = TelemetryDataLakeManagerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_data_lake_partition == {}
        assert r.by_data_lake_format == {}
        assert r.by_data_lake_tier == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            data_lake_partition=DataLakePartition.HOURLY,
            data_lake_format=DataLakeFormat.ORC,
            data_lake_tier=DataLakeTier.COLD,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.data_lake_partition == DataLakePartition.HOURLY
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_data_lake_partition(self):
        eng = _engine()
        eng.record_item(name="a", data_lake_partition=DataLakePartition.DAILY)
        eng.record_item(name="b", data_lake_partition=DataLakePartition.HOURLY)
        assert len(eng.list_records(data_lake_partition=DataLakePartition.DAILY)) == 1

    def test_filter_by_data_lake_format(self):
        eng = _engine()
        eng.record_item(name="a", data_lake_format=DataLakeFormat.PARQUET)
        eng.record_item(name="b", data_lake_format=DataLakeFormat.ORC)
        assert len(eng.list_records(data_lake_format=DataLakeFormat.PARQUET)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
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
        eng.record_item(name="a", data_lake_partition=DataLakePartition.DAILY, score=90.0)
        eng.record_item(name="b", data_lake_partition=DataLakePartition.DAILY, score=70.0)
        result = eng.analyze_distribution()
        assert "daily" in result
        assert result["daily"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
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
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
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
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
