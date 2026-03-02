"""Tests for shieldops.security.alert_context_assembler — AlertContextAssembler."""

from __future__ import annotations

from shieldops.security.alert_context_assembler import (
    AlertContextAssembler,
    AssemblyMethod,
    ContextAnalysis,
    ContextRecord,
    ContextRelevance,
    ContextReport,
    ContextSource,
)


def _engine(**kw) -> AlertContextAssembler:
    return AlertContextAssembler(**kw)


class TestEnums:
    def test_contextsource_val1(self):
        assert ContextSource.ASSET_INVENTORY == "asset_inventory"

    def test_contextsource_val2(self):
        assert ContextSource.THREAT_INTEL == "threat_intel"

    def test_contextsource_val3(self):
        assert ContextSource.USER_DIRECTORY == "user_directory"

    def test_contextsource_val4(self):
        assert ContextSource.NETWORK_TOPOLOGY == "network_topology"

    def test_contextsource_val5(self):
        assert ContextSource.VULN_DATABASE == "vuln_database"

    def test_contextrelevance_val1(self):
        assert ContextRelevance.CRITICAL == "critical"

    def test_contextrelevance_val2(self):
        assert ContextRelevance.HIGH == "high"

    def test_contextrelevance_val3(self):
        assert ContextRelevance.MEDIUM == "medium"

    def test_contextrelevance_val4(self):
        assert ContextRelevance.LOW == "low"

    def test_contextrelevance_val5(self):
        assert ContextRelevance.NONE == "none"

    def test_assemblymethod_val1(self):
        assert AssemblyMethod.AUTOMATED == "automated"

    def test_assemblymethod_val2(self):
        assert AssemblyMethod.SEMI_AUTOMATED == "semi_automated"

    def test_assemblymethod_val3(self):
        assert AssemblyMethod.MANUAL == "manual"

    def test_assemblymethod_val4(self):
        assert AssemblyMethod.CACHED == "cached"

    def test_assemblymethod_val5(self):
        assert AssemblyMethod.REALTIME == "realtime"


class TestModels:
    def test_record_defaults(self):
        r = ContextRecord()
        assert r.id
        assert r.alert_name == ""

    def test_analysis_defaults(self):
        a = ContextAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = ContextReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_context(
            alert_name="test",
            context_source=ContextSource.THREAT_INTEL,
            enrichment_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.alert_name == "test"
        assert r.enrichment_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_context(alert_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_context(alert_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_context(alert_name="a")
        eng.record_context(alert_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_context(alert_name="a", context_source=ContextSource.ASSET_INVENTORY)
        eng.record_context(alert_name="b", context_source=ContextSource.THREAT_INTEL)
        assert len(eng.list_records(context_source=ContextSource.ASSET_INVENTORY)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_context(alert_name="a", context_relevance=ContextRelevance.CRITICAL)
        eng.record_context(alert_name="b", context_relevance=ContextRelevance.HIGH)
        assert len(eng.list_records(context_relevance=ContextRelevance.CRITICAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_context(alert_name="a", team="sec")
        eng.record_context(alert_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_context(alert_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            alert_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(alert_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_context(
            alert_name="a", context_source=ContextSource.ASSET_INVENTORY, enrichment_score=90.0
        )
        eng.record_context(
            alert_name="b", context_source=ContextSource.ASSET_INVENTORY, enrichment_score=70.0
        )
        result = eng.analyze_distribution()
        assert ContextSource.ASSET_INVENTORY.value in result
        assert result[ContextSource.ASSET_INVENTORY.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_context(alert_name="a", enrichment_score=60.0)
        eng.record_context(alert_name="b", enrichment_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_context(alert_name="a", enrichment_score=50.0)
        eng.record_context(alert_name="b", enrichment_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["enrichment_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_context(alert_name="a", service="auth", enrichment_score=90.0)
        eng.record_context(alert_name="b", service="api", enrichment_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(alert_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(alert_name="a", analysis_score=20.0)
        eng.add_analysis(alert_name="b", analysis_score=20.0)
        eng.add_analysis(alert_name="c", analysis_score=80.0)
        eng.add_analysis(alert_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_context(alert_name="test", enrichment_score=50.0)
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
        eng.record_context(alert_name="test")
        eng.add_analysis(alert_name="test")
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
        eng.record_context(alert_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
