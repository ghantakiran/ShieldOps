"""Tests for shieldops.analytics.reliability_metrics — ReliabilityMetricsCollector."""

from __future__ import annotations

from shieldops.analytics.reliability_metrics import (
    MetricDataPoint,
    MetricSource,
    MetricType,
    ReliabilityMetricsCollector,
    ReliabilityMetricsReport,
    ReliabilityRecord,
    ReliabilityTier,
)


def _engine(**kw) -> ReliabilityMetricsCollector:
    return ReliabilityMetricsCollector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_type_mttr(self):
        assert MetricType.MTTR == "mttr"

    def test_metric_type_mtbf(self):
        assert MetricType.MTBF == "mtbf"

    def test_metric_type_change_failure_rate(self):
        assert MetricType.CHANGE_FAILURE_RATE == "change_failure_rate"

    def test_metric_type_deployment_frequency(self):
        assert MetricType.DEPLOYMENT_FREQUENCY == "deployment_frequency"

    def test_metric_type_availability(self):
        assert MetricType.AVAILABILITY == "availability"

    def test_reliability_tier_elite(self):
        assert ReliabilityTier.ELITE == "elite"

    def test_reliability_tier_high(self):
        assert ReliabilityTier.HIGH == "high"

    def test_reliability_tier_medium(self):
        assert ReliabilityTier.MEDIUM == "medium"

    def test_reliability_tier_low(self):
        assert ReliabilityTier.LOW == "low"

    def test_reliability_tier_unreliable(self):
        assert ReliabilityTier.UNRELIABLE == "unreliable"

    def test_metric_source_incident_data(self):
        assert MetricSource.INCIDENT_DATA == "incident_data"

    def test_metric_source_deployment_data(self):
        assert MetricSource.DEPLOYMENT_DATA == "deployment_data"

    def test_metric_source_monitoring(self):
        assert MetricSource.MONITORING == "monitoring"

    def test_metric_source_slo_tracking(self):
        assert MetricSource.SLO_TRACKING == "slo_tracking"

    def test_metric_source_manual_entry(self):
        assert MetricSource.MANUAL_ENTRY == "manual_entry"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_reliability_record_defaults(self):
        r = ReliabilityRecord()
        assert r.id
        assert r.service_id == ""
        assert r.metric_type == MetricType.MTTR
        assert r.reliability_tier == ReliabilityTier.UNRELIABLE
        assert r.metric_source == MetricSource.INCIDENT_DATA
        assert r.reliability_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_metric_data_point_defaults(self):
        d = MetricDataPoint()
        assert d.id
        assert d.data_point_name == ""
        assert d.metric_type == MetricType.MTTR
        assert d.value == 0.0
        assert d.samples_count == 0
        assert d.description == ""
        assert d.created_at > 0

    def test_reliability_metrics_report_defaults(self):
        r = ReliabilityMetricsReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_data_points == 0
        assert r.reliable_services == 0
        assert r.avg_reliability_score == 0.0
        assert r.by_type == {}
        assert r.by_tier == {}
        assert r.by_source == {}
        assert r.low_reliability == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_metric
# ---------------------------------------------------------------------------


class TestRecordMetric:
    def test_basic(self):
        eng = _engine()
        r = eng.record_metric(
            service_id="SVC-001",
            metric_type=MetricType.AVAILABILITY,
            reliability_tier=ReliabilityTier.ELITE,
            metric_source=MetricSource.SLO_TRACKING,
            reliability_score=99.9,
            team="sre",
        )
        assert r.service_id == "SVC-001"
        assert r.metric_type == MetricType.AVAILABILITY
        assert r.reliability_tier == ReliabilityTier.ELITE
        assert r.metric_source == MetricSource.SLO_TRACKING
        assert r.reliability_score == 99.9
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_metric(service_id=f"SVC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_metric
# ---------------------------------------------------------------------------


class TestGetMetric:
    def test_found(self):
        eng = _engine()
        r = eng.record_metric(
            service_id="SVC-001",
            metric_type=MetricType.MTBF,
        )
        result = eng.get_metric(r.id)
        assert result is not None
        assert result.metric_type == MetricType.MTBF

    def test_not_found(self):
        eng = _engine()
        assert eng.get_metric("nonexistent") is None


# ---------------------------------------------------------------------------
# list_metrics
# ---------------------------------------------------------------------------


class TestListMetrics:
    def test_list_all(self):
        eng = _engine()
        eng.record_metric(service_id="SVC-001")
        eng.record_metric(service_id="SVC-002")
        assert len(eng.list_metrics()) == 2

    def test_filter_by_metric_type(self):
        eng = _engine()
        eng.record_metric(
            service_id="SVC-001",
            metric_type=MetricType.MTTR,
        )
        eng.record_metric(
            service_id="SVC-002",
            metric_type=MetricType.AVAILABILITY,
        )
        results = eng.list_metrics(metric_type=MetricType.MTTR)
        assert len(results) == 1

    def test_filter_by_reliability_tier(self):
        eng = _engine()
        eng.record_metric(
            service_id="SVC-001",
            reliability_tier=ReliabilityTier.ELITE,
        )
        eng.record_metric(
            service_id="SVC-002",
            reliability_tier=ReliabilityTier.LOW,
        )
        results = eng.list_metrics(reliability_tier=ReliabilityTier.ELITE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_metric(service_id="SVC-001", team="sre")
        eng.record_metric(service_id="SVC-002", team="platform")
        results = eng.list_metrics(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_metric(service_id=f"SVC-{i}")
        assert len(eng.list_metrics(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_data_point
# ---------------------------------------------------------------------------


class TestAddDataPoint:
    def test_basic(self):
        eng = _engine()
        dp = eng.add_data_point(
            data_point_name="latency-p99-weekly",
            metric_type=MetricType.CHANGE_FAILURE_RATE,
            value=8.5,
            samples_count=3,
            description="Weekly change failure rate measurement",
        )
        assert dp.data_point_name == "latency-p99-weekly"
        assert dp.metric_type == MetricType.CHANGE_FAILURE_RATE
        assert dp.value == 8.5
        assert dp.samples_count == 3

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_data_point(data_point_name=f"dp-{i}")
        assert len(eng._data_points) == 2


# ---------------------------------------------------------------------------
# analyze_reliability_trends
# ---------------------------------------------------------------------------


class TestAnalyzeReliabilityTrends:
    def test_with_data(self):
        eng = _engine()
        eng.record_metric(
            service_id="SVC-001",
            metric_type=MetricType.MTTR,
            reliability_score=90.0,
        )
        eng.record_metric(
            service_id="SVC-002",
            metric_type=MetricType.MTTR,
            reliability_score=80.0,
        )
        result = eng.analyze_reliability_trends()
        assert "mttr" in result
        assert result["mttr"]["count"] == 2
        assert result["mttr"]["avg_reliability_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_reliability_trends() == {}


# ---------------------------------------------------------------------------
# identify_low_reliability_services
# ---------------------------------------------------------------------------


class TestIdentifyLowReliabilityServices:
    def test_detects_low(self):
        eng = _engine(min_reliability_score=90.0)
        eng.record_metric(
            service_id="SVC-001",
            reliability_score=50.0,
        )
        eng.record_metric(
            service_id="SVC-002",
            reliability_score=95.0,
        )
        results = eng.identify_low_reliability_services()
        assert len(results) == 1
        assert results[0]["service_id"] == "SVC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_reliability_services() == []


# ---------------------------------------------------------------------------
# rank_by_reliability_score
# ---------------------------------------------------------------------------


class TestRankByReliabilityScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_metric(service_id="SVC-001", team="sre", reliability_score=90.0)
        eng.record_metric(service_id="SVC-002", team="sre", reliability_score=80.0)
        eng.record_metric(service_id="SVC-003", team="platform", reliability_score=50.0)
        results = eng.rank_by_reliability_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["total_reliability"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_reliability_score() == []


# ---------------------------------------------------------------------------
# detect_reliability_regression
# ---------------------------------------------------------------------------


class TestDetectReliabilityRegression:
    def test_stable(self):
        eng = _engine()
        for score in [80.0, 80.0, 80.0, 80.0]:
            eng.record_metric(service_id="SVC", reliability_score=score)
        result = eng.detect_reliability_regression()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [50.0, 50.0, 90.0, 90.0]:
            eng.record_metric(service_id="SVC", reliability_score=score)
        result = eng.detect_reliability_regression()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_reliability_regression()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_reliability_score=90.0)
        eng.record_metric(
            service_id="SVC-001",
            metric_type=MetricType.MTTR,
            reliability_tier=ReliabilityTier.LOW,
            reliability_score=50.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ReliabilityMetricsReport)
        assert report.total_records == 1
        assert report.avg_reliability_score == 50.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_metric(service_id="SVC-001")
        eng.add_data_point(data_point_name="dp1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._data_points) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_data_points"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_metric(
            service_id="SVC-001",
            metric_type=MetricType.AVAILABILITY,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "availability" in stats["type_distribution"]
