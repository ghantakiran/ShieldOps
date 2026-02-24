"""Tests for shieldops.topology.service_health_agg — ServiceHealthAggregator.

Covers HealthSignalSource, HealthStatus, and AggregationStrategy enums,
HealthSignal / ServiceHealthScore / HealthAggReport models, and all
ServiceHealthAggregator operations including signal reporting, health
score calculation, degradation detection, service ranking, flapping
detection, availability calculation, and report generation.
"""

from __future__ import annotations

from shieldops.topology.service_health_agg import (
    AggregationStrategy,
    HealthAggReport,
    HealthSignal,
    HealthSignalSource,
    HealthStatus,
    ServiceHealthAggregator,
    ServiceHealthScore,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> ServiceHealthAggregator:
    return ServiceHealthAggregator(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of all three enums."""

    # -- HealthSignalSource (5 members) -----------------------------

    def test_source_metrics(self):
        assert HealthSignalSource.METRICS == "metrics"

    def test_source_alerts(self):
        assert HealthSignalSource.ALERTS == "alerts"

    def test_source_incidents(self):
        assert HealthSignalSource.INCIDENTS == "incidents"

    def test_source_dependencies(self):
        assert HealthSignalSource.DEPENDENCIES == "dependencies"

    def test_source_synthetic_checks(self):
        assert HealthSignalSource.SYNTHETIC_CHECKS == "synthetic_checks"

    # -- HealthStatus (5 members) -----------------------------------

    def test_status_healthy(self):
        assert HealthStatus.HEALTHY == "healthy"

    def test_status_degraded(self):
        assert HealthStatus.DEGRADED == "degraded"

    def test_status_partial_outage(self):
        assert HealthStatus.PARTIAL_OUTAGE == "partial_outage"

    def test_status_major_outage(self):
        assert HealthStatus.MAJOR_OUTAGE == "major_outage"

    def test_status_unknown(self):
        assert HealthStatus.UNKNOWN == "unknown"

    # -- AggregationStrategy (5 members) ----------------------------

    def test_strategy_worst_of(self):
        assert AggregationStrategy.WORST_OF == "worst_of"

    def test_strategy_weighted_average(self):
        assert AggregationStrategy.WEIGHTED_AVERAGE == "weighted_average"

    def test_strategy_majority_vote(self):
        assert AggregationStrategy.MAJORITY_VOTE == "majority_vote"

    def test_strategy_threshold_based(self):
        assert AggregationStrategy.THRESHOLD_BASED == "threshold_based"

    def test_strategy_custom(self):
        assert AggregationStrategy.CUSTOM == "custom"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_health_signal_defaults(self):
        s = HealthSignal()
        assert s.id
        assert s.service_name == ""
        assert s.source == HealthSignalSource.METRICS
        assert s.status == HealthStatus.UNKNOWN
        assert s.score == 100.0
        assert s.details == ""
        assert s.reported_at > 0
        assert s.created_at > 0

    def test_service_health_score_defaults(self):
        s = ServiceHealthScore()
        assert s.service_name == ""
        assert s.overall_status == HealthStatus.UNKNOWN
        assert s.overall_score == 0.0
        assert s.signal_count == 0
        assert s.by_source == {}
        assert s.last_updated > 0
        assert s.created_at > 0

    def test_health_agg_report_defaults(self):
        r = HealthAggReport()
        assert r.total_services == 0
        assert r.total_signals == 0
        assert r.avg_health_score == 0.0
        assert r.by_status == {}
        assert r.by_source == {}
        assert r.unhealthy_services == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# ReportSignal
# ===========================================================================


class TestReportSignal:
    """Test ServiceHealthAggregator.report_signal."""

    def test_basic_signal(self):
        eng = _engine()
        s = eng.report_signal(
            service_name="api",
            source=HealthSignalSource.METRICS,
            status=HealthStatus.HEALTHY,
            score=95.0,
        )
        assert s.id
        assert s.service_name == "api"
        assert s.source == HealthSignalSource.METRICS
        assert s.status == HealthStatus.HEALTHY
        assert s.score == 95.0

    def test_with_details(self):
        eng = _engine()
        s = eng.report_signal(
            service_name="web",
            source=HealthSignalSource.ALERTS,
            status=HealthStatus.DEGRADED,
            score=60.0,
            details="High error rate",
        )
        assert s.details == "High error rate"
        assert s.score == 60.0

    def test_eviction_on_overflow(self):
        eng = _engine(max_signals=3)
        eng.report_signal(service_name="a")
        eng.report_signal(service_name="b")
        eng.report_signal(service_name="c")
        s4 = eng.report_signal(service_name="d")
        items = eng.list_signals(limit=100)
        assert len(items) == 3
        assert items[-1].id == s4.id


# ===========================================================================
# GetSignal
# ===========================================================================


class TestGetSignal:
    """Test ServiceHealthAggregator.get_signal."""

    def test_found(self):
        eng = _engine()
        s = eng.report_signal(service_name="api")
        assert eng.get_signal(s.id) is s

    def test_not_found(self):
        eng = _engine()
        assert eng.get_signal("missing") is None


# ===========================================================================
# ListSignals
# ===========================================================================


class TestListSignals:
    """Test ServiceHealthAggregator.list_signals."""

    def test_all(self):
        eng = _engine()
        eng.report_signal(service_name="a")
        eng.report_signal(service_name="b")
        assert len(eng.list_signals()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.report_signal(service_name="api")
        eng.report_signal(service_name="web")
        eng.report_signal(service_name="api")
        results = eng.list_signals(service_name="api")
        assert len(results) == 2
        assert all(s.service_name == "api" for s in results)

    def test_filter_by_source(self):
        eng = _engine()
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.METRICS,
        )
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.ALERTS,
        )
        results = eng.list_signals(
            source=HealthSignalSource.ALERTS,
        )
        assert len(results) == 1
        assert results[0].source == HealthSignalSource.ALERTS

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.report_signal(service_name=f"svc-{i}")
        assert len(eng.list_signals(limit=3)) == 3


# ===========================================================================
# CalculateHealthScore
# ===========================================================================


class TestCalculateHealthScore:
    """Test ServiceHealthAggregator.calculate_health_score."""

    def test_empty_service(self):
        eng = _engine()
        score = eng.calculate_health_score("none")
        assert score.service_name == "none"
        assert score.signal_count == 0

    def test_healthy_service(self):
        eng = _engine()
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.METRICS,
            status=HealthStatus.HEALTHY,
            score=95.0,
        )
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.ALERTS,
            status=HealthStatus.HEALTHY,
            score=100.0,
        )
        score = eng.calculate_health_score("api")
        assert score.overall_score > 80
        assert score.overall_status == HealthStatus.HEALTHY

    def test_worst_of_strategy(self):
        eng = _engine()
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.METRICS,
            score=95.0,
        )
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.INCIDENTS,
            score=20.0,
        )
        score = eng.calculate_health_score(
            "api",
            strategy=AggregationStrategy.WORST_OF,
        )
        assert score.overall_score == 20.0

    def test_majority_vote_strategy(self):
        eng = _engine()
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
            score=100.0,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
            score=90.0,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.DEGRADED,
            score=60.0,
        )
        score = eng.calculate_health_score(
            "api",
            strategy=AggregationStrategy.MAJORITY_VOTE,
        )
        assert score.overall_score == 100.0


# ===========================================================================
# DetectHealthDegradation
# ===========================================================================


class TestDetectHealthDegradation:
    """Test ServiceHealthAggregator.detect_health_degradation."""

    def test_with_degraded_signals(self):
        eng = _engine(health_threshold=70.0)
        eng.report_signal(
            service_name="api",
            score=90.0,
        )
        eng.report_signal(
            service_name="api",
            score=30.0,
        )
        degraded = eng.detect_health_degradation("api")
        assert len(degraded) == 1
        assert degraded[0].score == 30.0

    def test_no_degradation(self):
        eng = _engine(health_threshold=70.0)
        eng.report_signal(
            service_name="api",
            score=90.0,
        )
        assert eng.detect_health_degradation("api") == []


# ===========================================================================
# RankServicesByHealth
# ===========================================================================


class TestRankServicesByHealth:
    """Test ServiceHealthAggregator.rank_services_by_health."""

    def test_ranking(self):
        eng = _engine()
        eng.report_signal(
            service_name="healthy-svc",
            score=95.0,
        )
        eng.report_signal(
            service_name="sick-svc",
            score=20.0,
        )
        ranked = eng.rank_services_by_health()
        assert len(ranked) == 2
        assert ranked[0].service_name == "sick-svc"
        assert ranked[1].service_name == "healthy-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_services_by_health() == []


# ===========================================================================
# IdentifyFlappingServices
# ===========================================================================


class TestIdentifyFlappingServices:
    """Test ServiceHealthAggregator.identify_flapping_services."""

    def test_flapping(self):
        eng = _engine()
        import time as t

        base = t.time()
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
            reported_at=base,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.DEGRADED,
            reported_at=base + 1,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
            reported_at=base + 2,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.MAJOR_OUTAGE,
            reported_at=base + 3,
        )
        flapping = eng.identify_flapping_services()
        assert len(flapping) == 1
        assert flapping[0]["service_name"] == "api"
        assert flapping[0]["status_changes"] >= 2

    def test_stable(self):
        eng = _engine()
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
        )
        assert eng.identify_flapping_services() == []


# ===========================================================================
# CalculateAvailabilityPct
# ===========================================================================


class TestCalculateAvailabilityPct:
    """Test ServiceHealthAggregator.calculate_availability_pct."""

    def test_all_healthy(self):
        eng = _engine()
        for _ in range(5):
            eng.report_signal(
                service_name="api",
                status=HealthStatus.HEALTHY,
            )
        assert eng.calculate_availability_pct("api") == 100.0

    def test_mixed(self):
        eng = _engine()
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.DEGRADED,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.HEALTHY,
        )
        eng.report_signal(
            service_name="api",
            status=HealthStatus.MAJOR_OUTAGE,
        )
        assert eng.calculate_availability_pct("api") == 50.0

    def test_no_signals(self):
        eng = _engine()
        assert eng.calculate_availability_pct("api") == 0.0


# ===========================================================================
# GenerateHealthReport
# ===========================================================================


class TestGenerateHealthReport:
    """Test ServiceHealthAggregator.generate_health_report."""

    def test_basic_report(self):
        eng = _engine(health_threshold=70.0)
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.METRICS,
            status=HealthStatus.HEALTHY,
            score=95.0,
        )
        eng.report_signal(
            service_name="web",
            source=HealthSignalSource.ALERTS,
            status=HealthStatus.MAJOR_OUTAGE,
            score=10.0,
        )
        report = eng.generate_health_report()
        assert isinstance(report, HealthAggReport)
        assert report.total_services == 2
        assert report.total_signals == 2
        assert report.avg_health_score > 0
        assert report.generated_at > 0
        assert len(report.by_source) >= 1

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_health_report()
        assert report.total_services == 0
        assert report.total_signals == 0

    def test_report_recommendations(self):
        eng = _engine(health_threshold=70.0)
        eng.report_signal(
            service_name="sick-svc",
            status=HealthStatus.MAJOR_OUTAGE,
            score=10.0,
        )
        report = eng.generate_health_report()
        assert len(report.recommendations) >= 1
        assert len(report.unhealthy_services) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test ServiceHealthAggregator.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.report_signal(service_name="api")
        eng.clear_data()
        assert len(eng.list_signals()) == 0
        stats = eng.get_stats()
        assert stats["total_signals"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test ServiceHealthAggregator.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_signals"] == 0
        assert stats["unique_services"] == 0
        assert stats["avg_signal_score"] == 0.0
        assert stats["source_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.report_signal(
            service_name="api",
            source=HealthSignalSource.METRICS,
            status=HealthStatus.HEALTHY,
            score=90.0,
        )
        eng.report_signal(
            service_name="web",
            source=HealthSignalSource.ALERTS,
            status=HealthStatus.DEGRADED,
            score=60.0,
        )
        stats = eng.get_stats()
        assert stats["total_signals"] == 2
        assert stats["unique_services"] == 2
        assert stats["avg_signal_score"] == 75.0
        assert stats["source_distribution"]["metrics"] == 1
        assert stats["source_distribution"]["alerts"] == 1
        assert stats["status_distribution"]["healthy"] == 1
        assert stats["status_distribution"]["degraded"] == 1
