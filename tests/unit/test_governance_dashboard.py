"""Tests for governance_dashboard — PlatformGovernanceDashboard."""

from __future__ import annotations

from shieldops.policy.governance_dashboard import (
    GovernanceArea,
    GovernanceDashboardReport,
    GovernancePolicy,
    GovernanceRecord,
    GovernanceStatus,
    GovernanceTrend,
    PlatformGovernanceDashboard,
)


def _engine(**kw) -> PlatformGovernanceDashboard:
    return PlatformGovernanceDashboard(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # GovernanceArea (5)
    def test_area_security(self):
        assert GovernanceArea.SECURITY == "security"

    def test_area_compliance(self):
        assert GovernanceArea.COMPLIANCE == "compliance"

    def test_area_cost(self):
        assert GovernanceArea.COST == "cost"

    def test_area_reliability(self):
        assert GovernanceArea.RELIABILITY == "reliability"

    def test_area_operational(self):
        assert GovernanceArea.OPERATIONAL == "operational"

    # GovernanceStatus (5)
    def test_status_excellent(self):
        assert GovernanceStatus.EXCELLENT == "excellent"

    def test_status_good(self):
        assert GovernanceStatus.GOOD == "good"

    def test_status_needs_attention(self):
        assert GovernanceStatus.NEEDS_ATTENTION == "needs_attention"

    def test_status_at_risk(self):
        assert GovernanceStatus.AT_RISK == "at_risk"

    def test_status_critical(self):
        assert GovernanceStatus.CRITICAL == "critical"

    # GovernanceTrend (5)
    def test_trend_improving(self):
        assert GovernanceTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert GovernanceTrend.STABLE == "stable"

    def test_trend_declining(self):
        assert GovernanceTrend.DECLINING == "declining"

    def test_trend_volatile(self):
        assert GovernanceTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert GovernanceTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_governance_record_defaults(self):
        r = GovernanceRecord()
        assert r.id
        assert r.area_name == ""
        assert r.area == GovernanceArea.SECURITY
        assert r.status == GovernanceStatus.GOOD
        assert r.trend == GovernanceTrend.STABLE
        assert r.score_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_governance_policy_defaults(self):
        r = GovernancePolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.area == GovernanceArea.SECURITY
        assert r.status == GovernanceStatus.GOOD
        assert r.min_score_pct == 70.0
        assert r.review_cadence_days == 7.0
        assert r.created_at > 0

    def test_governance_report_defaults(self):
        r = GovernanceDashboardReport()
        assert r.total_assessments == 0
        assert r.total_policies == 0
        assert r.excellent_rate_pct == 0.0
        assert r.by_area == {}
        assert r.by_status == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_assessment
# -------------------------------------------------------------------


class TestRecordAssessment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_assessment(
            "security-posture",
            area=GovernanceArea.SECURITY,
            status=GovernanceStatus.EXCELLENT,
        )
        assert r.area_name == "security-posture"
        assert r.area == GovernanceArea.SECURITY

    def test_with_trend(self):
        eng = _engine()
        r = eng.record_assessment(
            "cost-mgmt",
            trend=GovernanceTrend.IMPROVING,
        )
        assert r.trend == GovernanceTrend.IMPROVING

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_assessment(f"area-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_assessment
# -------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        r = eng.record_assessment("security-posture")
        assert eng.get_assessment(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# -------------------------------------------------------------------
# list_assessments
# -------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.record_assessment("area-a")
        eng.record_assessment("area-b")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_area_name(self):
        eng = _engine()
        eng.record_assessment("area-a")
        eng.record_assessment("area-b")
        results = eng.list_assessments(area_name="area-a")
        assert len(results) == 1

    def test_filter_by_area(self):
        eng = _engine()
        eng.record_assessment(
            "area-a",
            area=GovernanceArea.COST,
        )
        eng.record_assessment(
            "area-b",
            area=GovernanceArea.RELIABILITY,
        )
        results = eng.list_assessments(area=GovernanceArea.COST)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "security-review",
            area=GovernanceArea.SECURITY,
            status=GovernanceStatus.EXCELLENT,
            min_score_pct=85.0,
            review_cadence_days=7.0,
        )
        assert p.policy_name == "security-review"
        assert p.min_score_pct == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_governance_health
# -------------------------------------------------------------------


class TestAnalyzeGovernanceHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            "area-a",
            status=GovernanceStatus.EXCELLENT,
        )
        eng.record_assessment(
            "area-a",
            status=GovernanceStatus.CRITICAL,
        )
        result = eng.analyze_governance_health("area-a")
        assert result["area_name"] == "area-a"
        assert result["assessment_count"] == 2
        assert result["excellent_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_governance_health("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_at_risk_areas
# -------------------------------------------------------------------


class TestIdentifyAtRiskAreas:
    def test_with_at_risk(self):
        eng = _engine()
        eng.record_assessment(
            "area-a",
            status=GovernanceStatus.AT_RISK,
        )
        eng.record_assessment(
            "area-a",
            status=GovernanceStatus.AT_RISK,
        )
        eng.record_assessment(
            "area-b",
            status=GovernanceStatus.GOOD,
        )
        results = eng.identify_at_risk_areas()
        assert len(results) == 1
        assert results[0]["area_name"] == "area-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_at_risk_areas() == []


# -------------------------------------------------------------------
# rank_by_governance_score
# -------------------------------------------------------------------


class TestRankByGovernanceScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment("area-a", score_pct=90.0)
        eng.record_assessment("area-a", score_pct=80.0)
        eng.record_assessment("area-b", score_pct=50.0)
        results = eng.rank_by_governance_score()
        assert results[0]["area_name"] == "area-a"
        assert results[0]["avg_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_governance_score() == []


# -------------------------------------------------------------------
# detect_governance_gaps
# -------------------------------------------------------------------


class TestDetectGovernanceGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_assessment(
                "area-a",
                status=GovernanceStatus.CRITICAL,
            )
        eng.record_assessment(
            "area-b",
            status=GovernanceStatus.GOOD,
        )
        results = eng.detect_governance_gaps()
        assert len(results) == 1
        assert results[0]["area_name"] == "area-a"
        assert results[0]["gap_detected"] is True

    def test_no_gaps(self):
        eng = _engine()
        eng.record_assessment(
            "area-a",
            status=GovernanceStatus.CRITICAL,
        )
        assert eng.detect_governance_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            "area-a",
            status=GovernanceStatus.EXCELLENT,
        )
        eng.record_assessment(
            "area-b",
            status=GovernanceStatus.CRITICAL,
        )
        eng.record_assessment(
            "area-b",
            status=GovernanceStatus.CRITICAL,
        )
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_assessments == 3
        assert report.total_policies == 1
        assert report.by_area != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_assessments == 0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_assessment("area-a")
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
        assert stats["total_assessments"] == 0
        assert stats["total_policies"] == 0
        assert stats["area_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_assessment(
            "area-a",
            area=GovernanceArea.SECURITY,
        )
        eng.record_assessment(
            "area-b",
            area=GovernanceArea.COST,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_assessments"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_areas"] == 2
