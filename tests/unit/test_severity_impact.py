"""Tests for shieldops.incidents.severity_impact — SeverityImpactAnalyzer."""

from __future__ import annotations

from shieldops.incidents.severity_impact import (
    ImpactCorrelation,
    ImpactDimension,
    ImpactScope,
    ImpactSeverity,
    SeverityImpactAnalyzer,
    SeverityImpactRecord,
    SeverityImpactReport,
)


def _engine(**kw) -> SeverityImpactAnalyzer:
    return SeverityImpactAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_revenue(self):
        assert ImpactDimension.REVENUE == "revenue"

    def test_dimension_customer_experience(self):
        assert ImpactDimension.CUSTOMER_EXPERIENCE == "customer_experience"

    def test_dimension_operational_capacity(self):
        assert ImpactDimension.OPERATIONAL_CAPACITY == "operational_capacity"

    def test_dimension_data_integrity(self):
        assert ImpactDimension.DATA_INTEGRITY == "data_integrity"

    def test_dimension_reputation(self):
        assert ImpactDimension.REPUTATION == "reputation"

    def test_severity_catastrophic(self):
        assert ImpactSeverity.CATASTROPHIC == "catastrophic"

    def test_severity_severe(self):
        assert ImpactSeverity.SEVERE == "severe"

    def test_severity_significant(self):
        assert ImpactSeverity.SIGNIFICANT == "significant"

    def test_severity_moderate(self):
        assert ImpactSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert ImpactSeverity.MINOR == "minor"

    def test_scope_platform_wide(self):
        assert ImpactScope.PLATFORM_WIDE == "platform_wide"

    def test_scope_multi_service(self):
        assert ImpactScope.MULTI_SERVICE == "multi_service"

    def test_scope_single_service(self):
        assert ImpactScope.SINGLE_SERVICE == "single_service"

    def test_scope_single_component(self):
        assert ImpactScope.SINGLE_COMPONENT == "single_component"

    def test_scope_isolated(self):
        assert ImpactScope.ISOLATED == "isolated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_severity_impact_record_defaults(self):
        r = SeverityImpactRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.impact_dimension == ImpactDimension.REVENUE
        assert r.impact_severity == ImpactSeverity.MINOR
        assert r.impact_scope == ImpactScope.ISOLATED
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_correlation_defaults(self):
        c = ImpactCorrelation()
        assert c.id
        assert c.incident_id == ""
        assert c.impact_dimension == ImpactDimension.REVENUE
        assert c.correlation_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_severity_impact_report_defaults(self):
        r = SeverityImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_correlations == 0
        assert r.high_impact_count == 0
        assert r.avg_impact_score == 0.0
        assert r.by_dimension == {}
        assert r.by_severity == {}
        assert r.by_scope == {}
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
            impact_dimension=ImpactDimension.REVENUE,
            impact_severity=ImpactSeverity.CATASTROPHIC,
            impact_scope=ImpactScope.PLATFORM_WIDE,
            impact_score=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.impact_dimension == ImpactDimension.REVENUE
        assert r.impact_severity == ImpactSeverity.CATASTROPHIC
        assert r.impact_scope == ImpactScope.PLATFORM_WIDE
        assert r.impact_score == 95.0
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
            impact_score=85.0,
        )
        result = eng.get_impact(r.id)
        assert result is not None
        assert result.impact_score == 85.0

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

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_dimension=ImpactDimension.REVENUE,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_dimension=ImpactDimension.REPUTATION,
        )
        results = eng.list_impacts(dimension=ImpactDimension.REVENUE)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_severity=ImpactSeverity.CATASTROPHIC,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_severity=ImpactSeverity.MINOR,
        )
        results = eng.list_impacts(severity=ImpactSeverity.CATASTROPHIC)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001", service="api-gw")
        eng.record_impact(incident_id="INC-002", service="auth-svc")
        results = eng.list_impacts(service="api-gw")
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
# add_correlation
# ---------------------------------------------------------------------------


class TestAddCorrelation:
    def test_basic(self):
        eng = _engine()
        c = eng.add_correlation(
            incident_id="INC-001",
            impact_dimension=ImpactDimension.CUSTOMER_EXPERIENCE,
            correlation_score=0.92,
            threshold=0.8,
            breached=True,
            description="High customer impact",
        )
        assert c.incident_id == "INC-001"
        assert c.impact_dimension == ImpactDimension.CUSTOMER_EXPERIENCE
        assert c.correlation_score == 0.92
        assert c.threshold == 0.8
        assert c.breached is True
        assert c.description == "High customer impact"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_correlation(incident_id=f"INC-{i}")
        assert len(eng._correlations) == 2


# ---------------------------------------------------------------------------
# analyze_impact_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeImpactDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_dimension=ImpactDimension.REVENUE,
            impact_score=80.0,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_dimension=ImpactDimension.REVENUE,
            impact_score=60.0,
        )
        result = eng.analyze_impact_distribution()
        assert "revenue" in result
        assert result["revenue"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_impact_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_incidents
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactIncidents:
    def test_detects_high_impact(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_severity=ImpactSeverity.CATASTROPHIC,
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
        eng.record_impact(
            incident_id="INC-001",
            service="api-gw",
            impact_score=90.0,
        )
        eng.record_impact(
            incident_id="INC-002",
            service="api-gw",
            impact_score=80.0,
        )
        eng.record_impact(
            incident_id="INC-003",
            service="auth-svc",
            impact_score=50.0,
        )
        results = eng.rank_by_impact_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_impact_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# ---------------------------------------------------------------------------
# detect_impact_trends
# ---------------------------------------------------------------------------


class TestDetectImpactTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.add_correlation(
                incident_id="INC-001",
                correlation_score=score,
            )
        result = eng.detect_impact_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [20.0, 20.0, 80.0, 80.0]:
            eng.add_correlation(
                incident_id="INC-001",
                correlation_score=score,
            )
        result = eng.detect_impact_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_dimension=ImpactDimension.REVENUE,
            impact_severity=ImpactSeverity.CATASTROPHIC,
            impact_scope=ImpactScope.PLATFORM_WIDE,
            impact_score=95.0,
            service="api-gw",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SeverityImpactReport)
        assert report.total_records == 1
        assert report.high_impact_count == 1
        assert report.avg_impact_score == 95.0
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
        eng.add_correlation(incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._correlations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_correlations"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_dimension=ImpactDimension.REVENUE,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "revenue" in stats["dimension_distribution"]
