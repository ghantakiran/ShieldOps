"""Tests for shieldops.operations.reservation_optimizer — ReservationOptimizer."""

from __future__ import annotations

from shieldops.operations.reservation_optimizer import (
    ReservationAction,
    ReservationOptimizer,
    ReservationOptimizerReport,
    ReservationRecord,
    ReservationType,
    UtilizationLevel,
    UtilizationMetric,
)


def _engine(**kw) -> ReservationOptimizer:
    return ReservationOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_reservation_type_compute(self):
        assert ReservationType.COMPUTE == "compute"

    def test_reservation_type_storage(self):
        assert ReservationType.STORAGE == "storage"

    def test_reservation_type_database(self):
        assert ReservationType.DATABASE == "database"

    def test_reservation_type_network(self):
        assert ReservationType.NETWORK == "network"

    def test_reservation_type_specialized(self):
        assert ReservationType.SPECIALIZED == "specialized"

    def test_utilization_level_optimal(self):
        assert UtilizationLevel.OPTIMAL == "optimal"

    def test_utilization_level_adequate(self):
        assert UtilizationLevel.ADEQUATE == "adequate"

    def test_utilization_level_underutilized(self):
        assert UtilizationLevel.UNDERUTILIZED == "underutilized"

    def test_utilization_level_wasteful(self):
        assert UtilizationLevel.WASTEFUL == "wasteful"

    def test_utilization_level_unused(self):
        assert UtilizationLevel.UNUSED == "unused"

    def test_action_keep(self):
        assert ReservationAction.KEEP == "keep"

    def test_action_modify(self):
        assert ReservationAction.MODIFY == "modify"

    def test_action_exchange(self):
        assert ReservationAction.EXCHANGE == "exchange"

    def test_action_sell(self):
        assert ReservationAction.SELL == "sell"

    def test_action_terminate(self):
        assert ReservationAction.TERMINATE == "terminate"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_reservation_record_defaults(self):
        r = ReservationRecord()
        assert r.id
        assert r.reservation_id == ""
        assert r.reservation_type == ReservationType.COMPUTE
        assert r.utilization_level == UtilizationLevel.OPTIMAL
        assert r.reservation_action == ReservationAction.KEEP
        assert r.utilization_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_utilization_metric_defaults(self):
        m = UtilizationMetric()
        assert m.id
        assert m.reservation_id == ""
        assert m.reservation_type == ReservationType.COMPUTE
        assert m.metric_value == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_reservation_optimizer_report_defaults(self):
        r = ReservationOptimizerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.underutilized_count == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_reservation_type == {}
        assert r.by_utilization == {}
        assert r.by_action == {}
        assert r.top_underutilized == []
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
            reservation_type=ReservationType.STORAGE,
            utilization_level=UtilizationLevel.ADEQUATE,
            reservation_action=ReservationAction.KEEP,
            utilization_pct=75.0,
            service="api-gateway",
            team="sre",
        )
        assert r.reservation_id == "RES-001"
        assert r.reservation_type == ReservationType.STORAGE
        assert r.utilization_level == UtilizationLevel.ADEQUATE
        assert r.reservation_action == ReservationAction.KEEP
        assert r.utilization_pct == 75.0
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
            utilization_level=UtilizationLevel.WASTEFUL,
        )
        result = eng.get_reservation(r.id)
        assert result is not None
        assert result.utilization_level == UtilizationLevel.WASTEFUL

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

    def test_filter_by_reservation_type(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.STORAGE,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            reservation_type=ReservationType.COMPUTE,
        )
        results = eng.list_reservations(reservation_type=ReservationType.STORAGE)
        assert len(results) == 1

    def test_filter_by_utilization(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            utilization_level=UtilizationLevel.WASTEFUL,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        results = eng.list_reservations(utilization=UtilizationLevel.WASTEFUL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_reservation(reservation_id="RES-001", service="api")
        eng.record_reservation(reservation_id="RES-002", service="web")
        results = eng.list_reservations(service="api")
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
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            reservation_id="RES-001",
            reservation_type=ReservationType.DATABASE,
            metric_value=55.0,
            threshold=70.0,
            breached=True,
            description="Utilization below threshold",
        )
        assert m.reservation_id == "RES-001"
        assert m.reservation_type == ReservationType.DATABASE
        assert m.metric_value == 55.0
        assert m.threshold == 70.0
        assert m.breached is True
        assert m.description == "Utilization below threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(reservation_id=f"RES-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_utilization
# ---------------------------------------------------------------------------


class TestAnalyzeUtilization:
    def test_with_data(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.COMPUTE,
            utilization_pct=70.0,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            reservation_type=ReservationType.COMPUTE,
            utilization_pct=90.0,
        )
        result = eng.analyze_utilization()
        assert "compute" in result
        assert result["compute"]["count"] == 2
        assert result["compute"]["avg_utilization_pct"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_utilization() == {}


# ---------------------------------------------------------------------------
# identify_underutilized_reservations
# ---------------------------------------------------------------------------


class TestIdentifyUnderutilizedReservations:
    def test_detects_underutilized(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            utilization_level=UtilizationLevel.WASTEFUL,
        )
        eng.record_reservation(
            reservation_id="RES-002",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        results = eng.identify_underutilized_reservations()
        assert len(results) == 1
        assert results[0]["reservation_id"] == "RES-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_underutilized_reservations() == []


# ---------------------------------------------------------------------------
# rank_by_utilization
# ---------------------------------------------------------------------------


class TestRankByUtilization:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_reservation(reservation_id="RES-001", service="api", utilization_pct=90.0)
        eng.record_reservation(reservation_id="RES-002", service="api", utilization_pct=80.0)
        eng.record_reservation(reservation_id="RES-003", service="web", utilization_pct=50.0)
        results = eng.rank_by_utilization()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_utilization_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# ---------------------------------------------------------------------------
# detect_utilization_trends
# ---------------------------------------------------------------------------


class TestDetectUtilizationTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_metric(reservation_id="RES-001", metric_value=val)
        result = eng.detect_utilization_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_metric(reservation_id="RES-001", metric_value=val)
        result = eng.detect_utilization_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_utilization_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.COMPUTE,
            utilization_level=UtilizationLevel.WASTEFUL,
            utilization_pct=30.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ReservationOptimizerReport)
        assert report.total_records == 1
        assert report.underutilized_count == 1
        assert report.avg_utilization_pct == 30.0
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
        eng.add_metric(reservation_id="RES-001")
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
        assert stats["reservation_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_reservation(
            reservation_id="RES-001",
            reservation_type=ReservationType.STORAGE,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_reservations"] == 1
        assert "storage" in stats["reservation_type_distribution"]
