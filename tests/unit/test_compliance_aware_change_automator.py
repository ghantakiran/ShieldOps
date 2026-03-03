"""Tests for shieldops.changes.compliance_aware_change_automator

ComplianceAwareChangeAutomator.
"""

from __future__ import annotations

from shieldops.changes.compliance_aware_change_automator import (
    ChangeCategory,
    ComplianceAwareChangeAutomator,
    ComplianceAwareChangeReport,
    ComplianceChangeAnalysis,
    ComplianceChangeRecord,
    ComplianceCheck,
    ComplianceResult,
)


def _engine(**kw) -> ComplianceAwareChangeAutomator:
    return ComplianceAwareChangeAutomator(**kw)


class TestEnums:
    def test_change_category_infrastructure(self):
        assert ChangeCategory.INFRASTRUCTURE == "infrastructure"

    def test_change_category_application(self):
        assert ChangeCategory.APPLICATION == "application"

    def test_change_category_security(self):
        assert ChangeCategory.SECURITY == "security"

    def test_change_category_network(self):
        assert ChangeCategory.NETWORK == "network"

    def test_change_category_database(self):
        assert ChangeCategory.DATABASE == "database"

    def test_compliance_check_soc2_control(self):
        assert ComplianceCheck.SOC2_CONTROL == "soc2_control"

    def test_compliance_check_hipaa_rule(self):
        assert ComplianceCheck.HIPAA_RULE == "hipaa_rule"

    def test_compliance_check_pci_requirement(self):
        assert ComplianceCheck.PCI_REQUIREMENT == "pci_requirement"

    def test_compliance_check_internal_policy(self):
        assert ComplianceCheck.INTERNAL_POLICY == "internal_policy"

    def test_compliance_check_regulatory(self):
        assert ComplianceCheck.REGULATORY == "regulatory"

    def test_compliance_result_compliant(self):
        assert ComplianceResult.COMPLIANT == "compliant"

    def test_compliance_result_conditional(self):
        assert ComplianceResult.CONDITIONAL == "conditional"

    def test_compliance_result_non_compliant(self):
        assert ComplianceResult.NON_COMPLIANT == "non_compliant"

    def test_compliance_result_exempt(self):
        assert ComplianceResult.EXEMPT == "exempt"

    def test_compliance_result_review_required(self):
        assert ComplianceResult.REVIEW_REQUIRED == "review_required"


class TestModels:
    def test_record_defaults(self):
        r = ComplianceChangeRecord()
        assert r.id
        assert r.name == ""
        assert r.change_category == ChangeCategory.INFRASTRUCTURE
        assert r.compliance_check == ComplianceCheck.SOC2_CONTROL
        assert r.compliance_result == ComplianceResult.REVIEW_REQUIRED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ComplianceChangeAnalysis()
        assert a.id
        assert a.name == ""
        assert a.change_category == ChangeCategory.INFRASTRUCTURE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ComplianceAwareChangeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_change_category == {}
        assert r.by_compliance_check == {}
        assert r.by_compliance_result == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            change_category=ChangeCategory.INFRASTRUCTURE,
            compliance_check=ComplianceCheck.HIPAA_RULE,
            compliance_result=ComplianceResult.COMPLIANT,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.change_category == ChangeCategory.INFRASTRUCTURE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_change_category(self):
        eng = _engine()
        eng.record_entry(name="a", change_category=ChangeCategory.INFRASTRUCTURE)
        eng.record_entry(name="b", change_category=ChangeCategory.APPLICATION)
        assert len(eng.list_records(change_category=ChangeCategory.INFRASTRUCTURE)) == 1

    def test_filter_by_compliance_check(self):
        eng = _engine()
        eng.record_entry(name="a", compliance_check=ComplianceCheck.SOC2_CONTROL)
        eng.record_entry(name="b", compliance_check=ComplianceCheck.HIPAA_RULE)
        assert len(eng.list_records(compliance_check=ComplianceCheck.SOC2_CONTROL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", change_category=ChangeCategory.APPLICATION, score=90.0)
        eng.record_entry(name="b", change_category=ChangeCategory.APPLICATION, score=70.0)
        result = eng.analyze_distribution()
        assert "application" in result
        assert result["application"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
