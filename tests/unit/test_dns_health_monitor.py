"""Tests for shieldops.observability.dns_health_monitor."""

from __future__ import annotations

from shieldops.observability.dns_health_monitor import (
    DNSHealth,
    DNSHealthMonitor,
    DNSHealthReport,
    DNSPolicy,
    DNSProvider,
    DNSRecord,
    DNSRecordType,
)


def _engine(**kw) -> DNSHealthMonitor:
    return DNSHealthMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DNSRecordType (5)
    def test_record_type_a(self):
        assert DNSRecordType.A_RECORD == "a_record"

    def test_record_type_cname(self):
        assert DNSRecordType.CNAME == "cname"

    def test_record_type_mx(self):
        assert DNSRecordType.MX == "mx"

    def test_record_type_txt(self):
        assert DNSRecordType.TXT == "txt"

    def test_record_type_srv(self):
        assert DNSRecordType.SRV == "srv"

    # DNSHealth (5)
    def test_health_healthy(self):
        assert DNSHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert DNSHealth.DEGRADED == "degraded"

    def test_health_failing(self):
        assert DNSHealth.FAILING == "failing"

    def test_health_unreachable(self):
        assert DNSHealth.UNREACHABLE == "unreachable"

    def test_health_misconfigured(self):
        assert DNSHealth.MISCONFIGURED == "misconfigured"

    # DNSProvider (5)
    def test_provider_route53(self):
        assert DNSProvider.ROUTE53 == "route53"

    def test_provider_cloudflare(self):
        assert DNSProvider.CLOUDFLARE == "cloudflare"

    def test_provider_cloud_dns(self):
        assert DNSProvider.CLOUD_DNS == "cloud_dns"

    def test_provider_azure_dns(self):
        assert DNSProvider.AZURE_DNS == "azure_dns"

    def test_provider_custom(self):
        assert DNSProvider.CUSTOM == "custom"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_dns_record_defaults(self):
        r = DNSRecord()
        assert r.id
        assert r.domain_name == ""
        assert r.record_type == DNSRecordType.A_RECORD
        assert r.health == DNSHealth.HEALTHY
        assert r.provider == DNSProvider.ROUTE53
        assert r.resolution_ms == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_dns_policy_defaults(self):
        r = DNSPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.record_type == DNSRecordType.A_RECORD
        assert r.provider == DNSProvider.ROUTE53
        assert r.max_resolution_ms == 100.0
        assert r.ttl_seconds == 300.0
        assert r.created_at > 0

    def test_dns_health_report_defaults(self):
        r = DNSHealthReport()
        assert r.total_checks == 0
        assert r.total_policies == 0
        assert r.healthy_rate_pct == 0.0
        assert r.by_record_type == {}
        assert r.by_health == {}
        assert r.failing_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_check
# -------------------------------------------------------------------


class TestRecordCheck:
    def test_basic(self):
        eng = _engine()
        r = eng.record_check(
            "example.com",
            record_type=DNSRecordType.A_RECORD,
            health=DNSHealth.HEALTHY,
        )
        assert r.domain_name == "example.com"
        assert r.record_type == DNSRecordType.A_RECORD

    def test_with_provider(self):
        eng = _engine()
        r = eng.record_check(
            "example.com",
            provider=DNSProvider.CLOUDFLARE,
        )
        assert r.provider == DNSProvider.CLOUDFLARE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_check(f"domain-{i}.com")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_check
# -------------------------------------------------------------------


class TestGetCheck:
    def test_found(self):
        eng = _engine()
        r = eng.record_check("example.com")
        assert eng.get_check(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_check("nonexistent") is None


# -------------------------------------------------------------------
# list_checks
# -------------------------------------------------------------------


class TestListChecks:
    def test_list_all(self):
        eng = _engine()
        eng.record_check("example.com")
        eng.record_check("test.com")
        assert len(eng.list_checks()) == 2

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_check("example.com")
        eng.record_check("test.com")
        results = eng.list_checks(domain_name="example.com")
        assert len(results) == 1

    def test_filter_by_record_type(self):
        eng = _engine()
        eng.record_check(
            "a.com",
            record_type=DNSRecordType.CNAME,
        )
        eng.record_check(
            "b.com",
            record_type=DNSRecordType.MX,
        )
        results = eng.list_checks(record_type=DNSRecordType.CNAME)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "fast-resolution",
            record_type=DNSRecordType.A_RECORD,
            provider=DNSProvider.ROUTE53,
            max_resolution_ms=50.0,
            ttl_seconds=600.0,
        )
        assert p.policy_name == "fast-resolution"
        assert p.max_resolution_ms == 50.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_dns_health
# -------------------------------------------------------------------


class TestAnalyzeDNSHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_check(
            "example.com",
            health=DNSHealth.HEALTHY,
            resolution_ms=50.0,
        )
        eng.record_check(
            "example.com",
            health=DNSHealth.FAILING,
            resolution_ms=150.0,
        )
        result = eng.analyze_dns_health("example.com")
        assert result["domain_name"] == "example.com"
        assert result["check_count"] == 2
        assert result["healthy_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_dns_health("ghost.com")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_resolution_ms=200.0)
        eng.record_check(
            "fast.com",
            health=DNSHealth.HEALTHY,
            resolution_ms=50.0,
        )
        result = eng.analyze_dns_health("fast.com")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_failing_domains
# -------------------------------------------------------------------


class TestIdentifyFailingDomains:
    def test_with_failures(self):
        eng = _engine()
        eng.record_check("bad.com", health=DNSHealth.FAILING)
        eng.record_check("bad.com", health=DNSHealth.FAILING)
        eng.record_check("good.com", health=DNSHealth.HEALTHY)
        results = eng.identify_failing_domains()
        assert len(results) == 1
        assert results[0]["domain_name"] == "bad.com"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failing_domains() == []


# -------------------------------------------------------------------
# rank_by_resolution_time
# -------------------------------------------------------------------


class TestRankByResolutionTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_check("slow.com", resolution_ms=200.0)
        eng.record_check("slow.com", resolution_ms=200.0)
        eng.record_check("fast.com", resolution_ms=10.0)
        results = eng.rank_by_resolution_time()
        assert results[0]["domain_name"] == "slow.com"
        assert results[0]["avg_resolution_ms"] == 200.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_resolution_time() == []


# -------------------------------------------------------------------
# detect_dns_issues
# -------------------------------------------------------------------


class TestDetectDNSIssues:
    def test_with_issues(self):
        eng = _engine()
        for _ in range(5):
            eng.record_check(
                "bad.com",
                health=DNSHealth.DEGRADED,
            )
        eng.record_check("good.com", health=DNSHealth.HEALTHY)
        results = eng.detect_dns_issues()
        assert len(results) == 1
        assert results[0]["domain_name"] == "bad.com"
        assert results[0]["issue_detected"] is True

    def test_no_issues(self):
        eng = _engine()
        eng.record_check("ok.com", health=DNSHealth.DEGRADED)
        assert eng.detect_dns_issues() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_check("a.com", health=DNSHealth.HEALTHY)
        eng.record_check("b.com", health=DNSHealth.FAILING)
        eng.record_check("b.com", health=DNSHealth.FAILING)
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_checks == 3
        assert report.total_policies == 1
        assert report.by_record_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_checks == 0
        assert "optimal" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_check("example.com")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_checks"] == 0
        assert stats["total_policies"] == 0
        assert stats["record_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_check(
            "a.com",
            record_type=DNSRecordType.A_RECORD,
        )
        eng.record_check(
            "b.com",
            record_type=DNSRecordType.CNAME,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_checks"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_domains"] == 2
