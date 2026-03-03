"""Tests for shieldops.observability.log_analytics_intelligence — LogAnalyticsIntelligence."""

from __future__ import annotations

from shieldops.observability.log_analytics_intelligence import (
    LogAnalyticsIntelligence,
    LogAnalyticsReport,
    LogPatternAnalysis,
    LogPatternRecord,
    LogPatternType,
    LogSource,
    PatternConfidence,
)


def _engine(**kw) -> LogAnalyticsIntelligence:
    return LogAnalyticsIntelligence(**kw)


class TestEnums:
    def test_log_pattern_type_error_cluster(self):
        assert LogPatternType.ERROR_CLUSTER == "error_cluster"

    def test_log_pattern_type_anomaly(self):
        assert LogPatternType.ANOMALY == "anomaly"

    def test_log_pattern_type_trend_shift(self):
        assert LogPatternType.TREND_SHIFT == "trend_shift"

    def test_log_pattern_type_correlation(self):
        assert LogPatternType.CORRELATION == "correlation"

    def test_log_pattern_type_outlier(self):
        assert LogPatternType.OUTLIER == "outlier"

    def test_log_source_application(self):
        assert LogSource.APPLICATION == "application"

    def test_log_source_infrastructure(self):
        assert LogSource.INFRASTRUCTURE == "infrastructure"

    def test_log_source_security(self):
        assert LogSource.SECURITY == "security"

    def test_log_source_audit(self):
        assert LogSource.AUDIT == "audit"

    def test_log_source_system(self):
        assert LogSource.SYSTEM == "system"

    def test_pattern_confidence_confirmed(self):
        assert PatternConfidence.CONFIRMED == "confirmed"

    def test_pattern_confidence_high(self):
        assert PatternConfidence.HIGH == "high"

    def test_pattern_confidence_medium(self):
        assert PatternConfidence.MEDIUM == "medium"

    def test_pattern_confidence_low(self):
        assert PatternConfidence.LOW == "low"

    def test_pattern_confidence_speculative(self):
        assert PatternConfidence.SPECULATIVE == "speculative"


class TestModels:
    def test_record_defaults(self):
        r = LogPatternRecord()
        assert r.id
        assert r.name == ""
        assert r.log_pattern_type == LogPatternType.ERROR_CLUSTER
        assert r.log_source == LogSource.APPLICATION
        assert r.pattern_confidence == PatternConfidence.SPECULATIVE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = LogPatternAnalysis()
        assert a.id
        assert a.name == ""
        assert a.log_pattern_type == LogPatternType.ERROR_CLUSTER
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = LogAnalyticsReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_log_pattern_type == {}
        assert r.by_log_source == {}
        assert r.by_pattern_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            log_pattern_type=LogPatternType.ERROR_CLUSTER,
            log_source=LogSource.INFRASTRUCTURE,
            pattern_confidence=PatternConfidence.CONFIRMED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.log_pattern_type == LogPatternType.ERROR_CLUSTER
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

    def test_filter_by_log_pattern_type(self):
        eng = _engine()
        eng.record_entry(name="a", log_pattern_type=LogPatternType.ERROR_CLUSTER)
        eng.record_entry(name="b", log_pattern_type=LogPatternType.ANOMALY)
        assert len(eng.list_records(log_pattern_type=LogPatternType.ERROR_CLUSTER)) == 1

    def test_filter_by_log_source(self):
        eng = _engine()
        eng.record_entry(name="a", log_source=LogSource.APPLICATION)
        eng.record_entry(name="b", log_source=LogSource.INFRASTRUCTURE)
        assert len(eng.list_records(log_source=LogSource.APPLICATION)) == 1

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
        eng.record_entry(name="a", log_pattern_type=LogPatternType.ANOMALY, score=90.0)
        eng.record_entry(name="b", log_pattern_type=LogPatternType.ANOMALY, score=70.0)
        result = eng.analyze_distribution()
        assert "anomaly" in result
        assert result["anomaly"]["count"] == 2

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
