"""Tests for shieldops.sla.slo_observability_bridge — SloObservabilityBridge."""

from __future__ import annotations

from shieldops.sla.slo_observability_bridge import (
    BridgeSource,
    MappingQuality,
    SLIMapping,
    SLOBridgeAnalysis,
    SLOBridgeRecord,
    SloObservabilityBridge,
    SloObservabilityReport,
)


def _engine(**kw) -> SloObservabilityBridge:
    return SloObservabilityBridge(**kw)


class TestEnums:
    def test_sli_mapping_error_rate(self):
        assert SLIMapping.ERROR_RATE == "error_rate"

    def test_sli_mapping_latency_p99(self):
        assert SLIMapping.LATENCY_P99 == "latency_p99"

    def test_sli_mapping_availability(self):
        assert SLIMapping.AVAILABILITY == "availability"

    def test_sli_mapping_throughput(self):
        assert SLIMapping.THROUGHPUT == "throughput"

    def test_sli_mapping_saturation(self):
        assert SLIMapping.SATURATION == "saturation"

    def test_bridge_source_prometheus_rules(self):
        assert BridgeSource.PROMETHEUS_RULES == "prometheus_rules"

    def test_bridge_source_datadog_monitors(self):
        assert BridgeSource.DATADOG_MONITORS == "datadog_monitors"

    def test_bridge_source_custom_query(self):
        assert BridgeSource.CUSTOM_QUERY == "custom_query"

    def test_bridge_source_otel_metric(self):
        assert BridgeSource.OTEL_METRIC == "otel_metric"

    def test_bridge_source_derived(self):
        assert BridgeSource.DERIVED == "derived"

    def test_mapping_quality_precise(self):
        assert MappingQuality.PRECISE == "precise"

    def test_mapping_quality_approximate(self):
        assert MappingQuality.APPROXIMATE == "approximate"

    def test_mapping_quality_estimated(self):
        assert MappingQuality.ESTIMATED == "estimated"

    def test_mapping_quality_missing(self):
        assert MappingQuality.MISSING == "missing"

    def test_mapping_quality_unknown(self):
        assert MappingQuality.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = SLOBridgeRecord()
        assert r.id
        assert r.name == ""
        assert r.sli_mapping == SLIMapping.ERROR_RATE
        assert r.bridge_source == BridgeSource.PROMETHEUS_RULES
        assert r.mapping_quality == MappingQuality.UNKNOWN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SLOBridgeAnalysis()
        assert a.id
        assert a.name == ""
        assert a.sli_mapping == SLIMapping.ERROR_RATE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SloObservabilityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_sli_mapping == {}
        assert r.by_bridge_source == {}
        assert r.by_mapping_quality == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            sli_mapping=SLIMapping.ERROR_RATE,
            bridge_source=BridgeSource.DATADOG_MONITORS,
            mapping_quality=MappingQuality.PRECISE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.sli_mapping == SLIMapping.ERROR_RATE
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

    def test_filter_by_sli_mapping(self):
        eng = _engine()
        eng.record_entry(name="a", sli_mapping=SLIMapping.ERROR_RATE)
        eng.record_entry(name="b", sli_mapping=SLIMapping.LATENCY_P99)
        assert len(eng.list_records(sli_mapping=SLIMapping.ERROR_RATE)) == 1

    def test_filter_by_bridge_source(self):
        eng = _engine()
        eng.record_entry(name="a", bridge_source=BridgeSource.PROMETHEUS_RULES)
        eng.record_entry(name="b", bridge_source=BridgeSource.DATADOG_MONITORS)
        assert len(eng.list_records(bridge_source=BridgeSource.PROMETHEUS_RULES)) == 1

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
        eng.record_entry(name="a", sli_mapping=SLIMapping.LATENCY_P99, score=90.0)
        eng.record_entry(name="b", sli_mapping=SLIMapping.LATENCY_P99, score=70.0)
        result = eng.analyze_distribution()
        assert "latency_p99" in result
        assert result["latency_p99"]["count"] == 2

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
