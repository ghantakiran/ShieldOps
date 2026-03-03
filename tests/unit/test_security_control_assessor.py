"""Tests for shieldops.audit.security_control_assessor — SecurityControlAssessor."""

from __future__ import annotations

from shieldops.audit.security_control_assessor import (
    AssessmentMethod,
    AssessmentResult,
    ControlAnalysis,
    ControlAssessmentReport,
    ControlDomain,
    ControlRecord,
    SecurityControlAssessor,
)


def _engine(**kw) -> SecurityControlAssessor:
    return SecurityControlAssessor(**kw)


class TestEnums:
    def test_domain_access_management(self):
        assert ControlDomain.ACCESS_MANAGEMENT == "access_management"

    def test_domain_data_security(self):
        assert ControlDomain.DATA_SECURITY == "data_security"

    def test_domain_network_security(self):
        assert ControlDomain.NETWORK_SECURITY == "network_security"

    def test_domain_application_security(self):
        assert ControlDomain.APPLICATION_SECURITY == "application_security"

    def test_domain_operational_security(self):
        assert ControlDomain.OPERATIONAL_SECURITY == "operational_security"

    def test_result_effective(self):
        assert AssessmentResult.EFFECTIVE == "effective"

    def test_result_partially_effective(self):
        assert AssessmentResult.PARTIALLY_EFFECTIVE == "partially_effective"

    def test_result_ineffective(self):
        assert AssessmentResult.INEFFECTIVE == "ineffective"

    def test_result_not_tested(self):
        assert AssessmentResult.NOT_TESTED == "not_tested"

    def test_result_not_applicable(self):
        assert AssessmentResult.NOT_APPLICABLE == "not_applicable"

    def test_method_automated(self):
        assert AssessmentMethod.AUTOMATED == "automated"

    def test_method_manual(self):
        assert AssessmentMethod.MANUAL == "manual"

    def test_method_hybrid(self):
        assert AssessmentMethod.HYBRID == "hybrid"

    def test_method_continuous(self):
        assert AssessmentMethod.CONTINUOUS == "continuous"

    def test_method_sampling(self):
        assert AssessmentMethod.SAMPLING == "sampling"


class TestModels:
    def test_record_defaults(self):
        r = ControlRecord()
        assert r.id
        assert r.control_name == ""
        assert r.control_domain == ControlDomain.ACCESS_MANAGEMENT
        assert r.assessment_result == AssessmentResult.EFFECTIVE
        assert r.assessment_method == AssessmentMethod.AUTOMATED
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ControlAnalysis()
        assert a.id
        assert a.control_name == ""
        assert a.control_domain == ControlDomain.ACCESS_MANAGEMENT
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ControlAssessmentReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_domain == {}
        assert r.by_result == {}
        assert r.by_method == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_control(
            control_name="mfa-enforcement",
            control_domain=ControlDomain.ACCESS_MANAGEMENT,
            assessment_result=AssessmentResult.EFFECTIVE,
            assessment_method=AssessmentMethod.CONTINUOUS,
            effectiveness_score=85.0,
            service="iam-svc",
            team="security",
        )
        assert r.control_name == "mfa-enforcement"
        assert r.control_domain == ControlDomain.ACCESS_MANAGEMENT
        assert r.effectiveness_score == 85.0
        assert r.service == "iam-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_control(control_name=f"ctrl-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_control(control_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_control(control_name="a")
        eng.record_control(control_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_control_domain(self):
        eng = _engine()
        eng.record_control(control_name="a", control_domain=ControlDomain.ACCESS_MANAGEMENT)
        eng.record_control(control_name="b", control_domain=ControlDomain.DATA_SECURITY)
        assert len(eng.list_records(control_domain=ControlDomain.ACCESS_MANAGEMENT)) == 1

    def test_filter_by_assessment_result(self):
        eng = _engine()
        eng.record_control(control_name="a", assessment_result=AssessmentResult.EFFECTIVE)
        eng.record_control(control_name="b", assessment_result=AssessmentResult.INEFFECTIVE)
        assert len(eng.list_records(assessment_result=AssessmentResult.EFFECTIVE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_control(control_name="a", team="sec")
        eng.record_control(control_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_control(control_name=f"c-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            control_name="test",
            analysis_score=88.5,
            breached=True,
            description="control gap",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(control_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_control(
            control_name="a",
            control_domain=ControlDomain.ACCESS_MANAGEMENT,
            effectiveness_score=90.0,
        )
        eng.record_control(
            control_name="b",
            control_domain=ControlDomain.ACCESS_MANAGEMENT,
            effectiveness_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "access_management" in result
        assert result["access_management"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_control(control_name="a", effectiveness_score=60.0)
        eng.record_control(control_name="b", effectiveness_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_control(control_name="a", effectiveness_score=50.0)
        eng.record_control(control_name="b", effectiveness_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_control(control_name="a", service="auth", effectiveness_score=90.0)
        eng.record_control(control_name="b", service="api", effectiveness_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(control_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(control_name="a", analysis_score=20.0)
        eng.add_analysis(control_name="b", analysis_score=20.0)
        eng.add_analysis(control_name="c", analysis_score=80.0)
        eng.add_analysis(control_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_control(control_name="test", effectiveness_score=50.0)
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
        eng.record_control(control_name="test")
        eng.add_analysis(control_name="test")
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
        eng.record_control(control_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
