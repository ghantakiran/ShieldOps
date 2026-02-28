"""Tests for shieldops.operations.failover_coordinator."""

from __future__ import annotations

from shieldops.operations.failover_coordinator import (
    FailoverCoordinatorReport,
    FailoverPlan,
    FailoverRecord,
    FailoverRegion,
    FailoverStatus,
    FailoverType,
    MultiRegionFailoverCoordinator,
)


def _engine(**kw) -> MultiRegionFailoverCoordinator:
    return MultiRegionFailoverCoordinator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FailoverType (5)
    def test_type_dns_switchover(self):
        assert FailoverType.DNS_SWITCHOVER == "dns_switchover"

    def test_type_traffic_drain(self):
        assert FailoverType.TRAFFIC_DRAIN == "traffic_drain"

    def test_type_data_replication(self):
        assert FailoverType.DATA_REPLICATION == "data_replication"

    def test_type_cold_standby(self):
        assert FailoverType.COLD_STANDBY == "cold_standby"

    def test_type_active_active(self):
        assert FailoverType.ACTIVE_ACTIVE == "active_active"

    # FailoverStatus (5)
    def test_status_initiated(self):
        assert FailoverStatus.INITIATED == "initiated"

    def test_status_in_progress(self):
        assert FailoverStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert FailoverStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert FailoverStatus.FAILED == "failed"

    def test_status_rolled_back(self):
        assert FailoverStatus.ROLLED_BACK == "rolled_back"

    # FailoverRegion (5)
    def test_region_us_east(self):
        assert FailoverRegion.US_EAST == "us_east"

    def test_region_us_west(self):
        assert FailoverRegion.US_WEST == "us_west"

    def test_region_eu_west(self):
        assert FailoverRegion.EU_WEST == "eu_west"

    def test_region_ap_southeast(self):
        assert FailoverRegion.AP_SOUTHEAST == "ap_southeast"

    def test_region_ap_northeast(self):
        assert FailoverRegion.AP_NORTHEAST == "ap_northeast"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_failover_record_defaults(self):
        r = FailoverRecord()
        assert r.id
        assert r.service_name == ""
        assert r.failover_type == FailoverType.DNS_SWITCHOVER
        assert r.status == FailoverStatus.INITIATED
        assert r.region == FailoverRegion.US_EAST
        assert r.duration_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_failover_plan_defaults(self):
        r = FailoverPlan()
        assert r.id
        assert r.plan_name == ""
        assert r.failover_type == FailoverType.DNS_SWITCHOVER
        assert r.region == FailoverRegion.US_EAST
        assert r.rto_seconds == 300
        assert r.rpo_seconds == 60.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = FailoverCoordinatorReport()
        assert r.total_failovers == 0
        assert r.total_plans == 0
        assert r.success_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.failed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_failover
# -------------------------------------------------------------------


class TestRecordFailover:
    def test_basic(self):
        eng = _engine()
        r = eng.record_failover(
            "svc-a",
            failover_type=(FailoverType.DNS_SWITCHOVER),
            status=FailoverStatus.COMPLETED,
        )
        assert r.service_name == "svc-a"
        assert r.failover_type == FailoverType.DNS_SWITCHOVER

    def test_with_region(self):
        eng = _engine()
        r = eng.record_failover(
            "svc-b",
            region=FailoverRegion.EU_WEST,
        )
        assert r.region == FailoverRegion.EU_WEST

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_failover(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_failover
# -------------------------------------------------------------------


class TestGetFailover:
    def test_found(self):
        eng = _engine()
        r = eng.record_failover("svc-a")
        assert eng.get_failover(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_failover("nonexistent") is None


# -------------------------------------------------------------------
# list_failovers
# -------------------------------------------------------------------


class TestListFailovers:
    def test_list_all(self):
        eng = _engine()
        eng.record_failover("svc-a")
        eng.record_failover("svc-b")
        assert len(eng.list_failovers()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_failover("svc-a")
        eng.record_failover("svc-b")
        results = eng.list_failovers(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_failover(
            "svc-a",
            failover_type=(FailoverType.TRAFFIC_DRAIN),
        )
        eng.record_failover(
            "svc-b",
            failover_type=(FailoverType.DNS_SWITCHOVER),
        )
        results = eng.list_failovers(
            failover_type=(FailoverType.TRAFFIC_DRAIN),
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_plan
# -------------------------------------------------------------------


class TestAddPlan:
    def test_basic(self):
        eng = _engine()
        p = eng.add_plan(
            "dns-failover-plan",
            failover_type=(FailoverType.DNS_SWITCHOVER),
            region=FailoverRegion.US_WEST,
            rto_seconds=120,
            rpo_seconds=30.0,
        )
        assert p.plan_name == "dns-failover-plan"
        assert p.rto_seconds == 120

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_plan(f"plan-{i}")
        assert len(eng._plans) == 2


# -------------------------------------------------------------------
# analyze_failover_readiness
# -------------------------------------------------------------------


class TestAnalyzeFailoverReadiness:
    def test_with_data(self):
        eng = _engine()
        eng.record_failover(
            "svc-a",
            status=FailoverStatus.COMPLETED,
            duration_seconds=100.0,
        )
        eng.record_failover(
            "svc-a",
            status=FailoverStatus.FAILED,
            duration_seconds=500.0,
        )
        result = eng.analyze_failover_readiness("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["failover_count"] == 2
        assert result["success_rate"] == 50.0
        assert result["avg_duration"] == 300.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_failover_readiness("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_failed_failovers
# -------------------------------------------------------------------


class TestIdentifyFailedFailovers:
    def test_with_failures(self):
        eng = _engine()
        eng.record_failover(
            "svc-a",
            status=FailoverStatus.FAILED,
        )
        eng.record_failover(
            "svc-a",
            status=FailoverStatus.FAILED,
        )
        eng.record_failover(
            "svc-b",
            status=FailoverStatus.COMPLETED,
        )
        results = eng.identify_failed_failovers()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_failovers() == []


# -------------------------------------------------------------------
# rank_by_failover_speed
# -------------------------------------------------------------------


class TestRankByFailoverSpeed:
    def test_with_data(self):
        eng = _engine()
        eng.record_failover("svc-a", duration_seconds=100.0)
        eng.record_failover("svc-a", duration_seconds=200.0)
        eng.record_failover("svc-b", duration_seconds=50.0)
        results = eng.rank_by_failover_speed()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_duration"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_failover_speed() == []


# -------------------------------------------------------------------
# detect_failover_risks
# -------------------------------------------------------------------


class TestDetectFailoverRisks:
    def test_with_risks(self):
        eng = _engine()
        for _ in range(5):
            eng.record_failover(
                "svc-a",
                status=FailoverStatus.FAILED,
            )
        eng.record_failover(
            "svc-b",
            status=FailoverStatus.COMPLETED,
        )
        results = eng.detect_failover_risks()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["risk_detected"] is True

    def test_no_risks(self):
        eng = _engine()
        eng.record_failover(
            "svc-a",
            status=FailoverStatus.FAILED,
        )
        assert eng.detect_failover_risks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_failover(
            "svc-a",
            status=FailoverStatus.COMPLETED,
        )
        eng.record_failover(
            "svc-b",
            status=FailoverStatus.FAILED,
        )
        eng.record_failover(
            "svc-b",
            status=FailoverStatus.FAILED,
        )
        eng.add_plan("plan-1")
        report = eng.generate_report()
        assert report.total_failovers == 3
        assert report.total_plans == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_failovers == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_failover("svc-a")
        eng.add_plan("plan-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._plans) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_failovers"] == 0
        assert stats["total_plans"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_failover(
            "svc-a",
            failover_type=(FailoverType.DNS_SWITCHOVER),
        )
        eng.record_failover(
            "svc-b",
            failover_type=(FailoverType.TRAFFIC_DRAIN),
        )
        eng.add_plan("p1")
        stats = eng.get_stats()
        assert stats["total_failovers"] == 2
        assert stats["total_plans"] == 1
        assert stats["unique_services"] == 2
