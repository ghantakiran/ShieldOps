"""Tests for shieldops.agents.telemetry_analyzer — AgentTelemetryAnalyzer."""

from __future__ import annotations

from shieldops.agents.telemetry_analyzer import (
    AgentTelemetryAnalyzer,
    AnalysisScope,
    PerformanceTier,
    TelemetryAnalyzerReport,
    TelemetryBaseline,
    TelemetryMetric,
    TelemetryRecord,
)


def _engine(**kw) -> AgentTelemetryAnalyzer:
    return AgentTelemetryAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # TelemetryMetric (5)
    def test_metric_latency(self):
        assert TelemetryMetric.LATENCY == "latency"

    def test_metric_token_usage(self):
        assert TelemetryMetric.TOKEN_USAGE == "token_usage"  # noqa: S105

    def test_metric_accuracy(self):
        assert TelemetryMetric.ACCURACY == "accuracy"

    def test_metric_throughput(self):
        assert TelemetryMetric.THROUGHPUT == "throughput"

    def test_metric_error_rate(self):
        assert TelemetryMetric.ERROR_RATE == "error_rate"

    # PerformanceTier (5)
    def test_tier_excellent(self):
        assert PerformanceTier.EXCELLENT == "excellent"

    def test_tier_good(self):
        assert PerformanceTier.GOOD == "good"

    def test_tier_acceptable(self):
        assert PerformanceTier.ACCEPTABLE == "acceptable"

    def test_tier_poor(self):
        assert PerformanceTier.POOR == "poor"

    def test_tier_critical(self):
        assert PerformanceTier.CRITICAL == "critical"

    # AnalysisScope (5)
    def test_scope_single_run(self):
        assert AnalysisScope.SINGLE_RUN == "single_run"

    def test_scope_hourly(self):
        assert AnalysisScope.HOURLY == "hourly"

    def test_scope_daily(self):
        assert AnalysisScope.DAILY == "daily"

    def test_scope_weekly(self):
        assert AnalysisScope.WEEKLY == "weekly"

    def test_scope_monthly(self):
        assert AnalysisScope.MONTHLY == "monthly"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_telemetry_record_defaults(self):
        r = TelemetryRecord()
        assert r.id
        assert r.agent_name == ""
        assert r.telemetry_metric == TelemetryMetric.LATENCY
        assert r.performance_tier == PerformanceTier.GOOD
        assert r.analysis_scope == AnalysisScope.DAILY
        assert r.metric_value == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_telemetry_baseline_defaults(self):
        r = TelemetryBaseline()
        assert r.id
        assert r.baseline_name == ""
        assert r.telemetry_metric == TelemetryMetric.TOKEN_USAGE
        assert r.performance_tier == PerformanceTier.ACCEPTABLE
        assert r.threshold_value == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = TelemetryAnalyzerReport()
        assert r.total_records == 0
        assert r.total_baselines == 0
        assert r.performance_rate_pct == 0.0
        assert r.by_metric == {}
        assert r.by_tier == {}
        assert r.poor_performance_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_telemetry
# -------------------------------------------------------------------


class TestRecordTelemetry:
    def test_basic(self):
        eng = _engine()
        r = eng.record_telemetry(
            "agent-a",
            telemetry_metric=TelemetryMetric.ACCURACY,
            performance_tier=PerformanceTier.EXCELLENT,
        )
        assert r.agent_name == "agent-a"
        assert r.telemetry_metric == TelemetryMetric.ACCURACY

    def test_with_metric_value(self):
        eng = _engine()
        r = eng.record_telemetry("agent-b", metric_value=95.5)
        assert r.metric_value == 95.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_telemetry(f"agent-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_telemetry
# -------------------------------------------------------------------


class TestGetTelemetry:
    def test_found(self):
        eng = _engine()
        r = eng.record_telemetry("agent-a")
        assert eng.get_telemetry(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_telemetry("nonexistent") is None


# -------------------------------------------------------------------
# list_telemetry
# -------------------------------------------------------------------


class TestListTelemetry:
    def test_list_all(self):
        eng = _engine()
        eng.record_telemetry("agent-a")
        eng.record_telemetry("agent-b")
        assert len(eng.list_telemetry()) == 2

    def test_filter_by_agent(self):
        eng = _engine()
        eng.record_telemetry("agent-a")
        eng.record_telemetry("agent-b")
        results = eng.list_telemetry(agent_name="agent-a")
        assert len(results) == 1

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_telemetry("agent-a", telemetry_metric=TelemetryMetric.LATENCY)
        eng.record_telemetry("agent-b", telemetry_metric=TelemetryMetric.ACCURACY)
        results = eng.list_telemetry(telemetry_metric=TelemetryMetric.LATENCY)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_baseline
# -------------------------------------------------------------------


class TestAddBaseline:
    def test_basic(self):
        eng = _engine()
        r = eng.add_baseline(
            "baseline-1",
            telemetry_metric=TelemetryMetric.ERROR_RATE,
            performance_tier=PerformanceTier.GOOD,
            threshold_value=5.0,
        )
        assert r.baseline_name == "baseline-1"
        assert r.threshold_value == 5.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_baseline(f"baseline-{i}")
        assert len(eng._baselines) == 2


# -------------------------------------------------------------------
# analyze_agent_performance
# -------------------------------------------------------------------


class TestAnalyzeAgentPerformance:
    def test_with_data(self):
        eng = _engine()
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.EXCELLENT)
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.POOR)
        result = eng.analyze_agent_performance("agent-a")
        assert result["agent_name"] == "agent-a"
        assert result["total_records"] == 2
        assert result["good_performance_count"] == 1
        assert result["performance_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_agent_performance("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_performance_pct=50.0)
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.EXCELLENT)
        result = eng.analyze_agent_performance("agent-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_underperforming_agents
# -------------------------------------------------------------------


class TestIdentifyUnderperformingAgents:
    def test_with_underperforming(self):
        eng = _engine()
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.POOR)
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.CRITICAL)
        eng.record_telemetry("agent-b", performance_tier=PerformanceTier.EXCELLENT)
        results = eng.identify_underperforming_agents()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_underperforming_agents() == []


# -------------------------------------------------------------------
# rank_by_efficiency
# -------------------------------------------------------------------


class TestRankByEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_telemetry("agent-a", metric_value=90.0)
        eng.record_telemetry("agent-a", metric_value=80.0)
        eng.record_telemetry("agent-b", metric_value=50.0)
        results = eng.rank_by_efficiency()
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["avg_metric_value"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_efficiency() == []


# -------------------------------------------------------------------
# detect_performance_degradation
# -------------------------------------------------------------------


class TestDetectPerformanceDegradation:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_telemetry("agent-a", performance_tier=PerformanceTier.CRITICAL)
        eng.record_telemetry("agent-b", performance_tier=PerformanceTier.CRITICAL)
        results = eng.detect_performance_degradation()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.CRITICAL)
        assert eng.detect_performance_degradation() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.POOR)
        eng.record_telemetry("agent-b", performance_tier=PerformanceTier.EXCELLENT)
        eng.add_baseline("baseline-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_baselines == 1
        assert report.by_metric != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.recommendations[0] == "Agent telemetry performance meets targets"

    def test_poor_recommendation(self):
        eng = _engine()
        eng.record_telemetry("agent-a", performance_tier=PerformanceTier.POOR)
        report = eng.generate_report()
        assert "poor" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_telemetry("agent-a")
        eng.add_baseline("baseline-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._baselines) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_baselines"] == 0
        assert stats["metric_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_telemetry("agent-a", telemetry_metric=TelemetryMetric.LATENCY)
        eng.record_telemetry("agent-b", telemetry_metric=TelemetryMetric.ACCURACY)
        eng.add_baseline("baseline-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_baselines"] == 1
        assert stats["unique_agents"] == 2
