"""Tests for shieldops.config.deployment_freeze -- DeploymentFreezeManager."""

from __future__ import annotations

import time

import pytest

from shieldops.config.deployment_freeze import (
    DeploymentFreezeManager,
    FreezeCheckResult,
    FreezeException,
    FreezeScope,
    FreezeStatus,
    FreezeWindow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manager(**kwargs) -> DeploymentFreezeManager:
    return DeploymentFreezeManager(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_freeze_status_active(self):
        assert FreezeStatus.ACTIVE == "active"

    def test_freeze_status_scheduled(self):
        assert FreezeStatus.SCHEDULED == "scheduled"

    def test_freeze_status_expired(self):
        assert FreezeStatus.EXPIRED == "expired"

    def test_freeze_status_cancelled(self):
        assert FreezeStatus.CANCELLED == "cancelled"

    def test_freeze_scope_all(self):
        assert FreezeScope.ALL == "all"

    def test_freeze_scope_production(self):
        assert FreezeScope.PRODUCTION == "production"

    def test_freeze_scope_staging(self):
        assert FreezeScope.STAGING == "staging"

    def test_freeze_scope_custom(self):
        assert FreezeScope.CUSTOM == "custom"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_freeze_window_defaults(self):
        now = time.time()
        w = FreezeWindow(name="holiday", start_time=now, end_time=now + 3600)
        assert w.id
        assert w.status == FreezeStatus.SCHEDULED
        assert w.scope == FreezeScope.ALL
        assert w.reason == ""
        assert w.created_by == ""
        assert w.environments == []
        assert w.metadata == {}
        assert w.created_at > 0

    def test_freeze_exception_defaults(self):
        e = FreezeException(freeze_id="f1", service="api", reason="critical fix")
        assert e.id
        assert e.approved_by == ""
        assert e.created_at > 0

    def test_freeze_check_result_defaults(self):
        r = FreezeCheckResult(frozen=False)
        assert r.reason == ""
        assert r.freeze_id == ""
        assert r.exception_id == ""


# ---------------------------------------------------------------------------
# Create freeze
# ---------------------------------------------------------------------------


class TestCreateFreeze:
    def test_create_basic(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="holiday", start_time=now, end_time=now + 3600)
        assert f.name == "holiday"
        assert f.id

    def test_create_with_all_fields(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(
            name="audit",
            start_time=now,
            end_time=now + 7200,
            scope=FreezeScope.PRODUCTION,
            environments=["us-east-1"],
            reason="SOC2 audit",
            created_by="admin",
            metadata={"ticket": "SEC-123"},
        )
        assert f.scope == FreezeScope.PRODUCTION
        assert f.environments == ["us-east-1"]
        assert f.reason == "SOC2 audit"
        assert f.created_by == "admin"
        assert f.metadata["ticket"] == "SEC-123"

    def test_create_duration_exceeds_max(self):
        m = _manager(max_duration_days=1)
        now = time.time()
        with pytest.raises(ValueError, match="exceeds max"):
            m.create_freeze(name="long", start_time=now, end_time=now + 3 * 86400)

    def test_create_end_before_start(self):
        m = _manager()
        now = time.time()
        with pytest.raises(ValueError, match="end_time must be after"):
            m.create_freeze(name="bad", start_time=now, end_time=now - 100)

    def test_create_end_equals_start(self):
        m = _manager()
        now = time.time()
        with pytest.raises(ValueError, match="end_time must be after"):
            m.create_freeze(name="zero", start_time=now, end_time=now)

    def test_create_max_windows_limit(self):
        m = _manager(max_windows=2)
        now = time.time()
        m.create_freeze(name="f1", start_time=now, end_time=now + 3600)
        m.create_freeze(name="f2", start_time=now, end_time=now + 3600)
        with pytest.raises(ValueError, match="Maximum freeze windows limit"):
            m.create_freeze(name="f3", start_time=now, end_time=now + 3600)


# ---------------------------------------------------------------------------
# Cancel freeze
# ---------------------------------------------------------------------------


class TestCancelFreeze:
    def test_cancel_success(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="temp", start_time=now, end_time=now + 3600)
        result = m.cancel_freeze(f.id)
        assert result is not None
        assert result.status == FreezeStatus.CANCELLED

    def test_cancel_not_found(self):
        m = _manager()
        assert m.cancel_freeze("nonexistent") is None


# ---------------------------------------------------------------------------
# Check frozen
# ---------------------------------------------------------------------------


class TestCheckFrozen:
    def test_not_frozen_no_freezes(self):
        m = _manager()
        result = m.check_frozen()
        assert result.frozen is False

    def test_frozen_during_active_window(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="deploy-freeze", start_time=now - 100, end_time=now + 3600)
        result = m.check_frozen()
        assert result.frozen is True
        assert "deploy-freeze" in result.reason

    def test_not_frozen_outside_window(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="future", start_time=now + 7200, end_time=now + 10800)
        result = m.check_frozen()
        assert result.frozen is False

    def test_not_frozen_with_exception(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="deploy-freeze", start_time=now - 100, end_time=now + 3600)
        m.add_exception(f.id, service="api", reason="critical hotfix")
        result = m.check_frozen(service="api")
        assert result.frozen is False
        assert result.exception_id
        assert "critical hotfix" in result.reason

    def test_frozen_different_service_no_exception(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="deploy-freeze", start_time=now - 100, end_time=now + 3600)
        m.add_exception(f.id, service="api", reason="critical hotfix")
        result = m.check_frozen(service="web")
        assert result.frozen is True

    def test_scope_production_matches_production(self):
        m = _manager()
        now = time.time()
        m.create_freeze(
            name="prod-freeze",
            start_time=now - 100,
            end_time=now + 3600,
            scope=FreezeScope.PRODUCTION,
        )
        result = m.check_frozen(environment="production")
        assert result.frozen is True

    def test_scope_production_does_not_match_staging(self):
        m = _manager()
        now = time.time()
        m.create_freeze(
            name="prod-freeze",
            start_time=now - 100,
            end_time=now + 3600,
            scope=FreezeScope.PRODUCTION,
        )
        result = m.check_frozen(environment="staging")
        assert result.frozen is False

    def test_scope_staging_matches_staging(self):
        m = _manager()
        now = time.time()
        m.create_freeze(
            name="staging-freeze",
            start_time=now - 100,
            end_time=now + 3600,
            scope=FreezeScope.STAGING,
        )
        result = m.check_frozen(environment="staging")
        assert result.frozen is True

    def test_scope_all_matches_any_environment(self):
        m = _manager()
        now = time.time()
        m.create_freeze(
            name="all-freeze",
            start_time=now - 100,
            end_time=now + 3600,
            scope=FreezeScope.ALL,
        )
        result = m.check_frozen(environment="staging")
        assert result.frozen is True

    def test_scope_custom_matches_listed_environment(self):
        m = _manager()
        now = time.time()
        m.create_freeze(
            name="custom-freeze",
            start_time=now - 100,
            end_time=now + 3600,
            scope=FreezeScope.CUSTOM,
            environments=["us-east-1", "eu-west-1"],
        )
        result = m.check_frozen(environment="us-east-1")
        assert result.frozen is True

    def test_scope_custom_does_not_match_unlisted_environment(self):
        m = _manager()
        now = time.time()
        m.create_freeze(
            name="custom-freeze",
            start_time=now - 100,
            end_time=now + 3600,
            scope=FreezeScope.CUSTOM,
            environments=["us-east-1"],
        )
        result = m.check_frozen(environment="ap-south-1")
        assert result.frozen is False

    def test_cancelled_freeze_not_frozen(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="temp", start_time=now - 100, end_time=now + 3600)
        m.cancel_freeze(f.id)
        result = m.check_frozen()
        assert result.frozen is False

    def test_expired_freeze_not_frozen(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="past", start_time=now - 7200, end_time=now - 3600)
        result = m.check_frozen()
        assert result.frozen is False

    def test_check_frozen_returns_freeze_id(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="deploy-freeze", start_time=now - 100, end_time=now + 3600)
        result = m.check_frozen()
        assert result.freeze_id == f.id


# ---------------------------------------------------------------------------
# Add exception
# ---------------------------------------------------------------------------


class TestAddException:
    def test_add_success(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="freeze", start_time=now, end_time=now + 3600)
        exc = m.add_exception(f.id, service="api", reason="hotfix", approved_by="manager")
        assert exc.service == "api"
        assert exc.reason == "hotfix"
        assert exc.approved_by == "manager"

    def test_add_freeze_not_found(self):
        m = _manager()
        with pytest.raises(ValueError, match="Freeze window not found"):
            m.add_exception("nonexistent", service="api", reason="test")


# ---------------------------------------------------------------------------
# List freezes
# ---------------------------------------------------------------------------


class TestListFreezes:
    def test_list_all(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="f1", start_time=now, end_time=now + 3600)
        m.create_freeze(name="f2", start_time=now, end_time=now + 3600)
        assert len(m.list_freezes()) == 2

    def test_filter_by_status(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="f1", start_time=now, end_time=now + 3600)
        m.create_freeze(name="f2", start_time=now, end_time=now + 3600)
        m.cancel_freeze(f.id)
        cancelled = m.list_freezes(status=FreezeStatus.CANCELLED)
        assert len(cancelled) == 1
        assert cancelled[0].name == "f1"

    def test_auto_expire_on_list(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="past", start_time=now - 7200, end_time=now - 3600)
        freezes = m.list_freezes(status=FreezeStatus.EXPIRED)
        assert len(freezes) == 1
        assert freezes[0].status == FreezeStatus.EXPIRED

    def test_list_empty(self):
        m = _manager()
        assert len(m.list_freezes()) == 0


# ---------------------------------------------------------------------------
# Get freeze
# ---------------------------------------------------------------------------


class TestGetFreeze:
    def test_found(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="test", start_time=now, end_time=now + 3600)
        result = m.get_freeze(f.id)
        assert result is not None
        assert result.name == "test"

    def test_not_found(self):
        m = _manager()
        assert m.get_freeze("nonexistent") is None


# ---------------------------------------------------------------------------
# Get active freezes
# ---------------------------------------------------------------------------


class TestGetActiveFreezes:
    def test_active_only(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="active", start_time=now - 100, end_time=now + 3600)
        m.create_freeze(name="future", start_time=now + 7200, end_time=now + 10800)
        active = m.get_active_freezes()
        assert len(active) == 1
        assert active[0].name == "active"

    def test_no_active_all_future(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="future", start_time=now + 7200, end_time=now + 10800)
        assert len(m.get_active_freezes()) == 0

    def test_expired_not_returned(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="past", start_time=now - 7200, end_time=now - 3600)
        assert len(m.get_active_freezes()) == 0

    def test_cancelled_not_returned(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="cancelled", start_time=now - 100, end_time=now + 3600)
        m.cancel_freeze(f.id)
        assert len(m.get_active_freezes()) == 0

    def test_active_freeze_status_updated(self):
        m = _manager()
        now = time.time()
        m.create_freeze(name="active", start_time=now - 100, end_time=now + 3600)
        active = m.get_active_freezes()
        assert active[0].status == FreezeStatus.ACTIVE


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        m = _manager()
        s = m.get_stats()
        assert s["total_freezes"] == 0
        assert s["active_freezes"] == 0
        assert s["scheduled_freezes"] == 0
        assert s["expired_freezes"] == 0
        assert s["cancelled_freezes"] == 0
        assert s["total_exceptions"] == 0

    def test_stats_with_data(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="active", start_time=now - 100, end_time=now + 3600)
        m.create_freeze(name="future", start_time=now + 7200, end_time=now + 10800)
        m.add_exception(f.id, service="api", reason="hotfix")
        s = m.get_stats()
        assert s["total_freezes"] == 2
        assert s["active_freezes"] == 1
        assert s["scheduled_freezes"] == 1
        assert s["total_exceptions"] == 1

    def test_stats_cancelled(self):
        m = _manager()
        now = time.time()
        f = m.create_freeze(name="temp", start_time=now, end_time=now + 3600)
        m.cancel_freeze(f.id)
        s = m.get_stats()
        assert s["cancelled_freezes"] == 1
