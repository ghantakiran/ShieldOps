"""Tests for shieldops.compliance.governance_maturity_assessor — GovernanceMaturityAssessor."""

from __future__ import annotations

from shieldops.compliance.governance_maturity_assessor import (
    AssessmentFrequency,
    GovernanceDomain,
    GovernanceMaturityAssessor,
    GovernanceMaturityReport,
    MaturityAnalysis,
    MaturityLevel,
    MaturityRecord,
)


def _engine(**kw) -> GovernanceMaturityAssessor:
    return GovernanceMaturityAssessor(**kw)


class TestEnums:
    def test_level_optimized(self):
        assert MaturityLevel.OPTIMIZED == "optimized"

    def test_level_managed(self):
        assert MaturityLevel.MANAGED == "managed"

    def test_level_defined(self):
        assert MaturityLevel.DEFINED == "defined"

    def test_level_repeatable(self):
        assert MaturityLevel.REPEATABLE == "repeatable"

    def test_level_initial(self):
        assert MaturityLevel.INITIAL == "initial"

    def test_domain_risk_management(self):
        assert GovernanceDomain.RISK_MANAGEMENT == "risk_management"

    def test_domain_policy_management(self):
        assert GovernanceDomain.POLICY_MANAGEMENT == "policy_management"

    def test_domain_compliance(self):
        assert GovernanceDomain.COMPLIANCE == "compliance"

    def test_domain_audit(self):
        assert GovernanceDomain.AUDIT == "audit"

    def test_domain_security_operations(self):
        assert GovernanceDomain.SECURITY_OPERATIONS == "security_operations"

    def test_frequency_continuous(self):
        assert AssessmentFrequency.CONTINUOUS == "continuous"

    def test_frequency_quarterly(self):
        assert AssessmentFrequency.QUARTERLY == "quarterly"

    def test_frequency_semi_annual(self):
        assert AssessmentFrequency.SEMI_ANNUAL == "semi_annual"

    def test_frequency_annual(self):
        assert AssessmentFrequency.ANNUAL == "annual"

    def test_frequency_ad_hoc(self):
        assert AssessmentFrequency.AD_HOC == "ad_hoc"


class TestModels:
    def test_record_defaults(self):
        r = MaturityRecord()
        assert r.id
        assert r.domain_name == ""
        assert r.maturity_level == MaturityLevel.OPTIMIZED
        assert r.governance_domain == GovernanceDomain.RISK_MANAGEMENT
        assert r.assessment_frequency == AssessmentFrequency.CONTINUOUS
        assert r.maturity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = MaturityAnalysis()
        assert a.id
        assert a.domain_name == ""
        assert a.maturity_level == MaturityLevel.OPTIMIZED
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = GovernanceMaturityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_maturity_score == 0.0
        assert r.by_level == {}
        assert r.by_domain == {}
        assert r.by_frequency == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_maturity(
            domain_name="risk-management-program",
            maturity_level=MaturityLevel.MANAGED,
            governance_domain=GovernanceDomain.RISK_MANAGEMENT,
            assessment_frequency=AssessmentFrequency.QUARTERLY,
            maturity_score=85.0,
            service="grc-svc",
            team="compliance",
        )
        assert r.domain_name == "risk-management-program"
        assert r.maturity_level == MaturityLevel.MANAGED
        assert r.maturity_score == 85.0
        assert r.service == "grc-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_maturity(domain_name=f"dom-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_maturity(domain_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_maturity(domain_name="a")
        eng.record_maturity(domain_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_maturity_level(self):
        eng = _engine()
        eng.record_maturity(domain_name="a", maturity_level=MaturityLevel.OPTIMIZED)
        eng.record_maturity(domain_name="b", maturity_level=MaturityLevel.INITIAL)
        assert len(eng.list_records(maturity_level=MaturityLevel.OPTIMIZED)) == 1

    def test_filter_by_governance_domain(self):
        eng = _engine()
        eng.record_maturity(domain_name="a", governance_domain=GovernanceDomain.RISK_MANAGEMENT)
        eng.record_maturity(domain_name="b", governance_domain=GovernanceDomain.AUDIT)
        assert len(eng.list_records(governance_domain=GovernanceDomain.RISK_MANAGEMENT)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_maturity(domain_name="a", team="sec")
        eng.record_maturity(domain_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_maturity(domain_name=f"d-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            domain_name="test",
            analysis_score=88.5,
            breached=True,
            description="maturity gap",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(domain_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_maturity(
            domain_name="a",
            maturity_level=MaturityLevel.OPTIMIZED,
            maturity_score=90.0,
        )
        eng.record_maturity(
            domain_name="b",
            maturity_level=MaturityLevel.OPTIMIZED,
            maturity_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "optimized" in result
        assert result["optimized"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_maturity(domain_name="a", maturity_score=60.0)
        eng.record_maturity(domain_name="b", maturity_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_maturity(domain_name="a", maturity_score=50.0)
        eng.record_maturity(domain_name="b", maturity_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["maturity_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_maturity(domain_name="a", service="auth", maturity_score=90.0)
        eng.record_maturity(domain_name="b", service="api", maturity_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(domain_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(domain_name="a", analysis_score=20.0)
        eng.add_analysis(domain_name="b", analysis_score=20.0)
        eng.add_analysis(domain_name="c", analysis_score=80.0)
        eng.add_analysis(domain_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_maturity(domain_name="test", maturity_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_maturity(domain_name="test")
        eng.add_analysis(domain_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_maturity(domain_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
