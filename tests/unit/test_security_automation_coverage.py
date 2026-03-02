"""Tests for shieldops.security.security_automation_coverage — SecurityAutomationCoverage."""

from __future__ import annotations

from shieldops.security.security_automation_coverage import (
    AutomationAnalysis,
    AutomationCoverageReport,
    AutomationRecord,
    AutomationType,
    CoverageArea,
    MaturityLevel,
    SecurityAutomationCoverage,
)


def _engine(**kw) -> SecurityAutomationCoverage:
    return SecurityAutomationCoverage(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_playbook(self):
        assert AutomationType.PLAYBOOK == "playbook"

    def test_type_rule_based(self):
        assert AutomationType.RULE_BASED == "rule_based"

    def test_type_ml_driven(self):
        assert AutomationType.ML_DRIVEN == "ml_driven"

    def test_type_orchestration(self):
        assert AutomationType.ORCHESTRATION == "orchestration"

    def test_type_custom_script(self):
        assert AutomationType.CUSTOM_SCRIPT == "custom_script"

    def test_area_detection(self):
        assert CoverageArea.DETECTION == "detection"

    def test_area_response(self):
        assert CoverageArea.RESPONSE == "response"

    def test_area_investigation(self):
        assert CoverageArea.INVESTIGATION == "investigation"

    def test_area_reporting(self):
        assert CoverageArea.REPORTING == "reporting"

    def test_area_remediation(self):
        assert CoverageArea.REMEDIATION == "remediation"

    def test_maturity_optimized(self):
        assert MaturityLevel.OPTIMIZED == "optimized"

    def test_maturity_managed(self):
        assert MaturityLevel.MANAGED == "managed"

    def test_maturity_defined(self):
        assert MaturityLevel.DEFINED == "defined"

    def test_maturity_developing(self):
        assert MaturityLevel.DEVELOPING == "developing"

    def test_maturity_initial(self):
        assert MaturityLevel.INITIAL == "initial"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_automation_record_defaults(self):
        r = AutomationRecord()
        assert r.id
        assert r.automation_name == ""
        assert r.automation_type == AutomationType.PLAYBOOK
        assert r.coverage_area == CoverageArea.DETECTION
        assert r.maturity_level == MaturityLevel.OPTIMIZED
        assert r.coverage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_automation_analysis_defaults(self):
        c = AutomationAnalysis()
        assert c.id
        assert c.automation_name == ""
        assert c.automation_type == AutomationType.PLAYBOOK
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_automation_coverage_report_defaults(self):
        r = AutomationCoverageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_coverage_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_type == {}
        assert r.by_area == {}
        assert r.by_maturity == {}
        assert r.top_low_coverage == []
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
            automation_name="phishing-response",
            automation_type=AutomationType.RULE_BASED,
            coverage_area=CoverageArea.RESPONSE,
            maturity_level=MaturityLevel.MANAGED,
            coverage_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.automation_name == "phishing-response"
        assert r.automation_type == AutomationType.RULE_BASED
        assert r.coverage_area == CoverageArea.RESPONSE
        assert r.maturity_level == MaturityLevel.MANAGED
        assert r.coverage_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_automation(automation_name=f"A-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_automation
# ---------------------------------------------------------------------------


class TestGetAutomation:
    def test_found(self):
        eng = _engine()
        r = eng.record_automation(
            automation_name="phishing-response",
            maturity_level=MaturityLevel.OPTIMIZED,
        )
        result = eng.get_automation(r.id)
        assert result is not None
        assert result.maturity_level == MaturityLevel.OPTIMIZED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_automation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_automations
# ---------------------------------------------------------------------------


class TestListAutomations:
    def test_list_all(self):
        eng = _engine()
        eng.record_automation(automation_name="A-001")
        eng.record_automation(automation_name="A-002")
        assert len(eng.list_automations()) == 2

    def test_filter_by_automation_type(self):
        eng = _engine()
        eng.record_automation(
            automation_name="A-001",
            automation_type=AutomationType.PLAYBOOK,
        )
        eng.record_automation(
            automation_name="A-002",
            automation_type=AutomationType.ML_DRIVEN,
        )
        results = eng.list_automations(automation_type=AutomationType.PLAYBOOK)
        assert len(results) == 1

    def test_filter_by_coverage_area(self):
        eng = _engine()
        eng.record_automation(
            automation_name="A-001",
            coverage_area=CoverageArea.DETECTION,
        )
        eng.record_automation(
            automation_name="A-002",
            coverage_area=CoverageArea.RESPONSE,
        )
        results = eng.list_automations(
            coverage_area=CoverageArea.DETECTION,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_automation(automation_name="A-001", team="security")
        eng.record_automation(automation_name="A-002", team="platform")
        results = eng.list_automations(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_automation(automation_name=f"A-{i}")
        assert len(eng.list_automations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            automation_name="phishing-response",
            automation_type=AutomationType.RULE_BASED,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="coverage gap detected",
        )
        assert a.automation_name == "phishing-response"
        assert a.automation_type == AutomationType.RULE_BASED
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(automation_name=f"A-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_type_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_automation(
            automation_name="A-001",
            automation_type=AutomationType.PLAYBOOK,
            coverage_score=90.0,
        )
        eng.record_automation(
            automation_name="A-002",
            automation_type=AutomationType.PLAYBOOK,
            coverage_score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "playbook" in result
        assert result["playbook"]["count"] == 2
        assert result["playbook"]["avg_coverage_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_coverage_automations
# ---------------------------------------------------------------------------


class TestIdentifyLowCoverageAutomations:
    def test_detects_below_threshold(self):
        eng = _engine(automation_coverage_threshold=80.0)
        eng.record_automation(automation_name="A-001", coverage_score=60.0)
        eng.record_automation(automation_name="A-002", coverage_score=90.0)
        results = eng.identify_low_coverage_automations()
        assert len(results) == 1
        assert results[0]["automation_name"] == "A-001"

    def test_sorted_ascending(self):
        eng = _engine(automation_coverage_threshold=80.0)
        eng.record_automation(automation_name="A-001", coverage_score=50.0)
        eng.record_automation(automation_name="A-002", coverage_score=30.0)
        results = eng.identify_low_coverage_automations()
        assert len(results) == 2
        assert results[0]["coverage_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_coverage_automations() == []


# ---------------------------------------------------------------------------
# rank_by_coverage_score
# ---------------------------------------------------------------------------


class TestRankByCoverageScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_automation(automation_name="A-001", service="auth-svc", coverage_score=90.0)
        eng.record_automation(automation_name="A-002", service="api-gw", coverage_score=50.0)
        results = eng.rank_by_coverage_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_coverage_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage_score() == []


# ---------------------------------------------------------------------------
# detect_coverage_trends
# ---------------------------------------------------------------------------


class TestDetectCoverageTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(automation_name="A-001", analysis_score=50.0)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(automation_name="A-001", analysis_score=20.0)
        eng.add_analysis(automation_name="A-002", analysis_score=20.0)
        eng.add_analysis(automation_name="A-003", analysis_score=80.0)
        eng.add_analysis(automation_name="A-004", analysis_score=80.0)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "improving"
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
        eng = _engine(automation_coverage_threshold=80.0)
        eng.record_automation(
            automation_name="phishing-response",
            automation_type=AutomationType.RULE_BASED,
            coverage_area=CoverageArea.RESPONSE,
            maturity_level=MaturityLevel.MANAGED,
            coverage_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AutomationCoverageReport)
        assert report.total_records == 1
        assert report.low_coverage_count == 1
        assert len(report.top_low_coverage) == 1
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
        eng.record_automation(automation_name="A-001")
        eng.add_analysis(automation_name="A-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_automation(
            automation_name="A-001",
            automation_type=AutomationType.PLAYBOOK,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "playbook" in stats["type_distribution"]
