"""Tests for shieldops.observability.dns_health — DNSHealthMonitor."""

from __future__ import annotations

from shieldops.observability.dns_health import (
    DNSCheck,
    DNSHealthMonitor,
    DNSHealthStatus,
    PropagationCheck,
    PropagationState,
    RecordType,
    ZoneHealthReport,
)


def _engine(**kw) -> DNSHealthMonitor:
    return DNSHealthMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RecordType (6)
    def test_record_type_a(self):
        assert RecordType.A == "A"

    def test_record_type_aaaa(self):
        assert RecordType.AAAA == "AAAA"

    def test_record_type_cname(self):
        assert RecordType.CNAME == "CNAME"

    def test_record_type_mx(self):
        assert RecordType.MX == "MX"

    def test_record_type_txt(self):
        assert RecordType.TXT == "TXT"

    def test_record_type_ns(self):
        assert RecordType.NS == "NS"

    # DNSHealthStatus (5)
    def test_status_healthy(self):
        assert DNSHealthStatus.HEALTHY == "healthy"

    def test_status_degraded(self):
        assert DNSHealthStatus.DEGRADED == "degraded"

    def test_status_timeout(self):
        assert DNSHealthStatus.TIMEOUT == "timeout"

    def test_status_nxdomain(self):
        assert DNSHealthStatus.NXDOMAIN == "nxdomain"

    def test_status_servfail(self):
        assert DNSHealthStatus.SERVFAIL == "servfail"

    # PropagationState (4)
    def test_propagation_complete(self):
        assert PropagationState.COMPLETE == "complete"

    def test_propagation_in_progress(self):
        assert PropagationState.IN_PROGRESS == "in_progress"

    def test_propagation_inconsistent(self):
        assert PropagationState.INCONSISTENT == "inconsistent"

    def test_propagation_failed(self):
        assert PropagationState.FAILED == "failed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dns_check_defaults(self):
        c = DNSCheck(domain="example.com", record_type=RecordType.A)
        assert c.id
        assert c.status == DNSHealthStatus.HEALTHY
        assert c.ttl == 3600

    def test_propagation_check_defaults(self):
        p = PropagationCheck(domain="example.com", record_type=RecordType.A)
        assert p.id
        assert p.state == PropagationState.IN_PROGRESS
        assert p.resolvers_checked == 0

    def test_zone_health_report_defaults(self):
        r = ZoneHealthReport(zone="example.com")
        assert r.total_checks == 0
        assert r.health_score == 0.0
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# record_check
# ---------------------------------------------------------------------------


class TestRecordCheck:
    def test_healthy_check(self):
        eng = _engine(timeout_ms=5000)
        c = eng.record_check("example.com", RecordType.A, response_time_ms=100.0)
        assert c.status == DNSHealthStatus.HEALTHY

    def test_degraded_check(self):
        eng = _engine(timeout_ms=5000)
        # 0.7 * 5000 = 3500; response_time >= 3500 triggers DEGRADED
        c = eng.record_check("example.com", RecordType.A, response_time_ms=3500.0)
        assert c.status == DNSHealthStatus.DEGRADED

    def test_timeout_check(self):
        eng = _engine(timeout_ms=5000)
        c = eng.record_check("example.com", RecordType.A, response_time_ms=5000.0)
        assert c.status == DNSHealthStatus.TIMEOUT

    def test_eviction_at_max(self):
        eng = _engine(max_checks=3)
        for i in range(5):
            eng.record_check(f"d{i}.com", RecordType.A)
        assert len(eng._checks) == 3


# ---------------------------------------------------------------------------
# get_check
# ---------------------------------------------------------------------------


class TestGetCheck:
    def test_found(self):
        eng = _engine()
        c = eng.record_check("example.com", RecordType.A)
        assert eng.get_check(c.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_check("nonexistent") is None


# ---------------------------------------------------------------------------
# list_checks
# ---------------------------------------------------------------------------


class TestListChecks:
    def test_list_all(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A)
        eng.record_check("b.com", RecordType.MX)
        assert len(eng.list_checks()) == 2

    def test_filter_domain(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A)
        eng.record_check("b.com", RecordType.A)
        results = eng.list_checks(domain="a.com")
        assert len(results) == 1
        assert results[0].domain == "a.com"

    def test_filter_record_type(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A)
        eng.record_check("b.com", RecordType.MX)
        results = eng.list_checks(record_type=RecordType.MX)
        assert len(results) == 1
        assert results[0].record_type == RecordType.MX


# ---------------------------------------------------------------------------
# check_propagation
# ---------------------------------------------------------------------------


class TestCheckPropagation:
    def test_complete(self):
        eng = _engine()
        p = eng.check_propagation(
            "example.com",
            RecordType.A,
            resolvers_checked=10,
            resolvers_consistent=10,
        )
        assert p.state == PropagationState.COMPLETE

    def test_inconsistent(self):
        eng = _engine()
        # consistent < checked * 0.8 => inconsistent (5 < 10*0.8=8)
        p = eng.check_propagation(
            "example.com",
            RecordType.A,
            resolvers_checked=10,
            resolvers_consistent=5,
        )
        assert p.state == PropagationState.INCONSISTENT

    def test_failed(self):
        eng = _engine()
        p = eng.check_propagation(
            "example.com",
            RecordType.A,
            resolvers_checked=10,
            resolvers_consistent=0,
        )
        assert p.state == PropagationState.FAILED

    def test_in_progress(self):
        eng = _engine()
        # resolvers_checked=0 => IN_PROGRESS (default branch)
        p = eng.check_propagation(
            "example.com",
            RecordType.A,
            resolvers_checked=0,
            resolvers_consistent=0,
        )
        assert p.state == PropagationState.IN_PROGRESS


# ---------------------------------------------------------------------------
# detect_failures
# ---------------------------------------------------------------------------


class TestDetectFailures:
    def test_no_failures(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A, response_time_ms=50.0)
        assert len(eng.detect_failures()) == 0

    def test_some_failures(self):
        eng = _engine(timeout_ms=1000)
        eng.record_check("a.com", RecordType.A, response_time_ms=50.0)
        eng.record_check("b.com", RecordType.A, response_time_ms=1000.0)  # TIMEOUT
        failures = eng.detect_failures()
        assert len(failures) == 1
        assert failures[0].status == DNSHealthStatus.TIMEOUT


# ---------------------------------------------------------------------------
# measure_resolution_latency
# ---------------------------------------------------------------------------


class TestMeasureResolutionLatency:
    def test_empty(self):
        eng = _engine()
        assert eng.measure_resolution_latency() == {}

    def test_with_data(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A, response_time_ms=100.0)
        eng.record_check("a.com", RecordType.A, response_time_ms=200.0)
        latency = eng.measure_resolution_latency()
        assert "a.com" in latency
        assert latency["a.com"] == 150.0


# ---------------------------------------------------------------------------
# generate_zone_report
# ---------------------------------------------------------------------------


class TestGenerateZoneReport:
    def test_basic_report(self):
        eng = _engine(timeout_ms=1000)
        eng.record_check("api.example.com", RecordType.A, response_time_ms=50.0)
        eng.record_check("web.example.com", RecordType.A, response_time_ms=1000.0)
        report = eng.generate_zone_report("example.com")
        assert report.total_checks == 2
        assert report.healthy_count == 1
        assert report.timeout_count == 1
        assert report.health_score == 50.0


# ---------------------------------------------------------------------------
# list_propagation_checks
# ---------------------------------------------------------------------------


class TestListPropagationChecks:
    def test_list_all(self):
        eng = _engine()
        eng.check_propagation("a.com", RecordType.A, resolvers_checked=5, resolvers_consistent=5)
        eng.check_propagation("b.com", RecordType.A, resolvers_checked=5, resolvers_consistent=5)
        assert len(eng.list_propagation_checks()) == 2

    def test_filter_domain(self):
        eng = _engine()
        eng.check_propagation("a.com", RecordType.A, resolvers_checked=5, resolvers_consistent=5)
        eng.check_propagation("b.com", RecordType.A, resolvers_checked=5, resolvers_consistent=5)
        results = eng.list_propagation_checks(domain="a.com")
        assert len(results) == 1
        assert results[0].domain == "a.com"


# ---------------------------------------------------------------------------
# detect_ttl_anomalies
# ---------------------------------------------------------------------------


class TestDetectTtlAnomalies:
    def test_no_anomalies(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A, ttl=3600)
        assert len(eng.detect_ttl_anomalies()) == 0

    def test_with_anomalies(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A, ttl=10)  # too low (< 60)
        eng.record_check("b.com", RecordType.A, ttl=100000)  # too high (> 86400)
        eng.record_check("c.com", RecordType.A, ttl=3600)  # normal
        anomalies = eng.detect_ttl_anomalies()
        assert len(anomalies) == 2


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_checks"] == 0
        assert stats["total_propagation_checks"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_check("a.com", RecordType.A)
        eng.check_propagation("a.com", RecordType.A, resolvers_checked=5, resolvers_consistent=5)
        stats = eng.get_stats()
        assert stats["total_checks"] == 1
        assert stats["total_propagation_checks"] == 1
