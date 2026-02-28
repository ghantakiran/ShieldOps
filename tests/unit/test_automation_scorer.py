"""Tests for shieldops.compliance.automation_scorer — ComplianceAutomationScorer."""

from __future__ import annotations

from shieldops.compliance.automation_scorer import (
    AutomationControl,
    AutomationLevel,
    AutomationPriority,
    AutomationScoreRecord,
    AutomationScorerReport,
    ComplianceAutomationScorer,
    ControlCategory,
)


def _engine(**kw) -> ComplianceAutomationScorer:
    return ComplianceAutomationScorer(**kw)


class TestEnums:
    def test_level_fully_automated(self):
        assert AutomationLevel.FULLY_AUTOMATED == "fully_automated"

    def test_level_mostly_automated(self):
        assert AutomationLevel.MOSTLY_AUTOMATED == "mostly_automated"

    def test_level_partially_automated(self):
        assert AutomationLevel.PARTIALLY_AUTOMATED == "partially_automated"

    def test_level_manual_with_tools(self):
        assert AutomationLevel.MANUAL_WITH_TOOLS == "manual_with_tools"

    def test_level_fully_manual(self):
        assert AutomationLevel.FULLY_MANUAL == "fully_manual"

    def test_category_access_control(self):
        assert ControlCategory.ACCESS_CONTROL == "access_control"

    def test_category_data_protection(self):
        assert ControlCategory.DATA_PROTECTION == "data_protection"

    def test_category_monitoring(self):
        assert ControlCategory.MONITORING == "monitoring"

    def test_category_incident_response(self):
        assert ControlCategory.INCIDENT_RESPONSE == "incident_response"

    def test_category_change_management(self):
        assert ControlCategory.CHANGE_MANAGEMENT == "change_management"

    def test_priority_critical(self):
        assert AutomationPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert AutomationPriority.HIGH == "high"

    def test_priority_medium(self):
        assert AutomationPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert AutomationPriority.LOW == "low"

    def test_priority_optional(self):
        assert AutomationPriority.OPTIONAL == "optional"


class TestModels:
    def test_automation_score_record_defaults(self):
        r = AutomationScoreRecord()
        assert r.id
        assert r.control_name == ""
        assert r.automation_level == AutomationLevel.PARTIALLY_AUTOMATED
        assert r.category == ControlCategory.MONITORING
        assert r.priority == AutomationPriority.MEDIUM
        assert r.automation_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_automation_control_defaults(self):
        r = AutomationControl()
        assert r.id
        assert r.control_name == ""
        assert r.category == ControlCategory.MONITORING
        assert r.priority == AutomationPriority.MEDIUM
        assert r.target_pct == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = AutomationScorerReport()
        assert r.total_records == 0
        assert r.total_controls == 0
        assert r.avg_automation_pct == 0.0
        assert r.by_category == {}
        assert r.by_level == {}
        assert r.manual_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordScore:
    def test_basic(self):
        eng = _engine()
        r = eng.record_score("ctrl-1", automation_pct=85.0)
        assert r.control_name == "ctrl-1"
        assert r.automation_pct == 85.0

    def test_with_level(self):
        eng = _engine()
        r = eng.record_score("ctrl-2", automation_level=AutomationLevel.FULLY_AUTOMATED)
        assert r.automation_level == AutomationLevel.FULLY_AUTOMATED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_score(f"ctrl-{i}")
        assert len(eng._records) == 3


class TestGetScore:
    def test_found(self):
        eng = _engine()
        r = eng.record_score("ctrl-1")
        assert eng.get_score(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_score("nonexistent") is None


class TestListScores:
    def test_list_all(self):
        eng = _engine()
        eng.record_score("ctrl-1")
        eng.record_score("ctrl-2")
        assert len(eng.list_scores()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_score("ctrl-1", category=ControlCategory.ACCESS_CONTROL)
        eng.record_score("ctrl-2", category=ControlCategory.MONITORING)
        results = eng.list_scores(category=ControlCategory.ACCESS_CONTROL)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_score("ctrl-1", automation_level=AutomationLevel.FULLY_MANUAL)
        eng.record_score("ctrl-2", automation_level=AutomationLevel.FULLY_AUTOMATED)
        results = eng.list_scores(automation_level=AutomationLevel.FULLY_MANUAL)
        assert len(results) == 1


class TestAddControl:
    def test_basic(self):
        eng = _engine()
        ctrl = eng.add_control("ctrl-x", target_pct=90.0)
        assert ctrl.control_name == "ctrl-x"
        assert ctrl.target_pct == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_control(f"ctrl-{i}")
        assert len(eng._controls) == 2


class TestAnalyzeAutomationByCategory:
    def test_with_data(self):
        eng = _engine()
        eng.record_score("ctrl-1", category=ControlCategory.MONITORING, automation_pct=80.0)
        eng.record_score("ctrl-2", category=ControlCategory.MONITORING, automation_pct=60.0)
        result = eng.analyze_automation_by_category(ControlCategory.MONITORING)
        assert result["category"] == "monitoring"
        assert result["total"] == 2
        assert result["avg_automation_pct"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_automation_by_category(ControlCategory.ACCESS_CONTROL)
        assert result["status"] == "no_data"


class TestIdentifyManualControls:
    def test_with_manual(self):
        eng = _engine()
        eng.record_score("ctrl-1", automation_level=AutomationLevel.FULLY_MANUAL)
        eng.record_score("ctrl-1", automation_level=AutomationLevel.FULLY_MANUAL)
        eng.record_score("ctrl-2", automation_level=AutomationLevel.FULLY_AUTOMATED)
        results = eng.identify_manual_controls()
        assert len(results) == 1
        assert results[0]["control_name"] == "ctrl-1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_manual_controls() == []


class TestRankByAutomationLevel:
    def test_with_data(self):
        eng = _engine()
        eng.record_score("ctrl-1", category=ControlCategory.MONITORING, automation_pct=40.0)
        eng.record_score("ctrl-2", category=ControlCategory.ACCESS_CONTROL, automation_pct=90.0)
        results = eng.rank_by_automation_level()
        assert results[0]["category"] == "access_control"
        assert results[0]["avg_automation_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_automation_level() == []


class TestDetectAutomationTrends:
    def test_with_trends(self):
        eng = _engine()
        for i in range(5):
            eng.record_score(
                "ctrl-1",
                category=ControlCategory.MONITORING,
                automation_pct=float(40 + i * 10),
            )
        results = eng.detect_automation_trends()
        assert len(results) == 1
        assert results[0]["category"] == "monitoring"
        assert results[0]["trend"] == "improving"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_automation_trends() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_score(
            "ctrl-1", automation_pct=30.0, automation_level=AutomationLevel.FULLY_MANUAL
        )
        eng.record_score(
            "ctrl-2", automation_pct=90.0, automation_level=AutomationLevel.FULLY_AUTOMATED
        )
        eng.add_control("ctrl-x")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_controls == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_score("ctrl-1")
        eng.add_control("ctrl-x")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._controls) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_controls"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_score("ctrl-1", category=ControlCategory.MONITORING)
        eng.record_score("ctrl-2", category=ControlCategory.ACCESS_CONTROL)
        eng.add_control("ctrl-x")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_controls"] == 1
        assert stats["unique_controls"] == 2
