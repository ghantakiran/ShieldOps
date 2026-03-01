"""Tests for shieldops.compliance.policy_coverage — PolicyCoverageAnalyzer."""

from __future__ import annotations

from shieldops.compliance.policy_coverage import (
    CoverageAssessment,
    CoverageStatus,
    PolicyCoverageAnalyzer,
    PolicyCoverageRecord,
    PolicyCoverageReport,
    PolicyScope,
    PolicyType,
)


def _engine(**kw) -> PolicyCoverageAnalyzer:
    return PolicyCoverageAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_policy_scope_organization_wide(self):
        assert PolicyScope.ORGANIZATION_WIDE == "organization_wide"

    def test_policy_scope_department(self):
        assert PolicyScope.DEPARTMENT == "department"

    def test_policy_scope_team(self):
        assert PolicyScope.TEAM == "team"

    def test_policy_scope_service(self):
        assert PolicyScope.SERVICE == "service"

    def test_policy_scope_environment(self):
        assert PolicyScope.ENVIRONMENT == "environment"

    def test_coverage_status_fully_covered(self):
        assert CoverageStatus.FULLY_COVERED == "fully_covered"

    def test_coverage_status_partially_covered(self):
        assert CoverageStatus.PARTIALLY_COVERED == "partially_covered"

    def test_coverage_status_gap_identified(self):
        assert CoverageStatus.GAP_IDENTIFIED == "gap_identified"

    def test_coverage_status_not_applicable(self):
        assert CoverageStatus.NOT_APPLICABLE == "not_applicable"

    def test_coverage_status_pending(self):
        assert CoverageStatus.PENDING == "pending"

    def test_policy_type_access_control(self):
        assert PolicyType.ACCESS_CONTROL == "access_control"

    def test_policy_type_data_handling(self):
        assert PolicyType.DATA_HANDLING == "data_handling"

    def test_policy_type_change_management(self):
        assert PolicyType.CHANGE_MANAGEMENT == "change_management"

    def test_policy_type_incident_response(self):
        assert PolicyType.INCIDENT_RESPONSE == "incident_response"

    def test_policy_type_encryption(self):
        assert PolicyType.ENCRYPTION == "encryption"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_policy_coverage_record_defaults(self):
        r = PolicyCoverageRecord()
        assert r.id
        assert r.policy_name == ""
        assert r.policy_scope == PolicyScope.ORGANIZATION_WIDE
        assert r.coverage_status == CoverageStatus.PENDING
        assert r.policy_type == PolicyType.ACCESS_CONTROL
        assert r.coverage_pct == 0.0
        assert r.owner == ""
        assert r.created_at > 0

    def test_coverage_assessment_defaults(self):
        a = CoverageAssessment()
        assert a.id
        assert a.assessment_name == ""
        assert a.policy_scope == PolicyScope.ORGANIZATION_WIDE
        assert a.assessment_score == 0.0
        assert a.policies_evaluated == 0
        assert a.description == ""
        assert a.created_at > 0

    def test_policy_coverage_report_defaults(self):
        r = PolicyCoverageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.covered_scopes == 0
        assert r.avg_coverage_pct == 0.0
        assert r.by_scope == {}
        assert r.by_status == {}
        assert r.by_type == {}
        assert r.gap_policies == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_coverage
# ---------------------------------------------------------------------------


class TestRecordCoverage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_coverage(
            policy_name="access-policy-01",
            policy_scope=PolicyScope.DEPARTMENT,
            coverage_status=CoverageStatus.FULLY_COVERED,
            policy_type=PolicyType.ACCESS_CONTROL,
            coverage_pct=95.0,
            owner="security-team",
        )
        assert r.policy_name == "access-policy-01"
        assert r.policy_scope == PolicyScope.DEPARTMENT
        assert r.coverage_status == CoverageStatus.FULLY_COVERED
        assert r.policy_type == PolicyType.ACCESS_CONTROL
        assert r.coverage_pct == 95.0
        assert r.owner == "security-team"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_coverage(policy_name=f"policy-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_coverage
# ---------------------------------------------------------------------------


class TestGetCoverage:
    def test_found(self):
        eng = _engine()
        r = eng.record_coverage(
            policy_name="access-policy-01",
            policy_scope=PolicyScope.TEAM,
        )
        result = eng.get_coverage(r.id)
        assert result is not None
        assert result.policy_scope == PolicyScope.TEAM

    def test_not_found(self):
        eng = _engine()
        assert eng.get_coverage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_coverages
# ---------------------------------------------------------------------------


class TestListCoverages:
    def test_list_all(self):
        eng = _engine()
        eng.record_coverage(policy_name="policy-1")
        eng.record_coverage(policy_name="policy-2")
        assert len(eng.list_coverages()) == 2

    def test_filter_by_policy_scope(self):
        eng = _engine()
        eng.record_coverage(
            policy_name="policy-1",
            policy_scope=PolicyScope.ORGANIZATION_WIDE,
        )
        eng.record_coverage(
            policy_name="policy-2",
            policy_scope=PolicyScope.TEAM,
        )
        results = eng.list_coverages(policy_scope=PolicyScope.ORGANIZATION_WIDE)
        assert len(results) == 1

    def test_filter_by_coverage_status(self):
        eng = _engine()
        eng.record_coverage(
            policy_name="policy-1",
            coverage_status=CoverageStatus.FULLY_COVERED,
        )
        eng.record_coverage(
            policy_name="policy-2",
            coverage_status=CoverageStatus.GAP_IDENTIFIED,
        )
        results = eng.list_coverages(coverage_status=CoverageStatus.FULLY_COVERED)
        assert len(results) == 1

    def test_filter_by_owner(self):
        eng = _engine()
        eng.record_coverage(policy_name="policy-1", owner="security-team")
        eng.record_coverage(policy_name="policy-2", owner="platform-team")
        results = eng.list_coverages(owner="security-team")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_coverage(policy_name=f"policy-{i}")
        assert len(eng.list_coverages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            assessment_name="q1-coverage-review",
            policy_scope=PolicyScope.SERVICE,
            assessment_score=88.5,
            policies_evaluated=12,
            description="Quarterly policy coverage assessment",
        )
        assert a.assessment_name == "q1-coverage-review"
        assert a.policy_scope == PolicyScope.SERVICE
        assert a.assessment_score == 88.5
        assert a.policies_evaluated == 12

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(assessment_name=f"assessment-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_policy_coverage
# ---------------------------------------------------------------------------


class TestAnalyzePolicyCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_coverage(
            policy_name="policy-1",
            policy_scope=PolicyScope.ORGANIZATION_WIDE,
            coverage_pct=90.0,
        )
        eng.record_coverage(
            policy_name="policy-2",
            policy_scope=PolicyScope.ORGANIZATION_WIDE,
            coverage_pct=80.0,
        )
        result = eng.analyze_policy_coverage()
        assert "organization_wide" in result
        assert result["organization_wide"]["count"] == 2
        assert result["organization_wide"]["avg_coverage_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_policy_coverage() == {}


# ---------------------------------------------------------------------------
# identify_coverage_gaps
# ---------------------------------------------------------------------------


class TestIdentifyCoverageGaps:
    def test_detects_gaps(self):
        eng = _engine(min_policy_coverage_pct=85.0)
        eng.record_coverage(
            policy_name="policy-1",
            coverage_pct=60.0,
        )
        eng.record_coverage(
            policy_name="policy-2",
            coverage_pct=95.0,
        )
        results = eng.identify_coverage_gaps()
        assert len(results) == 1
        assert results[0]["policy_name"] == "policy-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_coverage_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_coverage_score
# ---------------------------------------------------------------------------


class TestRankByCoverageScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_coverage(policy_name="p1", owner="security-team", coverage_pct=90.0)
        eng.record_coverage(policy_name="p2", owner="security-team", coverage_pct=80.0)
        eng.record_coverage(policy_name="p3", owner="platform-team", coverage_pct=50.0)
        results = eng.rank_by_coverage_score()
        assert len(results) == 2
        assert results[0]["owner"] == "security-team"
        assert results[0]["total_coverage"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage_score() == []


# ---------------------------------------------------------------------------
# detect_coverage_trends
# ---------------------------------------------------------------------------


class TestDetectCoverageTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_coverage(policy_name="policy-1", coverage_pct=pct)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [50.0, 50.0, 90.0, 90.0]:
            eng.record_coverage(policy_name="policy-1", coverage_pct=pct)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_coverage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_policy_coverage_pct=85.0)
        eng.record_coverage(
            policy_name="policy-1",
            policy_scope=PolicyScope.ORGANIZATION_WIDE,
            coverage_status=CoverageStatus.PARTIALLY_COVERED,
            coverage_pct=60.0,
            owner="security-team",
        )
        report = eng.generate_report()
        assert isinstance(report, PolicyCoverageReport)
        assert report.total_records == 1
        assert report.avg_coverage_pct == 60.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_coverage(policy_name="policy-1")
        eng.add_assessment(assessment_name="a1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["scope_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_coverage(
            policy_name="policy-1",
            policy_scope=PolicyScope.DEPARTMENT,
            owner="security-team",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_owners"] == 1
        assert stats["unique_policies"] == 1
        assert "department" in stats["scope_distribution"]
