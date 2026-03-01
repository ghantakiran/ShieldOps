"""Tests for shieldops.sla.customer_impact — CustomerImpactScorer."""

from __future__ import annotations

from shieldops.sla.customer_impact import (
    CustomerImpactRecord,
    CustomerImpactReport,
    CustomerImpactScorer,
    CustomerTier,
    ImpactCategory,
    ImpactDetail,
    ImpactSeverity,
)


def _engine(**kw) -> CustomerImpactScorer:
    return CustomerImpactScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_availability(self):
        assert ImpactCategory.AVAILABILITY == "availability"

    def test_category_performance(self):
        assert ImpactCategory.PERFORMANCE == "performance"

    def test_category_functionality(self):
        assert ImpactCategory.FUNCTIONALITY == "functionality"

    def test_category_data_access(self):
        assert ImpactCategory.DATA_ACCESS == "data_access"

    def test_category_billing(self):
        assert ImpactCategory.BILLING == "billing"

    def test_tier_enterprise(self):
        assert CustomerTier.ENTERPRISE == "enterprise"

    def test_tier_business(self):
        assert CustomerTier.BUSINESS == "business"

    def test_tier_professional(self):
        assert CustomerTier.PROFESSIONAL == "professional"

    def test_tier_starter(self):
        assert CustomerTier.STARTER == "starter"

    def test_tier_free(self):
        assert CustomerTier.FREE == "free"

    def test_severity_critical(self):
        assert ImpactSeverity.CRITICAL == "critical"

    def test_severity_major(self):
        assert ImpactSeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert ImpactSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert ImpactSeverity.MINOR == "minor"

    def test_severity_cosmetic(self):
        assert ImpactSeverity.COSMETIC == "cosmetic"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_customer_impact_record_defaults(self):
        r = CustomerImpactRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.impact_category == ImpactCategory.AVAILABILITY
        assert r.customer_tier == CustomerTier.FREE
        assert r.impact_severity == ImpactSeverity.MINOR
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_detail_defaults(self):
        d = ImpactDetail()
        assert d.id
        assert d.incident_id == ""
        assert d.impact_category == ImpactCategory.AVAILABILITY
        assert d.value == 0.0
        assert d.threshold == 0.0
        assert d.breached is False
        assert d.description == ""
        assert d.created_at > 0

    def test_customer_impact_report_defaults(self):
        r = CustomerImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_details == 0
        assert r.high_impact_incidents == 0
        assert r.avg_impact_score == 0.0
        assert r.by_category == {}
        assert r.by_tier == {}
        assert r.by_severity == {}
        assert r.top_impacted == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_impact
# ---------------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact(
            incident_id="INC-001",
            impact_category=ImpactCategory.PERFORMANCE,
            customer_tier=CustomerTier.ENTERPRISE,
            impact_severity=ImpactSeverity.CRITICAL,
            impact_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.impact_category == ImpactCategory.PERFORMANCE
        assert r.customer_tier == CustomerTier.ENTERPRISE
        assert r.impact_severity == ImpactSeverity.CRITICAL
        assert r.impact_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_impact
# ---------------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact(
            incident_id="INC-001",
            impact_severity=ImpactSeverity.CRITICAL,
        )
        result = eng.get_impact(r.id)
        assert result is not None
        assert result.impact_severity == ImpactSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# ---------------------------------------------------------------------------
# list_impacts
# ---------------------------------------------------------------------------


class TestListImpacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001")
        eng.record_impact(incident_id="INC-002")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_category=ImpactCategory.BILLING,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_category=ImpactCategory.AVAILABILITY,
        )
        results = eng.list_impacts(category=ImpactCategory.BILLING)
        assert len(results) == 1

    def test_filter_by_tier(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            customer_tier=CustomerTier.ENTERPRISE,
        )
        eng.record_impact(
            incident_id="INC-002",
            customer_tier=CustomerTier.FREE,
        )
        results = eng.list_impacts(tier=CustomerTier.ENTERPRISE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001", service="api")
        eng.record_impact(incident_id="INC-002", service="web")
        results = eng.list_impacts(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001", team="sre")
        eng.record_impact(incident_id="INC-002", team="platform")
        results = eng.list_impacts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_impact(incident_id=f"INC-{i}")
        assert len(eng.list_impacts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_detail
# ---------------------------------------------------------------------------


class TestAddDetail:
    def test_basic(self):
        eng = _engine()
        d = eng.add_detail(
            incident_id="INC-001",
            impact_category=ImpactCategory.PERFORMANCE,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Performance within limits",
        )
        assert d.incident_id == "INC-001"
        assert d.impact_category == ImpactCategory.PERFORMANCE
        assert d.value == 75.0
        assert d.threshold == 80.0
        assert d.breached is False
        assert d.description == "Performance within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_detail(incident_id=f"INC-{i}")
        assert len(eng._details) == 2


# ---------------------------------------------------------------------------
# analyze_customer_impact
# ---------------------------------------------------------------------------


class TestAnalyzeCustomerImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_category=ImpactCategory.AVAILABILITY,
            impact_score=70.0,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_category=ImpactCategory.AVAILABILITY,
            impact_score=90.0,
        )
        result = eng.analyze_customer_impact()
        assert "availability" in result
        assert result["availability"]["count"] == 2
        assert result["availability"]["avg_impact_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_customer_impact() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_incidents
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactIncidents:
    def test_detects_high_impact(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_severity=ImpactSeverity.CRITICAL,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_severity=ImpactSeverity.MINOR,
        )
        results = eng.identify_high_impact_incidents()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_incidents() == []


# ---------------------------------------------------------------------------
# rank_by_impact_score
# ---------------------------------------------------------------------------


class TestRankByImpactScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001", service="api", impact_score=90.0)
        eng.record_impact(incident_id="INC-002", service="api", impact_score=80.0)
        eng.record_impact(incident_id="INC-003", service="web", impact_score=50.0)
        results = eng.rank_by_impact_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_impact_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# ---------------------------------------------------------------------------
# detect_impact_patterns
# ---------------------------------------------------------------------------


class TestDetectImpactPatterns:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_detail(incident_id="INC-001", value=val)
        result = eng.detect_impact_patterns()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_detail(incident_id="INC-001", value=val)
        result = eng.detect_impact_patterns()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_patterns()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_category=ImpactCategory.AVAILABILITY,
            impact_severity=ImpactSeverity.CRITICAL,
            impact_score=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, CustomerImpactReport)
        assert report.total_records == 1
        assert report.high_impact_incidents == 1
        assert report.avg_impact_score == 50.0
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
        eng.record_impact(incident_id="INC-001")
        eng.add_detail(incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._details) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_details"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_category=ImpactCategory.BILLING,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_incidents"] == 1
        assert "billing" in stats["category_distribution"]
