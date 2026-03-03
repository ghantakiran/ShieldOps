"""Tests for shieldops.compliance.security_policy_lifecycle — SecurityPolicyLifecycle."""

from __future__ import annotations

from shieldops.compliance.security_policy_lifecycle import (
    PolicyAnalysis,
    PolicyCategory,
    PolicyLifecycleReport,
    PolicyPhase,
    PolicyRecord,
    PolicyScope,
    SecurityPolicyLifecycle,
)


def _engine(**kw) -> SecurityPolicyLifecycle:
    return SecurityPolicyLifecycle(**kw)


class TestEnums:
    def test_phase_draft(self):
        assert PolicyPhase.DRAFT == "draft"

    def test_phase_review(self):
        assert PolicyPhase.REVIEW == "review"

    def test_phase_approved(self):
        assert PolicyPhase.APPROVED == "approved"

    def test_phase_enforced(self):
        assert PolicyPhase.ENFORCED == "enforced"

    def test_phase_retired(self):
        assert PolicyPhase.RETIRED == "retired"

    def test_category_access_control(self):
        assert PolicyCategory.ACCESS_CONTROL == "access_control"

    def test_category_data_protection(self):
        assert PolicyCategory.DATA_PROTECTION == "data_protection"

    def test_category_network_security(self):
        assert PolicyCategory.NETWORK_SECURITY == "network_security"

    def test_category_incident_response(self):
        assert PolicyCategory.INCIDENT_RESPONSE == "incident_response"

    def test_category_compliance(self):
        assert PolicyCategory.COMPLIANCE == "compliance"

    def test_scope_organization(self):
        assert PolicyScope.ORGANIZATION == "organization"

    def test_scope_department(self):
        assert PolicyScope.DEPARTMENT == "department"

    def test_scope_team(self):
        assert PolicyScope.TEAM == "team"

    def test_scope_application(self):
        assert PolicyScope.APPLICATION == "application"

    def test_scope_infrastructure(self):
        assert PolicyScope.INFRASTRUCTURE == "infrastructure"


class TestModels:
    def test_record_defaults(self):
        r = PolicyRecord()
        assert r.id
        assert r.policy_name == ""
        assert r.policy_phase == PolicyPhase.DRAFT
        assert r.policy_category == PolicyCategory.ACCESS_CONTROL
        assert r.policy_scope == PolicyScope.ORGANIZATION
        assert r.compliance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PolicyAnalysis()
        assert a.id
        assert a.policy_name == ""
        assert a.policy_phase == PolicyPhase.DRAFT
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PolicyLifecycleReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_phase == {}
        assert r.by_category == {}
        assert r.by_scope == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_policy(
            policy_name="data-retention-policy",
            policy_phase=PolicyPhase.ENFORCED,
            policy_category=PolicyCategory.DATA_PROTECTION,
            policy_scope=PolicyScope.ORGANIZATION,
            compliance_score=85.0,
            service="compliance-svc",
            team="governance",
        )
        assert r.policy_name == "data-retention-policy"
        assert r.policy_phase == PolicyPhase.ENFORCED
        assert r.compliance_score == 85.0
        assert r.service == "compliance-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_policy(policy_name=f"pol-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_policy(policy_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_policy(policy_name="a")
        eng.record_policy(policy_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_policy_phase(self):
        eng = _engine()
        eng.record_policy(policy_name="a", policy_phase=PolicyPhase.DRAFT)
        eng.record_policy(policy_name="b", policy_phase=PolicyPhase.ENFORCED)
        assert len(eng.list_records(policy_phase=PolicyPhase.DRAFT)) == 1

    def test_filter_by_policy_category(self):
        eng = _engine()
        eng.record_policy(policy_name="a", policy_category=PolicyCategory.ACCESS_CONTROL)
        eng.record_policy(policy_name="b", policy_category=PolicyCategory.DATA_PROTECTION)
        assert len(eng.list_records(policy_category=PolicyCategory.ACCESS_CONTROL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_policy(policy_name="a", team="sec")
        eng.record_policy(policy_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_policy(policy_name=f"p-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            policy_name="test",
            analysis_score=88.5,
            breached=True,
            description="policy gap",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(policy_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_policy(policy_name="a", policy_phase=PolicyPhase.DRAFT, compliance_score=90.0)
        eng.record_policy(policy_name="b", policy_phase=PolicyPhase.DRAFT, compliance_score=70.0)
        result = eng.analyze_distribution()
        assert "draft" in result
        assert result["draft"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_policy(policy_name="a", compliance_score=60.0)
        eng.record_policy(policy_name="b", compliance_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_policy(policy_name="a", compliance_score=50.0)
        eng.record_policy(policy_name="b", compliance_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["compliance_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_policy(policy_name="a", service="auth", compliance_score=90.0)
        eng.record_policy(policy_name="b", service="api", compliance_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(policy_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(policy_name="a", analysis_score=20.0)
        eng.add_analysis(policy_name="b", analysis_score=20.0)
        eng.add_analysis(policy_name="c", analysis_score=80.0)
        eng.add_analysis(policy_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_policy(policy_name="test", compliance_score=50.0)
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
        eng.record_policy(policy_name="test")
        eng.add_analysis(policy_name="test")
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
        eng.record_policy(policy_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
