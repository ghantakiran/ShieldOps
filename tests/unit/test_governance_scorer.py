"""Tests for shieldops.policy.governance_scorer — PlatformGovernanceScorer."""

from __future__ import annotations

from shieldops.policy.governance_scorer import (
    GovernanceDomain,
    GovernanceGrade,
    GovernanceMaturity,
    GovernanceMetric,
    GovernanceRecord,
    GovernanceScorerReport,
    PlatformGovernanceScorer,
)


def _engine(**kw) -> PlatformGovernanceScorer:
    return PlatformGovernanceScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # GovernanceDomain (5)
    def test_domain_access_management(self):
        assert GovernanceDomain.ACCESS_MANAGEMENT == "access_management"

    def test_domain_change_control(self):
        assert GovernanceDomain.CHANGE_CONTROL == "change_control"

    def test_domain_risk_management(self):
        assert GovernanceDomain.RISK_MANAGEMENT == "risk_management"

    def test_domain_compliance_oversight(self):
        assert GovernanceDomain.COMPLIANCE_OVERSIGHT == "compliance_oversight"

    def test_domain_incident_governance(self):
        assert GovernanceDomain.INCIDENT_GOVERNANCE == "incident_governance"

    # GovernanceGrade (5)
    def test_grade_excellent(self):
        assert GovernanceGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert GovernanceGrade.GOOD == "good"

    def test_grade_adequate(self):
        assert GovernanceGrade.ADEQUATE == "adequate"

    def test_grade_poor(self):
        assert GovernanceGrade.POOR == "poor"

    def test_grade_failing(self):
        assert GovernanceGrade.FAILING == "failing"

    # GovernanceMaturity (5)
    def test_maturity_optimized(self):
        assert GovernanceMaturity.OPTIMIZED == "optimized"

    def test_maturity_managed(self):
        assert GovernanceMaturity.MANAGED == "managed"

    def test_maturity_defined(self):
        assert GovernanceMaturity.DEFINED == "defined"

    def test_maturity_developing(self):
        assert GovernanceMaturity.DEVELOPING == "developing"

    def test_maturity_initial(self):
        assert GovernanceMaturity.INITIAL == "initial"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_governance_record_defaults(self):
        r = GovernanceRecord()
        assert r.id
        assert r.domain_name == ""
        assert r.domain == GovernanceDomain.ACCESS_MANAGEMENT
        assert r.grade == GovernanceGrade.ADEQUATE
        assert r.maturity == GovernanceMaturity.DEFINED
        assert r.score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_governance_metric_defaults(self):
        r = GovernanceMetric()
        assert r.id
        assert r.domain_name == ""
        assert r.domain == GovernanceDomain.ACCESS_MANAGEMENT
        assert r.grade == GovernanceGrade.ADEQUATE
        assert r.min_score == 70.0
        assert r.review_frequency_days == 30.0
        assert r.created_at > 0

    def test_governance_scorer_report_defaults(self):
        r = GovernanceScorerReport()
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.passing_rate_pct == 0.0
        assert r.by_domain == {}
        assert r.by_grade == {}
        assert r.weak_domain_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_governance
# -------------------------------------------------------------------


class TestRecordGovernance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_governance(
            "access-mgmt",
            domain=GovernanceDomain.ACCESS_MANAGEMENT,
            grade=GovernanceGrade.EXCELLENT,
        )
        assert r.domain_name == "access-mgmt"
        assert r.domain == GovernanceDomain.ACCESS_MANAGEMENT

    def test_with_maturity(self):
        eng = _engine()
        r = eng.record_governance(
            "change-ctrl",
            maturity=GovernanceMaturity.OPTIMIZED,
        )
        assert r.maturity == GovernanceMaturity.OPTIMIZED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_governance(f"domain-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_governance
# -------------------------------------------------------------------


class TestGetGovernance:
    def test_found(self):
        eng = _engine()
        r = eng.record_governance("domain-a")
        assert eng.get_governance(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_governance("nonexistent") is None


# -------------------------------------------------------------------
# list_governance_records
# -------------------------------------------------------------------


class TestListGovernanceRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_governance("domain-a")
        eng.record_governance("domain-b")
        assert len(eng.list_governance_records()) == 2

    def test_filter_by_domain_name(self):
        eng = _engine()
        eng.record_governance("domain-a")
        eng.record_governance("domain-b")
        results = eng.list_governance_records(domain_name="domain-a")
        assert len(results) == 1

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_governance("domain-a", domain=GovernanceDomain.ACCESS_MANAGEMENT)
        eng.record_governance("domain-b", domain=GovernanceDomain.CHANGE_CONTROL)
        results = eng.list_governance_records(domain=GovernanceDomain.ACCESS_MANAGEMENT)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_metric
# -------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            "access-metric",
            domain=GovernanceDomain.ACCESS_MANAGEMENT,
            grade=GovernanceGrade.EXCELLENT,
            min_score=80.0,
            review_frequency_days=14.0,
        )
        assert m.domain_name == "access-metric"
        assert m.min_score == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_metric(f"metric-{i}")
        assert len(eng._metrics) == 2


# -------------------------------------------------------------------
# analyze_governance_by_domain
# -------------------------------------------------------------------


class TestAnalyzeGovernanceByDomain:
    def test_with_data(self):
        eng = _engine()
        eng.record_governance("domain-a", grade=GovernanceGrade.EXCELLENT)
        eng.record_governance("domain-a", grade=GovernanceGrade.POOR)
        result = eng.analyze_governance_by_domain("domain-a")
        assert result["domain_name"] == "domain-a"
        assert result["record_count"] == 2
        assert result["passing_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_governance_by_domain("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_weak_domains
# -------------------------------------------------------------------


class TestIdentifyWeakDomains:
    def test_with_weak(self):
        eng = _engine()
        eng.record_governance("domain-a", grade=GovernanceGrade.POOR)
        eng.record_governance("domain-a", grade=GovernanceGrade.FAILING)
        eng.record_governance("domain-b", grade=GovernanceGrade.EXCELLENT)
        results = eng.identify_weak_domains()
        assert len(results) == 1
        assert results[0]["domain_name"] == "domain-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_weak_domains() == []


# -------------------------------------------------------------------
# rank_by_governance_score
# -------------------------------------------------------------------


class TestRankByGovernanceScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_governance("domain-a", score=90.0)
        eng.record_governance("domain-a", score=80.0)
        eng.record_governance("domain-b", score=50.0)
        results = eng.rank_by_governance_score()
        assert results[0]["domain_name"] == "domain-a"
        assert results[0]["avg_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_governance_score() == []


# -------------------------------------------------------------------
# detect_governance_trends
# -------------------------------------------------------------------


class TestDetectGovernanceTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_governance("domain-a", grade=GovernanceGrade.POOR)
        eng.record_governance("domain-b", grade=GovernanceGrade.EXCELLENT)
        results = eng.detect_governance_trends()
        assert len(results) == 1
        assert results[0]["domain_name"] == "domain-a"
        assert results[0]["trend_detected"] is True

    def test_no_trends(self):
        eng = _engine()
        eng.record_governance("domain-a", grade=GovernanceGrade.POOR)
        assert eng.detect_governance_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_governance("domain-a", grade=GovernanceGrade.EXCELLENT)
        eng.record_governance("domain-b", grade=GovernanceGrade.POOR)
        eng.record_governance("domain-b", grade=GovernanceGrade.POOR)
        eng.add_metric("metric-1")
        report = eng.generate_report()
        assert report.total_records == 3
        assert report.total_metrics == 1
        assert report.by_domain != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "meets all targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_governance("domain-a")
        eng.add_metric("metric-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_governance("domain-a", domain=GovernanceDomain.ACCESS_MANAGEMENT)
        eng.record_governance("domain-b", domain=GovernanceDomain.CHANGE_CONTROL)
        eng.add_metric("metric-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_metrics"] == 1
        assert stats["unique_domains"] == 2
