"""Tests for shieldops.sla.availability_tracker — PlatformAvailabilityTracker."""

from __future__ import annotations

from shieldops.sla.availability_tracker import (
    AvailabilityRecord,
    AvailabilityReport,
    AvailabilityStatus,
    AvailabilityTrend,
    OutageCategory,
    OutageEvent,
    PlatformAvailabilityTracker,
)


def _engine(**kw) -> PlatformAvailabilityTracker:
    return PlatformAvailabilityTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # AvailabilityStatus (5)
    def test_status_fully_available(self):
        assert AvailabilityStatus.FULLY_AVAILABLE == "fully_available"

    def test_status_partially_degraded(self):
        assert AvailabilityStatus.PARTIALLY_DEGRADED == "partially_degraded"

    def test_status_major_outage(self):
        assert AvailabilityStatus.MAJOR_OUTAGE == "major_outage"

    def test_status_maintenance(self):
        assert AvailabilityStatus.MAINTENANCE == "maintenance"

    def test_status_unknown(self):
        assert AvailabilityStatus.UNKNOWN == "unknown"

    # OutageCategory (5)
    def test_category_infrastructure(self):
        assert OutageCategory.INFRASTRUCTURE == "infrastructure"

    def test_category_application(self):
        assert OutageCategory.APPLICATION == "application"

    def test_category_network(self):
        assert OutageCategory.NETWORK == "network"

    def test_category_database(self):
        assert OutageCategory.DATABASE == "database"

    def test_category_third_party(self):
        assert OutageCategory.THIRD_PARTY == "third_party"

    # AvailabilityTrend (5)
    def test_trend_improving(self):
        assert AvailabilityTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert AvailabilityTrend.STABLE == "stable"

    def test_trend_declining(self):
        assert AvailabilityTrend.DECLINING == "declining"

    def test_trend_volatile(self):
        assert AvailabilityTrend.VOLATILE == "volatile"

    def test_trend_insufficient(self):
        assert AvailabilityTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_availability_record_defaults(self):
        r = AvailabilityRecord()
        assert r.id
        assert r.service == ""
        assert r.availability_pct == 100.0
        assert r.status == AvailabilityStatus.FULLY_AVAILABLE
        assert r.outage_minutes == 0.0
        assert r.category == OutageCategory.INFRASTRUCTURE
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_outage_event_defaults(self):
        o = OutageEvent()
        assert o.id
        assert o.service == ""
        assert o.start_time == 0.0
        assert o.end_time == 0.0
        assert o.duration_minutes == 0.0
        assert o.category == OutageCategory.INFRASTRUCTURE
        assert o.root_cause == ""
        assert o.created_at > 0

    def test_report_defaults(self):
        r = AvailabilityReport()
        assert r.total_records == 0
        assert r.total_outages == 0
        assert r.avg_availability_pct == 0.0
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.below_target_services == []
        assert r.longest_outages == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_availability
# -------------------------------------------------------------------


class TestRecordAvailability:
    def test_basic(self):
        eng = _engine()
        r = eng.record_availability(
            "svc-a",
            availability_pct=99.5,
            status=(AvailabilityStatus.PARTIALLY_DEGRADED),
        )
        assert r.service == "svc-a"
        assert r.availability_pct == 99.5
        assert r.status == AvailabilityStatus.PARTIALLY_DEGRADED

    def test_with_team(self):
        eng = _engine()
        r = eng.record_availability("svc-b", team="platform")
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_availability(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_availability
# -------------------------------------------------------------------


class TestGetAvailability:
    def test_found(self):
        eng = _engine()
        r = eng.record_availability("svc-a")
        assert eng.get_availability(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_availability("nonexistent") is None


# -------------------------------------------------------------------
# list_availabilities
# -------------------------------------------------------------------


class TestListAvailabilities:
    def test_list_all(self):
        eng = _engine()
        eng.record_availability("svc-a")
        eng.record_availability("svc-b")
        assert len(eng.list_availabilities()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_availability(
            "svc-a",
            status=(AvailabilityStatus.FULLY_AVAILABLE),
        )
        eng.record_availability(
            "svc-b",
            status=AvailabilityStatus.MAJOR_OUTAGE,
        )
        results = eng.list_availabilities(status=(AvailabilityStatus.FULLY_AVAILABLE))
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_availability(
            "svc-a",
            category=OutageCategory.INFRASTRUCTURE,
        )
        eng.record_availability(
            "svc-b",
            category=OutageCategory.NETWORK,
        )
        results = eng.list_availabilities(category=OutageCategory.INFRASTRUCTURE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_outage
# -------------------------------------------------------------------


class TestAddOutage:
    def test_basic(self):
        eng = _engine()
        o = eng.add_outage(
            "svc-a",
            duration_minutes=30.0,
            root_cause="disk full",
        )
        assert o.service == "svc-a"
        assert o.duration_minutes == 30.0
        assert o.root_cause == "disk full"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_outage(f"svc-{i}")
        assert len(eng._outages) == 2


# -------------------------------------------------------------------
# analyze_availability_by_service
# -------------------------------------------------------------------


class TestAnalyzeAvailabilityByService:
    def test_with_data(self):
        eng = _engine()
        eng.record_availability("svc-a", availability_pct=99.0)
        eng.record_availability("svc-a", availability_pct=99.8)
        results = eng.analyze_availability_by_service()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"
        assert results[0]["avg_availability_pct"] == 99.4

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_availability_by_service() == []


# -------------------------------------------------------------------
# identify_below_target_services
# -------------------------------------------------------------------


class TestIdentifyBelowTargetServices:
    def test_with_below_target(self):
        eng = _engine(min_availability_pct=99.9)
        eng.record_availability("svc-a", availability_pct=99.5)
        eng.record_availability("svc-b", availability_pct=100.0)
        results = eng.identify_below_target_services()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_below_target_services() == []


# -------------------------------------------------------------------
# rank_by_availability
# -------------------------------------------------------------------


class TestRankByAvailability:
    def test_with_data(self):
        eng = _engine()
        eng.record_availability("svc-a", availability_pct=95.0)
        eng.record_availability("svc-b", availability_pct=99.9)
        results = eng.rank_by_availability()
        assert results[0]["avg_availability_pct"] == 99.9

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_availability() == []


# -------------------------------------------------------------------
# detect_availability_trends
# -------------------------------------------------------------------


class TestDetectAvailabilityTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(4):
            eng.record_availability("svc-trending")
        eng.record_availability("svc-stable")
        results = eng.detect_availability_trends()
        assert len(results) == 1
        assert results[0]["service"] == "svc-trending"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_availability_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_availability_pct=99.9)
        eng.record_availability(
            "svc-a",
            availability_pct=95.0,
            status=AvailabilityStatus.MAJOR_OUTAGE,
        )
        eng.record_availability("svc-b", availability_pct=100.0)
        eng.add_outage("svc-a", duration_minutes=60.0)
        report = eng.generate_report()
        assert isinstance(report, AvailabilityReport)
        assert report.total_records == 2
        assert report.total_outages == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable limits" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_availability("svc-a")
        eng.add_outage("svc-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._outages) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_outages"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_availability(
            "svc-a",
            status=(AvailabilityStatus.FULLY_AVAILABLE),
        )
        eng.record_availability(
            "svc-b",
            status=AvailabilityStatus.MAJOR_OUTAGE,
        )
        eng.add_outage("svc-b")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_outages"] == 1
        assert stats["unique_services"] == 2
