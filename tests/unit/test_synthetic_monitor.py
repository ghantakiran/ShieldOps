"""Tests for shieldops.observability.synthetic_monitor — SyntheticMonitorManager."""

from __future__ import annotations

import pytest

from shieldops.observability.synthetic_monitor import (
    CheckResult,
    MonitorStatus,
    MonitorType,
    SyntheticMonitor,
    SyntheticMonitorManager,
)


def _manager(**kw) -> SyntheticMonitorManager:
    return SyntheticMonitorManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # MonitorType (6 values)

    def test_monitor_type_http(self):
        assert MonitorType.HTTP == "http"

    def test_monitor_type_api(self):
        assert MonitorType.API == "api"

    def test_monitor_type_browser(self):
        assert MonitorType.BROWSER == "browser"

    def test_monitor_type_tcp(self):
        assert MonitorType.TCP == "tcp"

    def test_monitor_type_dns(self):
        assert MonitorType.DNS == "dns"

    def test_monitor_type_ssl_cert(self):
        assert MonitorType.SSL_CERT == "ssl_cert"

    # MonitorStatus (4 values)

    def test_monitor_status_active(self):
        assert MonitorStatus.ACTIVE == "active"

    def test_monitor_status_paused(self):
        assert MonitorStatus.PAUSED == "paused"

    def test_monitor_status_failing(self):
        assert MonitorStatus.FAILING == "failing"

    def test_monitor_status_disabled(self):
        assert MonitorStatus.DISABLED == "disabled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_synthetic_monitor_defaults(self):
        m = SyntheticMonitor(
            name="health", monitor_type=MonitorType.HTTP, target_url="https://example.com"
        )
        assert m.id
        assert m.interval_seconds == 60
        assert m.timeout_seconds == 30
        assert m.expected_status_code == 200
        assert m.regions == []
        assert m.status == MonitorStatus.ACTIVE
        assert m.consecutive_failures == 0
        assert m.last_check_at is None
        assert m.last_success_at is None
        assert m.owner == ""
        assert m.metadata == {}
        assert m.created_at > 0

    def test_check_result_defaults(self):
        cr = CheckResult(monitor_id="m1", success=True)
        assert cr.id
        assert cr.response_time_ms == 0.0
        assert cr.status_code is None
        assert cr.region == ""
        assert cr.error_message == ""
        assert cr.checked_at > 0


# ---------------------------------------------------------------------------
# create_monitor
# ---------------------------------------------------------------------------


class TestCreateMonitor:
    def test_basic_create(self):
        mgr = _manager()
        m = mgr.create_monitor("health", MonitorType.HTTP, "https://example.com")
        assert m.name == "health"
        assert m.monitor_type == MonitorType.HTTP
        assert m.target_url == "https://example.com"
        assert m.status == MonitorStatus.ACTIVE

    def test_create_all_fields(self):
        mgr = _manager()
        m = mgr.create_monitor(
            "api-check",
            MonitorType.API,
            "https://api.example.com/health",
            interval_seconds=30,
            timeout_seconds=10,
            expected_status_code=204,
            regions=["us-east-1", "eu-west-1"],
            owner="team-platform",
        )
        assert m.interval_seconds == 30
        assert m.timeout_seconds == 10
        assert m.expected_status_code == 204
        assert m.regions == ["us-east-1", "eu-west-1"]
        assert m.owner == "team-platform"

    def test_create_max_limit(self):
        mgr = _manager(max_monitors=2)
        mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.create_monitor("m2", MonitorType.HTTP, "https://b.com")
        with pytest.raises(ValueError, match="Max monitors limit reached"):
            mgr.create_monitor("m3", MonitorType.HTTP, "https://c.com")


# ---------------------------------------------------------------------------
# record_check
# ---------------------------------------------------------------------------


class TestRecordCheck:
    def test_success_resets_failures(self):
        mgr = _manager(failure_threshold=3)
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=False)
        mgr.record_check(m.id, success=False)
        mgr.record_check(m.id, success=True)
        assert m.consecutive_failures == 0
        assert m.last_success_at is not None

    def test_failure_increments(self):
        mgr = _manager(failure_threshold=5)
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=False)
        assert m.consecutive_failures == 1
        mgr.record_check(m.id, success=False)
        assert m.consecutive_failures == 2

    def test_threshold_triggers_failing(self):
        mgr = _manager(failure_threshold=3)
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=False)
        mgr.record_check(m.id, success=False)
        mgr.record_check(m.id, success=False)
        assert m.status == MonitorStatus.FAILING

    def test_success_after_failing_resets_to_active(self):
        mgr = _manager(failure_threshold=2)
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=False)
        mgr.record_check(m.id, success=False)
        assert m.status == MonitorStatus.FAILING
        mgr.record_check(m.id, success=True)
        assert m.status == MonitorStatus.ACTIVE
        assert m.consecutive_failures == 0

    def test_record_check_not_found(self):
        mgr = _manager()
        with pytest.raises(ValueError, match="Monitor not found"):
            mgr.record_check("nonexistent", success=True)


# ---------------------------------------------------------------------------
# list_monitors
# ---------------------------------------------------------------------------


class TestListMonitors:
    def test_list_all(self):
        mgr = _manager()
        mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.create_monitor("m2", MonitorType.API, "https://b.com")
        assert len(mgr.list_monitors()) == 2

    def test_list_by_status(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.create_monitor("m2", MonitorType.API, "https://b.com")
        mgr.pause_monitor(m.id)
        results = mgr.list_monitors(status=MonitorStatus.PAUSED)
        assert len(results) == 1
        assert results[0].id == m.id

    def test_list_by_type(self):
        mgr = _manager()
        mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.create_monitor("m2", MonitorType.API, "https://b.com")
        results = mgr.list_monitors(monitor_type=MonitorType.API)
        assert len(results) == 1
        assert results[0].monitor_type == MonitorType.API

    def test_list_empty(self):
        mgr = _manager()
        assert mgr.list_monitors() == []


# ---------------------------------------------------------------------------
# pause / resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    def test_pause(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        result = mgr.pause_monitor(m.id)
        assert result is not None
        assert result.status == MonitorStatus.PAUSED

    def test_resume(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.pause_monitor(m.id)
        result = mgr.resume_monitor(m.id)
        assert result is not None
        assert result.status == MonitorStatus.ACTIVE
        assert result.consecutive_failures == 0

    def test_pause_not_found(self):
        mgr = _manager()
        assert mgr.pause_monitor("nonexistent") is None

    def test_resume_not_found(self):
        mgr = _manager()
        assert mgr.resume_monitor("nonexistent") is None


# ---------------------------------------------------------------------------
# delete_monitor
# ---------------------------------------------------------------------------


class TestDeleteMonitor:
    def test_delete_existing(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        assert mgr.delete_monitor(m.id) is True
        assert mgr.get_monitor(m.id) is None

    def test_delete_nonexistent(self):
        mgr = _manager()
        assert mgr.delete_monitor("nonexistent") is False


# ---------------------------------------------------------------------------
# get_check_history
# ---------------------------------------------------------------------------


class TestCheckHistory:
    def test_all_history(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=True)
        mgr.record_check(m.id, success=False)
        assert len(mgr.get_check_history()) == 2

    def test_by_monitor(self):
        mgr = _manager()
        m1 = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        m2 = mgr.create_monitor("m2", MonitorType.HTTP, "https://b.com")
        mgr.record_check(m1.id, success=True)
        mgr.record_check(m2.id, success=True)
        results = mgr.get_check_history(monitor_id=m1.id)
        assert len(results) == 1
        assert results[0].monitor_id == m1.id

    def test_limit(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        for _ in range(10):
            mgr.record_check(m.id, success=True)
        results = mgr.get_check_history(limit=3)
        assert len(results) == 3

    def test_newest_first(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=True)
        mgr.record_check(m.id, success=False)
        history = mgr.get_check_history()
        assert history[0].checked_at >= history[1].checked_at


# ---------------------------------------------------------------------------
# get_availability
# ---------------------------------------------------------------------------


class TestGetAvailability:
    def test_mixed_results(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=True, response_time_ms=100.0)
        mgr.record_check(m.id, success=True, response_time_ms=200.0)
        mgr.record_check(m.id, success=False, response_time_ms=0.0)
        avail = mgr.get_availability(m.id)
        assert avail["total_checks"] == 3
        assert avail["successful"] == 2
        assert avail["failed"] == 1
        assert avail["availability_pct"] == pytest.approx(66.666, abs=0.1)
        assert avail["avg_response_time_ms"] == pytest.approx(100.0, abs=0.1)

    def test_all_success(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=True, response_time_ms=50.0)
        mgr.record_check(m.id, success=True, response_time_ms=50.0)
        avail = mgr.get_availability(m.id)
        assert avail["availability_pct"] == 100.0
        assert avail["failed"] == 0

    def test_all_failure(self):
        mgr = _manager(failure_threshold=10)
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        mgr.record_check(m.id, success=False)
        mgr.record_check(m.id, success=False)
        avail = mgr.get_availability(m.id)
        assert avail["availability_pct"] == 0.0
        assert avail["successful"] == 0

    def test_no_checks(self):
        mgr = _manager()
        m = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        avail = mgr.get_availability(m.id)
        assert avail["total_checks"] == 0
        assert avail["availability_pct"] == 0.0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        mgr = _manager()
        stats = mgr.get_stats()
        assert stats["total_monitors"] == 0
        assert stats["active"] == 0
        assert stats["paused"] == 0
        assert stats["failing"] == 0
        assert stats["total_checks"] == 0
        assert stats["overall_availability_pct"] == 0.0

    def test_stats_populated(self):
        mgr = _manager(failure_threshold=2)
        m1 = mgr.create_monitor("m1", MonitorType.HTTP, "https://a.com")
        m2 = mgr.create_monitor("m2", MonitorType.API, "https://b.com")
        mgr.pause_monitor(m2.id)
        mgr.record_check(m1.id, success=True)
        mgr.record_check(m1.id, success=False)
        stats = mgr.get_stats()
        assert stats["total_monitors"] == 2
        assert stats["active"] == 1
        assert stats["paused"] == 1
        assert stats["total_checks"] == 2
        assert stats["overall_availability_pct"] == 50.0
