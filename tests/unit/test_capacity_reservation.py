"""Tests for shieldops.analytics.capacity_reservation -- CapacityReservationManager."""

from __future__ import annotations

import time

import pytest

from shieldops.analytics.capacity_reservation import (
    CapacityReservation,
    CapacityReservationManager,
    ReservationConflict,
    ReservationResource,
    ReservationStatus,
    ResourceType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manager(**kwargs) -> CapacityReservationManager:
    return CapacityReservationManager(**kwargs)


def _resource(
    rtype: ResourceType = ResourceType.CPU, amount: float = 4.0, unit: str = "cores"
) -> ReservationResource:
    return ReservationResource(resource_type=rtype, amount=amount, unit=unit)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_reservation_status_pending(self):
        assert ReservationStatus.PENDING == "pending"

    def test_reservation_status_approved(self):
        assert ReservationStatus.APPROVED == "approved"

    def test_reservation_status_active(self):
        assert ReservationStatus.ACTIVE == "active"

    def test_reservation_status_expired(self):
        assert ReservationStatus.EXPIRED == "expired"

    def test_reservation_status_cancelled(self):
        assert ReservationStatus.CANCELLED == "cancelled"

    def test_resource_type_cpu(self):
        assert ResourceType.CPU == "cpu"

    def test_resource_type_memory(self):
        assert ResourceType.MEMORY == "memory"

    def test_resource_type_storage(self):
        assert ResourceType.STORAGE == "storage"

    def test_resource_type_network(self):
        assert ResourceType.NETWORK == "network"

    def test_resource_type_instances(self):
        assert ResourceType.INSTANCES == "instances"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_reservation_resource_fields(self):
        r = ReservationResource(resource_type=ResourceType.CPU, amount=8.0)
        assert r.resource_type == ResourceType.CPU
        assert r.amount == 8.0
        assert r.unit == "cores"

    def test_capacity_reservation_defaults(self):
        now = time.time()
        res = CapacityReservation(name="test", start_time=now, end_time=now + 3600)
        assert res.id
        assert res.name == "test"
        assert res.team == ""
        assert res.resources == []
        assert res.status == ReservationStatus.PENDING
        assert res.reason == ""
        assert res.approved_by == ""
        assert res.metadata == {}

    def test_reservation_conflict_fields(self):
        c = ReservationConflict(
            reservation_id="r1",
            conflicting_id="r2",
            resource_type=ResourceType.MEMORY,
        )
        assert c.reservation_id == "r1"
        assert c.conflicting_id == "r2"
        assert c.resource_type == ResourceType.MEMORY
        assert c.message == ""


# ---------------------------------------------------------------------------
# Create reservation
# ---------------------------------------------------------------------------


class TestCreateReservation:
    def test_create_basic(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="gpu-pool",
            resources=[_resource()],
            start_time=now,
            end_time=now + 3600,
        )
        assert res.name == "gpu-pool"
        assert res.id
        assert res.status == ReservationStatus.PENDING

    def test_create_with_all_fields(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="ml-training",
            resources=[
                _resource(ResourceType.CPU, 16.0, "cores"),
                _resource(ResourceType.MEMORY, 64.0, "GB"),
            ],
            start_time=now,
            end_time=now + 7200,
            team="data-science",
            reason="Model training",
            metadata={"priority": "high"},
        )
        assert res.team == "data-science"
        assert res.reason == "Model training"
        assert len(res.resources) == 2
        assert res.metadata["priority"] == "high"

    def test_create_duration_exceeds_max(self):
        m = _manager(max_duration_days=1)
        now = time.time()
        with pytest.raises(ValueError, match="exceeds max"):
            m.create_reservation(
                name="too-long",
                resources=[_resource()],
                start_time=now,
                end_time=now + 5 * 86400,
            )

    def test_create_end_before_start(self):
        m = _manager()
        now = time.time()
        with pytest.raises(ValueError, match="end_time must be after"):
            m.create_reservation(
                name="invalid",
                resources=[_resource()],
                start_time=now,
                end_time=now - 100,
            )

    def test_create_max_limit(self):
        m = _manager(max_active=2)
        now = time.time()
        m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.create_reservation(
            name="r2", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        with pytest.raises(ValueError, match="Maximum active reservations"):
            m.create_reservation(
                name="r3", resources=[_resource()], start_time=now, end_time=now + 3600
            )

    def test_create_unique_ids(self):
        m = _manager()
        now = time.time()
        r1 = m.create_reservation(
            name="a", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        r2 = m.create_reservation(
            name="b", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        assert r1.id != r2.id

    def test_create_end_time_equals_start_time(self):
        m = _manager()
        now = time.time()
        with pytest.raises(ValueError, match="end_time must be after"):
            m.create_reservation(
                name="zero-dur",
                resources=[_resource()],
                start_time=now,
                end_time=now,
            )


# ---------------------------------------------------------------------------
# Approve reservation
# ---------------------------------------------------------------------------


class TestApproveReservation:
    def test_approve_success(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        result = m.approve_reservation(res.id, approved_by="admin")
        assert result is not None
        assert result.status == ReservationStatus.APPROVED
        assert result.approved_by == "admin"

    def test_approve_not_pending_fails(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.approve_reservation(res.id)
        result = m.approve_reservation(res.id)
        assert result is None

    def test_approve_not_found(self):
        m = _manager()
        assert m.approve_reservation("nonexistent") is None

    def test_approve_cancelled_fails(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.cancel_reservation(res.id)
        result = m.approve_reservation(res.id)
        assert result is None


# ---------------------------------------------------------------------------
# Activate reservation
# ---------------------------------------------------------------------------


class TestActivateReservation:
    def test_activate_success(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.approve_reservation(res.id)
        result = m.activate_reservation(res.id)
        assert result is not None
        assert result.status == ReservationStatus.ACTIVE

    def test_activate_not_approved_fails(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        result = m.activate_reservation(res.id)
        assert result is None

    def test_activate_not_found(self):
        m = _manager()
        assert m.activate_reservation("nonexistent") is None


# ---------------------------------------------------------------------------
# Cancel reservation
# ---------------------------------------------------------------------------


class TestCancelReservation:
    def test_cancel_success(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        result = m.cancel_reservation(res.id)
        assert result is not None
        assert result.status == ReservationStatus.CANCELLED

    def test_cancel_not_found(self):
        m = _manager()
        assert m.cancel_reservation("nonexistent") is None

    def test_cancel_approved_reservation(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.approve_reservation(res.id)
        result = m.cancel_reservation(res.id)
        assert result is not None
        assert result.status == ReservationStatus.CANCELLED


# ---------------------------------------------------------------------------
# Check conflicts
# ---------------------------------------------------------------------------


class TestCheckConflicts:
    def test_no_conflicts(self):
        m = _manager()
        now = time.time()
        conflicts = m.check_conflicts(
            start_time=now,
            end_time=now + 3600,
            resources=[_resource()],
        )
        assert conflicts == []

    def test_overlapping_time_and_resource_conflict(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="existing",
            resources=[_resource(ResourceType.CPU, 8.0)],
            start_time=now,
            end_time=now + 7200,
        )
        m.approve_reservation(res.id)
        conflicts = m.check_conflicts(
            start_time=now + 1800,
            end_time=now + 5400,
            resources=[_resource(ResourceType.CPU, 4.0)],
        )
        assert len(conflicts) == 1
        assert conflicts[0].resource_type == ResourceType.CPU
        assert conflicts[0].conflicting_id == res.id

    def test_no_conflict_different_resource_types(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="existing",
            resources=[_resource(ResourceType.CPU, 8.0)],
            start_time=now,
            end_time=now + 7200,
        )
        m.approve_reservation(res.id)
        conflicts = m.check_conflicts(
            start_time=now,
            end_time=now + 3600,
            resources=[_resource(ResourceType.MEMORY, 32.0, "GB")],
        )
        assert conflicts == []

    def test_no_conflict_non_overlapping_time(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="existing",
            resources=[_resource(ResourceType.CPU, 8.0)],
            start_time=now,
            end_time=now + 3600,
        )
        m.approve_reservation(res.id)
        conflicts = m.check_conflicts(
            start_time=now + 7200,
            end_time=now + 10800,
            resources=[_resource(ResourceType.CPU, 4.0)],
        )
        assert conflicts == []

    def test_pending_reservation_ignored_in_conflicts(self):
        m = _manager()
        now = time.time()
        m.create_reservation(
            name="pending",
            resources=[_resource(ResourceType.CPU, 8.0)],
            start_time=now,
            end_time=now + 7200,
        )
        conflicts = m.check_conflicts(
            start_time=now,
            end_time=now + 3600,
            resources=[_resource(ResourceType.CPU, 4.0)],
        )
        assert conflicts == []


# ---------------------------------------------------------------------------
# List reservations
# ---------------------------------------------------------------------------


class TestListReservations:
    def test_list_all(self):
        m = _manager()
        now = time.time()
        m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.create_reservation(
            name="r2", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        assert len(m.list_reservations()) == 2

    def test_list_filter_by_status(self):
        m = _manager()
        now = time.time()
        r1 = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.create_reservation(
            name="r2", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.approve_reservation(r1.id)
        approved = m.list_reservations(status=ReservationStatus.APPROVED)
        assert len(approved) == 1
        assert approved[0].name == "r1"

    def test_list_empty(self):
        m = _manager()
        assert m.list_reservations() == []


# ---------------------------------------------------------------------------
# Get reservation
# ---------------------------------------------------------------------------


class TestGetReservation:
    def test_get_found(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        result = m.get_reservation(res.id)
        assert result is not None
        assert result.name == "r1"

    def test_get_not_found(self):
        m = _manager()
        assert m.get_reservation("nonexistent") is None


# ---------------------------------------------------------------------------
# Get utilization
# ---------------------------------------------------------------------------


class TestGetUtilization:
    def test_utilization_empty(self):
        m = _manager()
        u = m.get_utilization()
        assert u["active_resources"] == {}
        assert u["active_reservations"] == 0

    def test_utilization_with_active_reservations(self):
        m = _manager()
        now = time.time()
        res = m.create_reservation(
            name="r1",
            resources=[
                _resource(ResourceType.CPU, 8.0, "cores"),
                _resource(ResourceType.MEMORY, 32.0, "GB"),
            ],
            start_time=now,
            end_time=now + 3600,
        )
        m.approve_reservation(res.id)
        m.activate_reservation(res.id)
        u = m.get_utilization()
        assert u["active_reservations"] == 1
        assert ResourceType.CPU in u["active_resources"]
        assert u["active_resources"][ResourceType.CPU]["total_amount"] == 8.0
        assert u["active_resources"][ResourceType.MEMORY]["total_amount"] == 32.0

    def test_utilization_ignores_pending(self):
        m = _manager()
        now = time.time()
        m.create_reservation(
            name="r1",
            resources=[_resource(ResourceType.CPU, 8.0)],
            start_time=now,
            end_time=now + 3600,
        )
        u = m.get_utilization()
        assert u["active_reservations"] == 0
        assert u["active_resources"] == {}

    def test_utilization_sums_multiple_active(self):
        m = _manager()
        now = time.time()
        r1 = m.create_reservation(
            name="r1",
            resources=[_resource(ResourceType.CPU, 4.0)],
            start_time=now,
            end_time=now + 3600,
        )
        m.approve_reservation(r1.id)
        m.activate_reservation(r1.id)
        r2 = m.create_reservation(
            name="r2",
            resources=[_resource(ResourceType.CPU, 6.0)],
            start_time=now,
            end_time=now + 3600,
        )
        m.approve_reservation(r2.id)
        m.activate_reservation(r2.id)
        u = m.get_utilization()
        assert u["active_reservations"] == 2
        assert u["active_resources"][ResourceType.CPU]["total_amount"] == 10.0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        m = _manager()
        s = m.get_stats()
        assert s["total_reservations"] == 0
        assert s["pending"] == 0
        assert s["approved"] == 0
        assert s["active"] == 0
        assert s["expired"] == 0
        assert s["cancelled"] == 0

    def test_stats_with_data(self):
        m = _manager()
        now = time.time()
        r1 = m.create_reservation(
            name="r1", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        r2 = m.create_reservation(
            name="r2", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.create_reservation(
            name="r3", resources=[_resource()], start_time=now, end_time=now + 3600
        )
        m.approve_reservation(r1.id)
        m.activate_reservation(r1.id)
        m.cancel_reservation(r2.id)
        s = m.get_stats()
        assert s["total_reservations"] == 3
        assert s["active"] == 1
        assert s["cancelled"] == 1
        assert s["pending"] == 1
