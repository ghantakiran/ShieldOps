"""Tests for shieldops.billing.capacity_reservation_planner — CapacityReservationPlanner."""

from __future__ import annotations

from shieldops.billing.capacity_reservation_planner import (
    CapacityReservationPlanner,
    CapacityReservationReport,
    ReservationPlan,
    ReservationRecord,
    ReservationTerm,
    ReservationType,
    UtilizationLevel,
)


def _engine(**kw) -> CapacityReservationPlanner:
    return CapacityReservationPlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_reservation_type_on_demand(self):
        assert ReservationType.ON_DEMAND == "on_demand"

    def test_reservation_type_reserved(self):
        assert ReservationType.RESERVED == "reserved"

    def test_reservation_type_spot(self):
        assert ReservationType.SPOT == "spot"

    def test_reservation_type_savings_plan(self):
        assert ReservationType.SAVINGS_PLAN == "savings_plan"

    def test_reservation_type_committed(self):
        assert ReservationType.COMMITTED == "committed"

    def test_utilization_level_over_provisioned(self):
        assert UtilizationLevel.OVER_PROVISIONED == "over_provisioned"

    def test_utilization_level_optimal(self):
        assert UtilizationLevel.OPTIMAL == "optimal"

    def test_utilization_level_under_utilized(self):
        assert UtilizationLevel.UNDER_UTILIZED == "under_utilized"

    def test_utilization_level_idle(self):
        assert UtilizationLevel.IDLE == "idle"

    def test_utilization_level_unknown(self):
        assert UtilizationLevel.UNKNOWN == "unknown"

    def test_reservation_term_monthly(self):
        assert ReservationTerm.MONTHLY == "monthly"

    def test_reservation_term_quarterly(self):
        assert ReservationTerm.QUARTERLY == "quarterly"

    def test_reservation_term_annual(self):
        assert ReservationTerm.ANNUAL == "annual"

    def test_reservation_term_three_year(self):
        assert ReservationTerm.THREE_YEAR == "three_year"

    def test_reservation_term_custom(self):
        assert ReservationTerm.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_reservation_record_defaults(self):
        r = ReservationRecord()
        assert r.id
        assert r.reservation_id == ""
        assert r.reservation_type == ReservationType.ON_DEMAND
        assert r.utilization_level == UtilizationLevel.UNKNOWN
        assert r.reservation_term == ReservationTerm.ANNUAL
        assert r.utilization_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_reservation_plan_defaults(self):
        p = ReservationPlan()
        assert p.id
        assert p.reservation_id == ""
        assert p.reservation_type == ReservationType.ON_DEMAND
        assert p.plan_score == 0.0
        assert p.threshold == 0.0
        assert p.breached is False
        assert p.description == ""
        assert p.created_at > 0

    def test_capacity_reservation_report_defaults(self):
        r = CapacityReservationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_plans == 0
        assert r.under_utilized_count == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_type == {}
        assert r.by_level == {}
        assert r.by_term == {}
        assert r.top_under_utilized == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_reservation
# ---------------------------------------------------------------------------


class TestRecordReservation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.RESERVED,
            utilization_level=UtilizationLevel.OPTIMAL,
            reservation_term=ReservationTerm.ANNUAL,
            utilization_pct=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.reservation_id == "RES-001"
        assert r.reservation_type == ReservationType.RESERVED
        assert r.utilization_level == UtilizationLevel.OPTIMAL
        assert r.reservation_term == ReservationTerm.ANNUAL
        assert r.utilization_pct == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_reservation(reservation_id=f"RES-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_reservation
# ---------------------------------------------------------------------------


class TestGetReservation:
    def test_found(self):
        eng = _engine()
        r = eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.SPOT,
        )
        result = eng.get_reservation(r.id)
        assert result is not None
        assert result.reservation_type == ReservationType.SPOT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_reservation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_reservations
# ---------------------------------------------------------------------------


class TestListReservations:
    def test_list_all(self):
        eng = _engine()
        eng.record_reservation(reservation_id="RES-001")
        eng.record_reservation(reservation_id="RES-002")
        assert len(eng.list_reservations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.RESERVED,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            reservation_type=ReservationType.SPOT,
        )
        results = eng.list_reservations(res_type=ReservationType.RESERVED)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            utilization_level=UtilizationLevel.IDLE,
        )
        results = eng.list_reservations(level=UtilizationLevel.OPTIMAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_reservation(reservation_id="RES-001", service="api-gateway")
        eng.record_reservation(reservation_id="RES-002", service="auth-svc")
        results = eng.list_reservations(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_reservation(reservation_id="RES-001", team="sre")
        eng.record_reservation(reservation_id="RES-002", team="platform")
        results = eng.list_reservations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_reservation(reservation_id=f"RES-{i}")
        assert len(eng.list_reservations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_plan
# ---------------------------------------------------------------------------


class TestAddPlan:
    def test_basic(self):
        eng = _engine()
        p = eng.add_plan(
            reservation_id="RES-001",
            reservation_type=ReservationType.SAVINGS_PLAN,
            plan_score=85.0,
            threshold=90.0,
            breached=True,
            description="Under-utilized reservation detected",
        )
        assert p.reservation_id == "RES-001"
        assert p.reservation_type == ReservationType.SAVINGS_PLAN
        assert p.plan_score == 85.0
        assert p.threshold == 90.0
        assert p.breached is True
        assert p.description == "Under-utilized reservation detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_plan(reservation_id=f"RES-{i}")
        assert len(eng._plans) == 2


# ---------------------------------------------------------------------------
# analyze_reservation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeReservationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.RESERVED,
            utilization_pct=10.0,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            reservation_type=ReservationType.RESERVED,
            utilization_pct=20.0,
        )
        result = eng.analyze_reservation_distribution()
        assert "reserved" in result
        assert result["reserved"]["count"] == 2
        assert result["reserved"]["avg_utilization_pct"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_reservation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_under_utilized_reservations
# ---------------------------------------------------------------------------


class TestIdentifyUnderUtilizedReservations:
    def test_detects(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            utilization_level=UtilizationLevel.UNDER_UTILIZED,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        results = eng.identify_under_utilized_reservations()
        assert len(results) == 1
        assert results[0]["reservation_id"] == "RES-001"

    def test_detects_idle(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            utilization_level=UtilizationLevel.IDLE,
        )
        results = eng.identify_under_utilized_reservations()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_under_utilized_reservations() == []


# ---------------------------------------------------------------------------
# rank_by_utilization
# ---------------------------------------------------------------------------


class TestRankByUtilization:
    def test_ranked(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            service="api-gateway",
            utilization_pct=120.0,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            service="auth-svc",
            utilization_pct=30.0,
        )
        eng.record_reservation(
            reservation_id="RES-003",
            service="api-gateway",
            utilization_pct=80.0,
        )
        results = eng.rank_by_utilization()
        assert len(results) == 2
        # ascending: auth-svc (30.0) first, api-gateway (100.0) second
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_utilization_pct"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# ---------------------------------------------------------------------------
# detect_reservation_trends
# ---------------------------------------------------------------------------


class TestDetectReservationTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_plan(reservation_id="RES-1", plan_score=val)
        result = eng.detect_reservation_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_plan(reservation_id="RES-1", plan_score=val)
        result = eng.detect_reservation_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_shrinking(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_plan(reservation_id="RES-1", plan_score=val)
        result = eng.detect_reservation_trends()
        assert result["trend"] == "shrinking"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_reservation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.RESERVED,
            utilization_level=UtilizationLevel.UNDER_UTILIZED,
            reservation_term=ReservationTerm.ANNUAL,
            utilization_pct=5.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, CapacityReservationReport)
        assert report.total_records == 1
        assert report.under_utilized_count == 1
        assert len(report.top_under_utilized) >= 1
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
        eng.record_reservation(reservation_id="RES-001")
        eng.add_plan(reservation_id="RES-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._plans) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_plans"] == 0
        assert stats["reservation_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.RESERVED,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "reserved" in stats["reservation_type_distribution"]
