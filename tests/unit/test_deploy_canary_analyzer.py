"""Tests for shieldops.changes.deploy_canary_analyzer — DeployCanaryAnalyzer."""

from __future__ import annotations

from shieldops.changes.deploy_canary_analyzer import (
    CanaryMetric,
    CanaryOutcome,
    CanaryRecord,
    CanarySignal,
    CanaryStrategy,
    DeployCanaryAnalyzer,
    DeployCanaryReport,
)


def _engine(**kw) -> DeployCanaryAnalyzer:
    return DeployCanaryAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_outcome_promoted(self):
        assert CanaryOutcome.PROMOTED == "promoted"

    def test_outcome_rolled_back(self):
        assert CanaryOutcome.ROLLED_BACK == "rolled_back"

    def test_outcome_extended(self):
        assert CanaryOutcome.EXTENDED == "extended"

    def test_outcome_paused(self):
        assert CanaryOutcome.PAUSED == "paused"

    def test_outcome_inconclusive(self):
        assert CanaryOutcome.INCONCLUSIVE == "inconclusive"

    def test_signal_latency_increase(self):
        assert CanarySignal.LATENCY_INCREASE == "latency_increase"

    def test_signal_error_spike(self):
        assert CanarySignal.ERROR_SPIKE == "error_spike"

    def test_signal_resource_anomaly(self):
        assert CanarySignal.RESOURCE_ANOMALY == "resource_anomaly"

    def test_signal_traffic_drop(self):
        assert CanarySignal.TRAFFIC_DROP == "traffic_drop"

    def test_signal_healthy(self):
        assert CanarySignal.HEALTHY == "healthy"

    def test_strategy_percentage(self):
        assert CanaryStrategy.PERCENTAGE == "percentage"

    def test_strategy_time_based(self):
        assert CanaryStrategy.TIME_BASED == "time_based"

    def test_strategy_metric_based(self):
        assert CanaryStrategy.METRIC_BASED == "metric_based"

    def test_strategy_region_based(self):
        assert CanaryStrategy.REGION_BASED == "region_based"

    def test_strategy_feature_flag(self):
        assert CanaryStrategy.FEATURE_FLAG == "feature_flag"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_canary_record_defaults(self):
        r = CanaryRecord()
        assert r.id
        assert r.canary_id == ""
        assert r.canary_outcome == CanaryOutcome.INCONCLUSIVE
        assert r.canary_signal == CanarySignal.HEALTHY
        assert r.canary_strategy == CanaryStrategy.PERCENTAGE
        assert r.success_rate == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_canary_metric_defaults(self):
        m = CanaryMetric()
        assert m.id
        assert m.canary_id == ""
        assert m.canary_outcome == CanaryOutcome.INCONCLUSIVE
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_deploy_canary_report_defaults(self):
        r = DeployCanaryReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.failed_canaries == 0
        assert r.avg_success_rate == 0.0
        assert r.by_outcome == {}
        assert r.by_signal == {}
        assert r.by_strategy == {}
        assert r.top_failed == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_canary
# ---------------------------------------------------------------------------


class TestRecordCanary:
    def test_basic(self):
        eng = _engine()
        r = eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.PROMOTED,
            canary_signal=CanarySignal.HEALTHY,
            canary_strategy=CanaryStrategy.PERCENTAGE,
            success_rate=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.canary_id == "CAN-001"
        assert r.canary_outcome == CanaryOutcome.PROMOTED
        assert r.canary_signal == CanarySignal.HEALTHY
        assert r.canary_strategy == CanaryStrategy.PERCENTAGE
        assert r.success_rate == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_canary(canary_id=f"CAN-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_canary
# ---------------------------------------------------------------------------


class TestGetCanary:
    def test_found(self):
        eng = _engine()
        r = eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.PROMOTED,
        )
        result = eng.get_canary(r.id)
        assert result is not None
        assert result.canary_outcome == CanaryOutcome.PROMOTED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_canary("nonexistent") is None


# ---------------------------------------------------------------------------
# list_canaries
# ---------------------------------------------------------------------------


class TestListCanaries:
    def test_list_all(self):
        eng = _engine()
        eng.record_canary(canary_id="CAN-001")
        eng.record_canary(canary_id="CAN-002")
        assert len(eng.list_canaries()) == 2

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.PROMOTED,
        )
        eng.record_canary(
            canary_id="CAN-002",
            canary_outcome=CanaryOutcome.ROLLED_BACK,
        )
        results = eng.list_canaries(
            canary_outcome=CanaryOutcome.PROMOTED,
        )
        assert len(results) == 1

    def test_filter_by_signal(self):
        eng = _engine()
        eng.record_canary(
            canary_id="CAN-001",
            canary_signal=CanarySignal.HEALTHY,
        )
        eng.record_canary(
            canary_id="CAN-002",
            canary_signal=CanarySignal.ERROR_SPIKE,
        )
        results = eng.list_canaries(
            canary_signal=CanarySignal.HEALTHY,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_canary(canary_id="CAN-001", team="sre")
        eng.record_canary(canary_id="CAN-002", team="platform")
        results = eng.list_canaries(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_canary(canary_id=f"CAN-{i}")
        assert len(eng.list_canaries(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.PROMOTED,
            metric_score=92.5,
            threshold=90.0,
            breached=False,
            description="latency check",
        )
        assert m.canary_id == "CAN-001"
        assert m.canary_outcome == CanaryOutcome.PROMOTED
        assert m.metric_score == 92.5
        assert m.threshold == 90.0
        assert m.breached is False
        assert m.description == "latency check"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(canary_id=f"CAN-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_canary_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCanaryDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.PROMOTED,
            success_rate=95.0,
        )
        eng.record_canary(
            canary_id="CAN-002",
            canary_outcome=CanaryOutcome.PROMOTED,
            success_rate=85.0,
        )
        result = eng.analyze_canary_distribution()
        assert "promoted" in result
        assert result["promoted"]["count"] == 2
        assert result["promoted"]["avg_success_rate"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_canary_distribution() == {}


# ---------------------------------------------------------------------------
# identify_failed_canaries
# ---------------------------------------------------------------------------


class TestIdentifyFailedCanaries:
    def test_detects_failed(self):
        eng = _engine()
        eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.ROLLED_BACK,
        )
        eng.record_canary(
            canary_id="CAN-002",
            canary_outcome=CanaryOutcome.PROMOTED,
        )
        results = eng.identify_failed_canaries()
        assert len(results) == 1
        assert results[0]["canary_id"] == "CAN-001"

    def test_detects_inconclusive(self):
        eng = _engine()
        eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.INCONCLUSIVE,
        )
        results = eng.identify_failed_canaries()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_canaries() == []


# ---------------------------------------------------------------------------
# rank_by_success_rate
# ---------------------------------------------------------------------------


class TestRankBySuccessRate:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_canary(canary_id="CAN-001", service="api", success_rate=90.0)
        eng.record_canary(canary_id="CAN-002", service="web", success_rate=70.0)
        results = eng.rank_by_success_rate()
        assert len(results) == 2
        assert results[0]["service"] == "web"
        assert results[0]["avg_success_rate"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_success_rate() == []


# ---------------------------------------------------------------------------
# detect_canary_trends
# ---------------------------------------------------------------------------


class TestDetectCanaryTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(canary_id="CAN-001", metric_score=50.0)
        result = eng.detect_canary_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(canary_id="CAN-001", metric_score=20.0)
        eng.add_metric(canary_id="CAN-002", metric_score=20.0)
        eng.add_metric(canary_id="CAN-003", metric_score=80.0)
        eng.add_metric(canary_id="CAN-004", metric_score=80.0)
        result = eng.detect_canary_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_canary_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.ROLLED_BACK,
            canary_signal=CanarySignal.ERROR_SPIKE,
            canary_strategy=CanaryStrategy.PERCENTAGE,
            success_rate=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DeployCanaryReport)
        assert report.total_records == 1
        assert report.failed_canaries == 1
        assert len(report.top_failed) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_canary(canary_id="CAN-001")
        eng.add_metric(canary_id="CAN-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["outcome_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_canary(
            canary_id="CAN-001",
            canary_outcome=CanaryOutcome.PROMOTED,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_canaries"] == 1
        assert "promoted" in stats["outcome_distribution"]
