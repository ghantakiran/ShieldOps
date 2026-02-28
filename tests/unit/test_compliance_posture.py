"""Tests for posture_scorer — CompliancePostureScorer."""

from __future__ import annotations

from shieldops.compliance.posture_scorer import (
    CompliancePostureScorer,
    PostureDomain,
    PostureGrade,
    PosturePolicy,
    PostureRecord,
    PostureScorerReport,
    RemediationUrgency,
)


def _engine(**kw) -> CompliancePostureScorer:
    return CompliancePostureScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PostureDomain (5)
    def test_domain_access_control(self):
        assert PostureDomain.ACCESS_CONTROL == "access_control"

    def test_domain_data_protection(self):
        assert PostureDomain.DATA_PROTECTION == "data_protection"

    def test_domain_network_security(self):
        assert PostureDomain.NETWORK_SECURITY == "network_security"

    def test_domain_logging(self):
        assert PostureDomain.LOGGING == "logging"

    def test_domain_encryption(self):
        assert PostureDomain.ENCRYPTION == "encryption"

    # PostureGrade (5)
    def test_grade_exemplary(self):
        assert PostureGrade.EXEMPLARY == "exemplary"

    def test_grade_strong(self):
        assert PostureGrade.STRONG == "strong"

    def test_grade_acceptable(self):
        assert PostureGrade.ACCEPTABLE == "acceptable"

    def test_grade_weak(self):
        assert PostureGrade.WEAK == "weak"

    def test_grade_non_compliant(self):
        assert PostureGrade.NON_COMPLIANT == "non_compliant"

    # RemediationUrgency (5)
    def test_urgency_immediate(self):
        assert RemediationUrgency.IMMEDIATE == "immediate"

    def test_urgency_high(self):
        assert RemediationUrgency.HIGH == "high"

    def test_urgency_medium(self):
        assert RemediationUrgency.MEDIUM == "medium"

    def test_urgency_low(self):
        assert RemediationUrgency.LOW == "low"

    def test_urgency_scheduled(self):
        assert RemediationUrgency.SCHEDULED == "scheduled"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_posture_record_defaults(self):
        r = PostureRecord()
        assert r.id
        assert r.domain_name == ""
        assert r.domain == PostureDomain.ACCESS_CONTROL
        assert r.grade == PostureGrade.ACCEPTABLE
        assert r.urgency == RemediationUrgency.MEDIUM
        assert r.score_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_posture_policy_defaults(self):
        r = PosturePolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.domain == PostureDomain.ACCESS_CONTROL
        assert r.grade == PostureGrade.ACCEPTABLE
        assert r.min_score_pct == 70.0
        assert r.review_frequency_days == 30.0
        assert r.created_at > 0

    def test_posture_scorer_report_defaults(self):
        r = PostureScorerReport()
        assert r.total_assessments == 0
        assert r.total_policies == 0
        assert r.strong_rate_pct == 0.0
        assert r.by_domain == {}
        assert r.by_grade == {}
        assert r.non_compliant_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_assessment
# -------------------------------------------------------------------


class TestRecordAssessment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_assessment(
            "access-mgmt",
            domain=PostureDomain.ACCESS_CONTROL,
            grade=PostureGrade.STRONG,
        )
        assert r.domain_name == "access-mgmt"
        assert r.domain == PostureDomain.ACCESS_CONTROL

    def test_with_urgency(self):
        eng = _engine()
        r = eng.record_assessment(
            "encryption-mgmt",
            urgency=RemediationUrgency.IMMEDIATE,
        )
        assert r.urgency == RemediationUrgency.IMMEDIATE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_assessment(f"domain-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_assessment
# -------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        r = eng.record_assessment("access-mgmt")
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
        eng.record_assessment("domain-a")
        eng.record_assessment("domain-b")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_domain_name(self):
        eng = _engine()
        eng.record_assessment("domain-a")
        eng.record_assessment("domain-b")
        results = eng.list_assessments(domain_name="domain-a")
        assert len(results) == 1

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_assessment(
            "domain-a",
            domain=PostureDomain.ENCRYPTION,
        )
        eng.record_assessment(
            "domain-b",
            domain=PostureDomain.LOGGING,
        )
        results = eng.list_assessments(domain=PostureDomain.ENCRYPTION)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "access-review",
            domain=PostureDomain.ACCESS_CONTROL,
            grade=PostureGrade.STRONG,
            min_score_pct=80.0,
            review_frequency_days=14.0,
        )
        assert p.policy_name == "access-review"
        assert p.min_score_pct == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_posture_health
# -------------------------------------------------------------------


class TestAnalyzePostureHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            "domain-a",
            grade=PostureGrade.STRONG,
        )
        eng.record_assessment(
            "domain-a",
            grade=PostureGrade.WEAK,
        )
        result = eng.analyze_posture_health("domain-a")
        assert result["domain_name"] == "domain-a"
        assert result["assessment_count"] == 2
        assert result["strong_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_posture_health("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_non_compliant
# -------------------------------------------------------------------


class TestIdentifyNonCompliant:
    def test_with_non_compliant(self):
        eng = _engine()
        eng.record_assessment(
            "domain-a",
            grade=PostureGrade.WEAK,
        )
        eng.record_assessment(
            "domain-a",
            grade=PostureGrade.WEAK,
        )
        eng.record_assessment(
            "domain-b",
            grade=PostureGrade.STRONG,
        )
        results = eng.identify_non_compliant()
        assert len(results) == 1
        assert results[0]["domain_name"] == "domain-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant() == []


# -------------------------------------------------------------------
# rank_by_score
# -------------------------------------------------------------------


class TestRankByScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment("domain-a", score_pct=90.0)
        eng.record_assessment("domain-a", score_pct=80.0)
        eng.record_assessment("domain-b", score_pct=50.0)
        results = eng.rank_by_score()
        assert results[0]["domain_name"] == "domain-a"
        assert results[0]["avg_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# -------------------------------------------------------------------
# detect_posture_gaps
# -------------------------------------------------------------------


class TestDetectPostureGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_assessment(
                "domain-a",
                grade=PostureGrade.WEAK,
            )
        eng.record_assessment(
            "domain-b",
            grade=PostureGrade.STRONG,
        )
        results = eng.detect_posture_gaps()
        assert len(results) == 1
        assert results[0]["domain_name"] == "domain-a"
        assert results[0]["gap_detected"] is True

    def test_no_gaps(self):
        eng = _engine()
        eng.record_assessment(
            "domain-a",
            grade=PostureGrade.WEAK,
        )
        assert eng.detect_posture_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            "domain-a",
            grade=PostureGrade.STRONG,
        )
        eng.record_assessment(
            "domain-b",
            grade=PostureGrade.WEAK,
        )
        eng.record_assessment(
            "domain-b",
            grade=PostureGrade.WEAK,
        )
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_assessments == 3
        assert report.total_policies == 1
        assert report.by_domain != {}
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
        eng.record_assessment("domain-a")
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
        assert stats["domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_assessment(
            "domain-a",
            domain=PostureDomain.ACCESS_CONTROL,
        )
        eng.record_assessment(
            "domain-b",
            domain=PostureDomain.ENCRYPTION,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_assessments"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_domains"] == 2
