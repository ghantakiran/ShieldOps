"""Tests for shieldops.observability.intelligent_retention_manager — IntelligentRetentionManager."""

from __future__ import annotations

from shieldops.observability.intelligent_retention_manager import (
    DataValue,
    IntelligentRetentionManager,
    IntelligentRetentionManagerAnalysis,
    IntelligentRetentionManagerRecord,
    IntelligentRetentionManagerReport,
    RetentionAction,
    RetentionPolicy,
)


def _engine(**kw) -> IntelligentRetentionManager:
    return IntelligentRetentionManager(**kw)


class TestEnums:
    def test_retention_policy_first(self):
        assert RetentionPolicy.HOT_30D == "hot_30d"

    def test_retention_policy_second(self):
        assert RetentionPolicy.WARM_90D == "warm_90d"

    def test_retention_policy_third(self):
        assert RetentionPolicy.COLD_365D == "cold_365d"

    def test_retention_policy_fourth(self):
        assert RetentionPolicy.ARCHIVE_UNLIMITED == "archive_unlimited"

    def test_retention_policy_fifth(self):
        assert RetentionPolicy.CUSTOM == "custom"

    def test_data_value_first(self):
        assert DataValue.CRITICAL == "critical"

    def test_data_value_second(self):
        assert DataValue.HIGH == "high"

    def test_data_value_third(self):
        assert DataValue.MEDIUM == "medium"

    def test_data_value_fourth(self):
        assert DataValue.LOW == "low"

    def test_data_value_fifth(self):
        assert DataValue.MINIMAL == "minimal"

    def test_retention_action_first(self):
        assert RetentionAction.RETAIN == "retain"

    def test_retention_action_second(self):
        assert RetentionAction.DOWNSAMPLE == "downsample"

    def test_retention_action_third(self):
        assert RetentionAction.COMPRESS == "compress"

    def test_retention_action_fourth(self):
        assert RetentionAction.ARCHIVE == "archive"

    def test_retention_action_fifth(self):
        assert RetentionAction.DELETE == "delete"


class TestModels:
    def test_record_defaults(self):
        r = IntelligentRetentionManagerRecord()
        assert r.id
        assert r.name == ""
        assert r.retention_policy == RetentionPolicy.HOT_30D
        assert r.data_value == DataValue.CRITICAL
        assert r.retention_action == RetentionAction.RETAIN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = IntelligentRetentionManagerAnalysis()
        assert a.id
        assert a.name == ""
        assert a.retention_policy == RetentionPolicy.HOT_30D
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = IntelligentRetentionManagerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_retention_policy == {}
        assert r.by_data_value == {}
        assert r.by_retention_action == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            retention_policy=RetentionPolicy.HOT_30D,
            data_value=DataValue.HIGH,
            retention_action=RetentionAction.COMPRESS,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.retention_policy == RetentionPolicy.HOT_30D
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

    def test_filter_by_retention_policy(self):
        eng = _engine()
        eng.record_item(name="a", retention_policy=RetentionPolicy.WARM_90D)
        eng.record_item(name="b", retention_policy=RetentionPolicy.HOT_30D)
        assert len(eng.list_records(retention_policy=RetentionPolicy.WARM_90D)) == 1

    def test_filter_by_data_value(self):
        eng = _engine()
        eng.record_item(name="a", data_value=DataValue.CRITICAL)
        eng.record_item(name="b", data_value=DataValue.HIGH)
        assert len(eng.list_records(data_value=DataValue.CRITICAL)) == 1

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
        eng.record_item(name="a", retention_policy=RetentionPolicy.WARM_90D, score=90.0)
        eng.record_item(name="b", retention_policy=RetentionPolicy.WARM_90D, score=70.0)
        result = eng.analyze_distribution()
        assert "warm_90d" in result
        assert result["warm_90d"]["count"] == 2

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
