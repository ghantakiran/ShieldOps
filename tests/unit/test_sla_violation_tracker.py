"""Tests for the SLA violation tracker module.

Covers:
- ViolationSeverity enum values
- SLAMetricType enum values
- SLATarget model defaults and full creation
- SLAViolation model defaults
- SLAReport model defaults
- SLAViolationTracker creation and defaults
- create_target() with all params, minimal, max limit
- check_violation() higher_is_worse: warning, breach, critical, no violation
- check_violation() lower_is_worse: warning, breach, critical, no violation
- resolve_violation() found and not found
- get_target() found and not found
- list_targets() all, filter by service
- delete_target() found and not found
- list_violations() all, filter service, severity, active_only
- get_service_report() basic, compliance, active breaches
- get_stats() empty and populated
- Violation list auto-trimming at max_violations
"""

from __future__ import annotations

import time

import pytest

from shieldops.sla.violation_tracker import (
    SLAMetricType,
    SLAReport,
    SLATarget,
    SLAViolation,
    SLAViolationTracker,
    ViolationSeverity,
)

# -- Helpers ----------------------------------------------------------


def _make_tracker(**kwargs) -> SLAViolationTracker:
    """Return a fresh SLAViolationTracker with optional overrides."""
    return SLAViolationTracker(**kwargs)


def _make_latency_target(
    tracker: SLAViolationTracker,
    service: str = "api-gw",
    **kwargs,
) -> SLATarget:
    """Create a latency SLA target (higher_is_worse)."""
    defaults = dict(
        service=service,
        metric_type=SLAMetricType.LATENCY,
        target_value=200.0,
        threshold_warning=300.0,
        threshold_breach=500.0,
    )
    defaults.update(kwargs)
    return tracker.create_target(**defaults)


def _make_availability_target(
    tracker: SLAViolationTracker,
    service: str = "api-gw",
    **kwargs,
) -> SLATarget:
    """Create an availability SLA target (lower_is_worse)."""
    defaults = dict(
        service=service,
        metric_type=SLAMetricType.AVAILABILITY,
        target_value=99.9,
        threshold_warning=99.5,
        threshold_breach=99.0,
    )
    defaults.update(kwargs)
    return tracker.create_target(**defaults)


# -- Fixtures ---------------------------------------------------------


@pytest.fixture()
def tracker() -> SLAViolationTracker:
    """Return a fresh SLAViolationTracker."""
    return SLAViolationTracker()


@pytest.fixture()
def populated_tracker() -> SLAViolationTracker:
    """Tracker with targets and some violations."""
    t = SLAViolationTracker()
    lat = _make_latency_target(t, service="api-gw")
    avail = _make_availability_target(t, service="api-gw")
    _make_latency_target(t, service="web-app")

    # Trigger violations
    t.check_violation(lat.id, current_value=350.0)  # warning
    t.check_violation(lat.id, current_value=600.0)  # breach
    t.check_violation(avail.id, current_value=98.5)  # breach
    return t


# -- Enum Tests -------------------------------------------------------


class TestViolationSeverityEnum:
    def test_warning_value(self) -> None:
        assert ViolationSeverity.WARNING == "warning"

    def test_breach_value(self) -> None:
        assert ViolationSeverity.BREACH == "breach"

    def test_critical_breach_value(self) -> None:
        assert ViolationSeverity.CRITICAL_BREACH == "critical_breach"

    def test_all_members(self) -> None:
        members = {m.value for m in ViolationSeverity}
        assert members == {"warning", "breach", "critical_breach"}


class TestSLAMetricTypeEnum:
    def test_availability_value(self) -> None:
        assert SLAMetricType.AVAILABILITY == "availability"

    def test_latency_value(self) -> None:
        assert SLAMetricType.LATENCY == "latency"

    def test_error_rate_value(self) -> None:
        assert SLAMetricType.ERROR_RATE == "error_rate"

    def test_throughput_value(self) -> None:
        assert SLAMetricType.THROUGHPUT == "throughput"

    def test_response_time_value(self) -> None:
        assert SLAMetricType.RESPONSE_TIME == "response_time"

    def test_all_members(self) -> None:
        members = {m.value for m in SLAMetricType}
        expected = {
            "availability",
            "latency",
            "error_rate",
            "throughput",
            "response_time",
        }
        assert members == expected


# -- Model Tests ------------------------------------------------------


class TestSLATargetModel:
    def test_defaults(self) -> None:
        t = SLATarget(
            service="api",
            metric_type=SLAMetricType.LATENCY,
            target_value=200.0,
            threshold_warning=300.0,
            threshold_breach=500.0,
        )
        assert t.service == "api"
        assert t.metric_type == SLAMetricType.LATENCY
        assert t.target_value == 200.0
        assert t.threshold_warning == 300.0
        assert t.threshold_breach == 500.0
        assert t.period_hours == 24
        assert t.metadata == {}
        assert t.created_at > 0
        assert len(t.id) == 12

    def test_unique_ids(self) -> None:
        t1 = SLATarget(
            service="a",
            metric_type=SLAMetricType.LATENCY,
            target_value=1,
            threshold_warning=2,
            threshold_breach=3,
        )
        t2 = SLATarget(
            service="b",
            metric_type=SLAMetricType.LATENCY,
            target_value=1,
            threshold_warning=2,
            threshold_breach=3,
        )
        assert t1.id != t2.id


class TestSLAViolationModel:
    def test_defaults(self) -> None:
        v = SLAViolation(
            target_id="t1",
            service="api",
            metric_type=SLAMetricType.LATENCY,
            current_value=600.0,
            target_value=200.0,
            severity=ViolationSeverity.BREACH,
        )
        assert v.target_id == "t1"
        assert v.service == "api"
        assert v.current_value == 600.0
        assert v.severity == ViolationSeverity.BREACH
        assert v.message == ""
        assert v.detected_at > 0
        assert v.resolved_at is None
        assert len(v.id) == 12


class TestSLAReportModel:
    def test_defaults(self) -> None:
        r = SLAReport(service="api")
        assert r.service == "api"
        assert r.total_targets == 0
        assert r.violations == 0
        assert r.compliance_pct == pytest.approx(100.0)
        assert r.active_breaches == 0


# -- Tracker Creation -------------------------------------------------


class TestTrackerCreation:
    def test_default_params(self) -> None:
        t = SLAViolationTracker()
        assert t._max_targets == 500
        assert t._max_violations == 10000

    def test_custom_params(self) -> None:
        t = SLAViolationTracker(max_targets=10, max_violations=100)
        assert t._max_targets == 10
        assert t._max_violations == 100

    def test_starts_empty(self) -> None:
        t = SLAViolationTracker()
        assert len(t._targets) == 0
        assert len(t._violations) == 0


# -- create_target ----------------------------------------------------


class TestCreateTarget:
    def test_minimal(self, tracker: SLAViolationTracker) -> None:
        target = tracker.create_target(
            service="api",
            metric_type=SLAMetricType.LATENCY,
            target_value=200.0,
            threshold_warning=300.0,
            threshold_breach=500.0,
        )
        assert target.service == "api"
        assert target.metric_type == SLAMetricType.LATENCY

    def test_all_params(self, tracker: SLAViolationTracker) -> None:
        target = tracker.create_target(
            service="api",
            metric_type=SLAMetricType.AVAILABILITY,
            target_value=99.9,
            threshold_warning=99.5,
            threshold_breach=99.0,
            period_hours=168,
            metadata={"team": "platform"},
        )
        assert target.period_hours == 168
        assert target.metadata == {"team": "platform"}

    def test_stored_in_tracker(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        assert tracker.get_target(target.id) is not None

    def test_max_limit_raises(self) -> None:
        t = SLAViolationTracker(max_targets=2)
        _make_latency_target(t, service="a")
        _make_latency_target(t, service="b")
        with pytest.raises(ValueError, match="Maximum targets limit reached"):
            _make_latency_target(t, service="c")

    def test_none_metadata_becomes_empty_dict(self, tracker: SLAViolationTracker) -> None:
        target = tracker.create_target(
            service="api",
            metric_type=SLAMetricType.LATENCY,
            target_value=200.0,
            threshold_warning=300.0,
            threshold_breach=500.0,
            metadata=None,
        )
        assert target.metadata == {}

    def test_returns_sla_target_instance(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        assert isinstance(target, SLATarget)


# -- check_violation (higher_is_worse) --------------------------------


class TestCheckViolationHigherIsWorse:
    """Latency, error_rate, response_time: higher values are worse."""

    def test_no_violation_below_warning(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.check_violation(target.id, 250.0)
        assert result is None

    def test_warning_at_threshold(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.check_violation(target.id, 300.0)
        assert result is not None
        assert result.severity == ViolationSeverity.WARNING

    def test_warning_between_thresholds(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.check_violation(target.id, 400.0)
        assert result.severity == ViolationSeverity.WARNING

    def test_breach_at_threshold(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.check_violation(target.id, 500.0)
        assert result.severity == ViolationSeverity.BREACH

    def test_breach_between_thresholds(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.check_violation(target.id, 600.0)
        assert result.severity == ViolationSeverity.BREACH

    def test_critical_breach_at_1_5x(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        # 500 * 1.5 = 750
        result = tracker.check_violation(target.id, 750.0)
        assert result.severity == ViolationSeverity.CRITICAL_BREACH

    def test_critical_breach_above_1_5x(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.check_violation(target.id, 1000.0)
        assert result.severity == ViolationSeverity.CRITICAL_BREACH

    def test_error_rate_is_higher_is_worse(self, tracker: SLAViolationTracker) -> None:
        target = tracker.create_target(
            service="api",
            metric_type=SLAMetricType.ERROR_RATE,
            target_value=0.1,
            threshold_warning=1.0,
            threshold_breach=5.0,
        )
        result = tracker.check_violation(target.id, 2.0)
        assert result.severity == ViolationSeverity.WARNING

    def test_response_time_is_higher_is_worse(self, tracker: SLAViolationTracker) -> None:
        target = tracker.create_target(
            service="api",
            metric_type=SLAMetricType.RESPONSE_TIME,
            target_value=100.0,
            threshold_warning=200.0,
            threshold_breach=500.0,
        )
        result = tracker.check_violation(target.id, 600.0)
        assert result.severity == ViolationSeverity.BREACH

    def test_target_not_found_raises(self, tracker: SLAViolationTracker) -> None:
        with pytest.raises(ValueError, match="SLA target not found"):
            tracker.check_violation("bad-id", 100.0)

    def test_violation_message_populated(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.check_violation(target.id, 400.0)
        assert "latency" in result.message
        assert "api-gw" in result.message

    def test_violation_stored_in_tracker(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        tracker.check_violation(target.id, 400.0)
        assert len(tracker._violations) == 1


# -- check_violation (lower_is_worse) ---------------------------------


class TestCheckViolationLowerIsWorse:
    """Availability, throughput: lower values are worse."""

    def test_no_violation_above_warning(self, tracker: SLAViolationTracker) -> None:
        target = _make_availability_target(tracker)
        result = tracker.check_violation(target.id, 99.8)
        assert result is None

    def test_warning_at_threshold(self, tracker: SLAViolationTracker) -> None:
        target = _make_availability_target(tracker)
        result = tracker.check_violation(target.id, 99.5)
        assert result is not None
        assert result.severity == ViolationSeverity.WARNING

    def test_warning_between_thresholds(self, tracker: SLAViolationTracker) -> None:
        target = _make_availability_target(tracker)
        result = tracker.check_violation(target.id, 99.2)
        assert result.severity == ViolationSeverity.WARNING

    def test_breach_at_threshold(self, tracker: SLAViolationTracker) -> None:
        target = _make_availability_target(tracker)
        result = tracker.check_violation(target.id, 99.0)
        assert result.severity == ViolationSeverity.BREACH

    def test_breach_between_thresholds(self, tracker: SLAViolationTracker) -> None:
        target = _make_availability_target(tracker)
        # Between 99.0 and 99.0*0.5=49.5
        result = tracker.check_violation(target.id, 98.0)
        assert result.severity == ViolationSeverity.BREACH

    def test_critical_breach_at_half(self, tracker: SLAViolationTracker) -> None:
        target = _make_availability_target(tracker)
        # 99.0 * 0.5 = 49.5
        result = tracker.check_violation(target.id, 49.5)
        assert result.severity == ViolationSeverity.CRITICAL_BREACH

    def test_critical_breach_below_half(self, tracker: SLAViolationTracker) -> None:
        target = _make_availability_target(tracker)
        result = tracker.check_violation(target.id, 10.0)
        assert result.severity == ViolationSeverity.CRITICAL_BREACH

    def test_throughput_is_lower_is_worse(self, tracker: SLAViolationTracker) -> None:
        target = tracker.create_target(
            service="api",
            metric_type=SLAMetricType.THROUGHPUT,
            target_value=1000.0,
            threshold_warning=800.0,
            threshold_breach=500.0,
        )
        result = tracker.check_violation(target.id, 400.0)
        assert result.severity == ViolationSeverity.BREACH


# -- resolve_violation ------------------------------------------------


class TestResolveViolation:
    def test_basic(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        v = tracker.check_violation(target.id, 400.0)
        result = tracker.resolve_violation(v.id)
        assert result is not None
        assert result.resolved_at is not None

    def test_resolved_at_is_recent(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        v = tracker.check_violation(target.id, 400.0)
        before = time.time()
        tracker.resolve_violation(v.id)
        after = time.time()
        assert before <= v.resolved_at <= after

    def test_not_found_returns_none(self, tracker: SLAViolationTracker) -> None:
        result = tracker.resolve_violation("bad-id")
        assert result is None


# -- get_target -------------------------------------------------------


class TestGetTarget:
    def test_found(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.get_target(target.id)
        assert result is not None
        assert result.id == target.id

    def test_not_found(self, tracker: SLAViolationTracker) -> None:
        assert tracker.get_target("nonexistent") is None


# -- list_targets -----------------------------------------------------


class TestListTargets:
    def test_all(self, populated_tracker: SLAViolationTracker) -> None:
        targets = populated_tracker.list_targets()
        assert len(targets) == 3

    def test_filter_by_service(self, populated_tracker: SLAViolationTracker) -> None:
        targets = populated_tracker.list_targets(service="api-gw")
        assert len(targets) == 2

    def test_no_match(self, populated_tracker: SLAViolationTracker) -> None:
        targets = populated_tracker.list_targets(service="unknown")
        assert targets == []

    def test_empty_tracker(self, tracker: SLAViolationTracker) -> None:
        assert tracker.list_targets() == []


# -- delete_target ----------------------------------------------------


class TestDeleteTarget:
    def test_found(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        result = tracker.delete_target(target.id)
        assert result is True
        assert tracker.get_target(target.id) is None

    def test_not_found(self, tracker: SLAViolationTracker) -> None:
        result = tracker.delete_target("bad-id")
        assert result is False


# -- list_violations --------------------------------------------------


class TestListViolations:
    def test_all(self, populated_tracker: SLAViolationTracker) -> None:
        violations = populated_tracker.list_violations()
        assert len(violations) == 3

    def test_filter_by_service(self, populated_tracker: SLAViolationTracker) -> None:
        violations = populated_tracker.list_violations(service="api-gw")
        assert len(violations) == 3

    def test_filter_by_severity(self, populated_tracker: SLAViolationTracker) -> None:
        violations = populated_tracker.list_violations(severity=ViolationSeverity.WARNING)
        assert len(violations) == 1

    def test_active_only(self, populated_tracker: SLAViolationTracker) -> None:
        violations = populated_tracker.list_violations(active_only=True)
        assert len(violations) == 3
        for v in violations:
            assert v.resolved_at is None

    def test_active_only_after_resolve(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        v = tracker.check_violation(target.id, 400.0)
        tracker.resolve_violation(v.id)
        active = tracker.list_violations(active_only=True)
        assert len(active) == 0

    def test_no_match(self, tracker: SLAViolationTracker) -> None:
        violations = tracker.list_violations(service="unknown")
        assert violations == []

    def test_empty_tracker(self, tracker: SLAViolationTracker) -> None:
        assert tracker.list_violations() == []


# -- Violation list auto-trim -----------------------------------------


class TestViolationAutoTrim:
    def test_trims_at_max(self) -> None:
        t = SLAViolationTracker(max_violations=4)
        target = _make_latency_target(t)
        for _ in range(5):
            t.check_violation(target.id, 400.0)
        # After trim: keeps max_violations // 2 = 2, plus the new one
        assert len(t._violations) <= 4


# -- get_service_report -----------------------------------------------


class TestGetServiceReport:
    def test_basic(self, populated_tracker: SLAViolationTracker) -> None:
        report = populated_tracker.get_service_report("api-gw")
        assert isinstance(report, SLAReport)
        assert report.service == "api-gw"
        assert report.total_targets == 2
        assert report.violations == 3

    def test_compliance_calculation(self, populated_tracker: SLAViolationTracker) -> None:
        report = populated_tracker.get_service_report("api-gw")
        # 3 violations, 2 targets -> (1 - 3/2)*100 = -50 -> clamped 0
        assert report.compliance_pct == pytest.approx(0.0)

    def test_active_breaches_count(self, populated_tracker: SLAViolationTracker) -> None:
        report = populated_tracker.get_service_report("api-gw")
        # 2 breaches (latency 600 + avail 98.5), not resolved
        assert report.active_breaches == 2

    def test_no_violations_100_compliance(self, populated_tracker: SLAViolationTracker) -> None:
        report = populated_tracker.get_service_report("web-app")
        assert report.compliance_pct == pytest.approx(100.0)
        assert report.violations == 0

    def test_unknown_service(self, tracker: SLAViolationTracker) -> None:
        report = tracker.get_service_report("unknown")
        assert report.total_targets == 0
        assert report.violations == 0
        assert report.compliance_pct == pytest.approx(100.0)

    def test_resolved_breach_not_counted_as_active(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        v = tracker.check_violation(target.id, 600.0)
        tracker.resolve_violation(v.id)
        report = tracker.get_service_report("api-gw")
        assert report.active_breaches == 0
        assert report.violations == 1


# -- get_stats --------------------------------------------------------


class TestGetStats:
    def test_empty_tracker(self, tracker: SLAViolationTracker) -> None:
        stats = tracker.get_stats()
        assert stats["total_targets"] == 0
        assert stats["total_violations"] == 0
        assert stats["active_violations"] == 0
        assert stats["warnings"] == 0
        assert stats["breaches"] == 0
        assert stats["critical_breaches"] == 0

    def test_populated(self, populated_tracker: SLAViolationTracker) -> None:
        stats = populated_tracker.get_stats()
        assert stats["total_targets"] == 3
        assert stats["total_violations"] == 3
        assert stats["active_violations"] == 3
        assert stats["warnings"] == 1
        assert stats["breaches"] == 2
        assert stats["critical_breaches"] == 0

    def test_after_resolve(self, tracker: SLAViolationTracker) -> None:
        target = _make_latency_target(tracker)
        v = tracker.check_violation(target.id, 400.0)
        tracker.resolve_violation(v.id)
        stats = tracker.get_stats()
        assert stats["total_violations"] == 1
        assert stats["active_violations"] == 0

    def test_stats_keys(self, tracker: SLAViolationTracker) -> None:
        stats = tracker.get_stats()
        expected_keys = {
            "total_targets",
            "total_violations",
            "active_violations",
            "warnings",
            "breaches",
            "critical_breaches",
        }
        assert set(stats.keys()) == expected_keys
