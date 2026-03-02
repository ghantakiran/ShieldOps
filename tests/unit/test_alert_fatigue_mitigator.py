"""Tests for shieldops.security.alert_fatigue_mitigator — AlertFatigueMitigator."""

from __future__ import annotations

from shieldops.security.alert_fatigue_mitigator import (
    AlertFatigueMitigator,
    FatigueAnalysis,
    FatigueLevel,
    FatigueRecord,
    FatigueReport,
    FatigueSource,
    MitigationStrategy,
)


def _engine(**kw) -> AlertFatigueMitigator:
    return AlertFatigueMitigator(**kw)


class TestEnums:
    def test_fatiguesource_val1(self):
        assert FatigueSource.VOLUME_OVERLOAD == "volume_overload"

    def test_fatiguesource_val2(self):
        assert FatigueSource.REPETITIVE_ALERTS == "repetitive_alerts"

    def test_fatiguesource_val3(self):
        assert FatigueSource.LOW_FIDELITY == "low_fidelity"

    def test_fatiguesource_val4(self):
        assert FatigueSource.POOR_CONTEXT == "poor_context"

    def test_fatiguesource_val5(self):
        assert FatigueSource.IRRELEVANT == "irrelevant"

    def test_mitigationstrategy_val1(self):
        assert MitigationStrategy.AGGREGATION == "aggregation"

    def test_mitigationstrategy_val2(self):
        assert MitigationStrategy.DEDUPLICATION == "deduplication"

    def test_mitigationstrategy_val3(self):
        assert MitigationStrategy.PRIORITIZATION == "prioritization"

    def test_mitigationstrategy_val4(self):
        assert MitigationStrategy.SUPPRESSION == "suppression"

    def test_mitigationstrategy_val5(self):
        assert MitigationStrategy.ENRICHMENT == "enrichment"

    def test_fatiguelevel_val1(self):
        assert FatigueLevel.CRITICAL == "critical"

    def test_fatiguelevel_val2(self):
        assert FatigueLevel.HIGH == "high"

    def test_fatiguelevel_val3(self):
        assert FatigueLevel.MODERATE == "moderate"

    def test_fatiguelevel_val4(self):
        assert FatigueLevel.LOW == "low"

    def test_fatiguelevel_val5(self):
        assert FatigueLevel.HEALTHY == "healthy"


class TestModels:
    def test_record_defaults(self):
        r = FatigueRecord()
        assert r.id
        assert r.source_name == ""

    def test_analysis_defaults(self):
        a = FatigueAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = FatigueReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_fatigue(
            source_name="test",
            fatigue_source=FatigueSource.REPETITIVE_ALERTS,
            fatigue_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.source_name == "test"
        assert r.fatigue_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_fatigue(source_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_fatigue(source_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_fatigue(source_name="a")
        eng.record_fatigue(source_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_fatigue(source_name="a", fatigue_source=FatigueSource.VOLUME_OVERLOAD)
        eng.record_fatigue(source_name="b", fatigue_source=FatigueSource.REPETITIVE_ALERTS)
        assert len(eng.list_records(fatigue_source=FatigueSource.VOLUME_OVERLOAD)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_fatigue(source_name="a", mitigation_strategy=MitigationStrategy.AGGREGATION)
        eng.record_fatigue(source_name="b", mitigation_strategy=MitigationStrategy.DEDUPLICATION)
        assert len(eng.list_records(mitigation_strategy=MitigationStrategy.AGGREGATION)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_fatigue(source_name="a", team="sec")
        eng.record_fatigue(source_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_fatigue(source_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            source_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(source_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_fatigue(
            source_name="a", fatigue_source=FatigueSource.VOLUME_OVERLOAD, fatigue_score=90.0
        )
        eng.record_fatigue(
            source_name="b", fatigue_source=FatigueSource.VOLUME_OVERLOAD, fatigue_score=70.0
        )
        result = eng.analyze_distribution()
        assert FatigueSource.VOLUME_OVERLOAD.value in result
        assert result[FatigueSource.VOLUME_OVERLOAD.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_fatigue(source_name="a", fatigue_score=60.0)
        eng.record_fatigue(source_name="b", fatigue_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_fatigue(source_name="a", fatigue_score=50.0)
        eng.record_fatigue(source_name="b", fatigue_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["fatigue_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_fatigue(source_name="a", service="auth", fatigue_score=90.0)
        eng.record_fatigue(source_name="b", service="api", fatigue_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(source_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(source_name="a", analysis_score=20.0)
        eng.add_analysis(source_name="b", analysis_score=20.0)
        eng.add_analysis(source_name="c", analysis_score=80.0)
        eng.add_analysis(source_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_fatigue(source_name="test", fatigue_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_fatigue(source_name="test")
        eng.add_analysis(source_name="test")
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
        eng.record_fatigue(source_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
