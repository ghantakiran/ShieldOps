"""Tests for shieldops.compliance.compliance_automation_scorer — ComplianceAutomationScorer."""

from __future__ import annotations

from shieldops.compliance.compliance_automation_scorer import (
    AutomationAnalysis,
    AutomationMaturity,
    AutomationRecord,
    AutomationReport,
    AutomationScope,
    ComplianceAutomationScorer,
    ROICategory,
)


def _engine(**kw) -> ComplianceAutomationScorer:
    return ComplianceAutomationScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_automationscope_evidence_collection(self):
        assert AutomationScope.EVIDENCE_COLLECTION == "evidence_collection"

    def test_automationscope_control_testing(self):
        assert AutomationScope.CONTROL_TESTING == "control_testing"

    def test_automationscope_reporting(self):
        assert AutomationScope.REPORTING == "reporting"

    def test_automationscope_monitoring(self):
        assert AutomationScope.MONITORING == "monitoring"

    def test_automationscope_remediation(self):
        assert AutomationScope.REMEDIATION == "remediation"

    def test_automationmaturity_fully_automated(self):
        assert AutomationMaturity.FULLY_AUTOMATED == "fully_automated"

    def test_automationmaturity_mostly_automated(self):
        assert AutomationMaturity.MOSTLY_AUTOMATED == "mostly_automated"

    def test_automationmaturity_partially_automated(self):
        assert AutomationMaturity.PARTIALLY_AUTOMATED == "partially_automated"

    def test_automationmaturity_manual_with_tools(self):
        assert AutomationMaturity.MANUAL_WITH_TOOLS == "manual_with_tools"

    def test_automationmaturity_fully_manual(self):
        assert AutomationMaturity.FULLY_MANUAL == "fully_manual"

    def test_roicategory_high_roi(self):
        assert ROICategory.HIGH_ROI == "high_roi"

    def test_roicategory_moderate_roi(self):
        assert ROICategory.MODERATE_ROI == "moderate_roi"

    def test_roicategory_low_roi(self):
        assert ROICategory.LOW_ROI == "low_roi"

    def test_roicategory_break_even(self):
        assert ROICategory.BREAK_EVEN == "break_even"

    def test_roicategory_negative_roi(self):
        assert ROICategory.NEGATIVE_ROI == "negative_roi"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_automationrecord_defaults(self):
        r = AutomationRecord()
        assert r.id
        assert r.process_name == ""
        assert r.automation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_automationanalysis_defaults(self):
        c = AutomationAnalysis()
        assert c.id
        assert c.process_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_automationreport_defaults(self):
        r = AutomationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_automation_count == 0
        assert r.avg_automation_score == 0
        assert r.by_scope == {}
        assert r.by_maturity == {}
        assert r.by_roi == {}
        assert r.top_low_automation == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_automation
# ---------------------------------------------------------------------------


class TestRecordAutomation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_automation(
            process_name="test-item",
            automation_scope=AutomationScope.CONTROL_TESTING,
            automation_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.process_name == "test-item"
        assert r.automation_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_automation(process_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_automation
# ---------------------------------------------------------------------------


class TestGetAutomation:
    def test_found(self):
        eng = _engine()
        r = eng.record_automation(process_name="test-item")
        result = eng.get_automation(r.id)
        assert result is not None
        assert result.process_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_automation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_automations
# ---------------------------------------------------------------------------


class TestListAutomations:
    def test_list_all(self):
        eng = _engine()
        eng.record_automation(process_name="ITEM-001")
        eng.record_automation(process_name="ITEM-002")
        assert len(eng.list_automations()) == 2

    def test_filter_by_automation_scope(self):
        eng = _engine()
        eng.record_automation(
            process_name="ITEM-001", automation_scope=AutomationScope.EVIDENCE_COLLECTION
        )
        eng.record_automation(
            process_name="ITEM-002", automation_scope=AutomationScope.CONTROL_TESTING
        )
        results = eng.list_automations(automation_scope=AutomationScope.EVIDENCE_COLLECTION)
        assert len(results) == 1

    def test_filter_by_automation_maturity(self):
        eng = _engine()
        eng.record_automation(
            process_name="ITEM-001", automation_maturity=AutomationMaturity.FULLY_AUTOMATED
        )
        eng.record_automation(
            process_name="ITEM-002", automation_maturity=AutomationMaturity.MOSTLY_AUTOMATED
        )
        results = eng.list_automations(automation_maturity=AutomationMaturity.FULLY_AUTOMATED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_automation(process_name="ITEM-001", team="security")
        eng.record_automation(process_name="ITEM-002", team="platform")
        results = eng.list_automations(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_automation(process_name=f"ITEM-{i}")
        assert len(eng.list_automations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            process_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.process_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(process_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_automation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_automation(
            process_name="ITEM-001",
            automation_scope=AutomationScope.EVIDENCE_COLLECTION,
            automation_score=90.0,
        )
        eng.record_automation(
            process_name="ITEM-002",
            automation_scope=AutomationScope.EVIDENCE_COLLECTION,
            automation_score=70.0,
        )
        result = eng.analyze_automation_distribution()
        assert "evidence_collection" in result
        assert result["evidence_collection"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_automation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_automation_processes
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(automation_threshold=70.0)
        eng.record_automation(process_name="ITEM-001", automation_score=30.0)
        eng.record_automation(process_name="ITEM-002", automation_score=90.0)
        results = eng.identify_low_automation_processes()
        assert len(results) == 1
        assert results[0]["process_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(automation_threshold=70.0)
        eng.record_automation(process_name="ITEM-001", automation_score=50.0)
        eng.record_automation(process_name="ITEM-002", automation_score=30.0)
        results = eng.identify_low_automation_processes()
        assert len(results) == 2
        assert results[0]["automation_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_automation_processes() == []


# ---------------------------------------------------------------------------
# rank_by_automation
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_automation(process_name="ITEM-001", service="auth-svc", automation_score=90.0)
        eng.record_automation(process_name="ITEM-002", service="api-gw", automation_score=50.0)
        results = eng.rank_by_automation()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_automation() == []


# ---------------------------------------------------------------------------
# detect_automation_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(process_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_automation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(process_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(process_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(process_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(process_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_automation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_automation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(automation_threshold=70.0)
        eng.record_automation(process_name="test-item", automation_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, AutomationReport)
        assert report.total_records == 1
        assert report.low_automation_count == 1
        assert len(report.top_low_automation) == 1
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
        eng.record_automation(process_name="ITEM-001")
        eng.add_analysis(process_name="ITEM-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_automation(
            process_name="ITEM-001",
            automation_scope=AutomationScope.EVIDENCE_COLLECTION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
