"""Tests for shieldops.operations.toil_automator — ToilAutomationTracker."""

from __future__ import annotations

from shieldops.operations.toil_automator import (
    AutomationProgress,
    AutomationROI,
    AutomationStatus,
    ToilAutomationReport,
    ToilAutomationTracker,
    ToilCategory,
    ToilRecord,
)


def _engine(**kw) -> ToilAutomationTracker:
    return ToilAutomationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_manual_deployment(self):
        assert ToilCategory.MANUAL_DEPLOYMENT == "manual_deployment"

    def test_category_certificate_renewal(self):
        assert ToilCategory.CERTIFICATE_RENEWAL == "certificate_renewal"

    def test_category_log_analysis(self):
        assert ToilCategory.LOG_ANALYSIS == "log_analysis"

    def test_category_incident_triage(self):
        assert ToilCategory.INCIDENT_TRIAGE == "incident_triage"

    def test_category_config_update(self):
        assert ToilCategory.CONFIG_UPDATE == "config_update"

    def test_status_fully_automated(self):
        assert AutomationStatus.FULLY_AUTOMATED == "fully_automated"

    def test_status_partially_automated(self):
        assert AutomationStatus.PARTIALLY_AUTOMATED == "partially_automated"

    def test_status_scripted(self):
        assert AutomationStatus.SCRIPTED == "scripted"

    def test_status_manual(self):
        assert AutomationStatus.MANUAL == "manual"

    def test_status_not_started(self):
        assert AutomationStatus.NOT_STARTED == "not_started"

    def test_roi_high(self):
        assert AutomationROI.HIGH == "high"

    def test_roi_moderate(self):
        assert AutomationROI.MODERATE == "moderate"

    def test_roi_low(self):
        assert AutomationROI.LOW == "low"

    def test_roi_break_even(self):
        assert AutomationROI.BREAK_EVEN == "break_even"

    def test_roi_negative(self):
        assert AutomationROI.NEGATIVE == "negative"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_toil_record_defaults(self):
        r = ToilRecord()
        assert r.id
        assert r.task_id == ""
        assert r.toil_category == ToilCategory.MANUAL_DEPLOYMENT
        assert r.automation_status == AutomationStatus.NOT_STARTED
        assert r.automation_roi == AutomationROI.LOW
        assert r.time_savings == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_automation_progress_defaults(self):
        p = AutomationProgress()
        assert p.id
        assert p.task_id == ""
        assert p.toil_category == ToilCategory.MANUAL_DEPLOYMENT
        assert p.value == 0.0
        assert p.threshold == 0.0
        assert p.breached is False
        assert p.description == ""
        assert p.created_at > 0

    def test_toil_automation_report_defaults(self):
        r = ToilAutomationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_progress == 0
        assert r.manual_tasks == 0
        assert r.avg_time_savings == 0.0
        assert r.by_category == {}
        assert r.by_status == {}
        assert r.by_roi == {}
        assert r.top_savings == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_toil
# ---------------------------------------------------------------------------


class TestRecordToil:
    def test_basic(self):
        eng = _engine()
        r = eng.record_toil(
            task_id="TOIL-001",
            toil_category=ToilCategory.CERTIFICATE_RENEWAL,
            automation_status=AutomationStatus.SCRIPTED,
            automation_roi=AutomationROI.HIGH,
            time_savings=120.0,
            service="api-gateway",
            team="sre",
        )
        assert r.task_id == "TOIL-001"
        assert r.toil_category == ToilCategory.CERTIFICATE_RENEWAL
        assert r.automation_status == AutomationStatus.SCRIPTED
        assert r.automation_roi == AutomationROI.HIGH
        assert r.time_savings == 120.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_toil(task_id=f"TOIL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_toil
# ---------------------------------------------------------------------------


class TestGetToil:
    def test_found(self):
        eng = _engine()
        r = eng.record_toil(
            task_id="TOIL-001",
            automation_status=AutomationStatus.MANUAL,
        )
        result = eng.get_toil(r.id)
        assert result is not None
        assert result.automation_status == AutomationStatus.MANUAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_toil("nonexistent") is None


# ---------------------------------------------------------------------------
# list_toils
# ---------------------------------------------------------------------------


class TestListToils:
    def test_list_all(self):
        eng = _engine()
        eng.record_toil(task_id="TOIL-001")
        eng.record_toil(task_id="TOIL-002")
        assert len(eng.list_toils()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_toil(
            task_id="TOIL-001",
            toil_category=ToilCategory.LOG_ANALYSIS,
        )
        eng.record_toil(
            task_id="TOIL-002",
            toil_category=ToilCategory.MANUAL_DEPLOYMENT,
        )
        results = eng.list_toils(category=ToilCategory.LOG_ANALYSIS)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_toil(
            task_id="TOIL-001",
            automation_status=AutomationStatus.MANUAL,
        )
        eng.record_toil(
            task_id="TOIL-002",
            automation_status=AutomationStatus.FULLY_AUTOMATED,
        )
        results = eng.list_toils(status=AutomationStatus.MANUAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_toil(task_id="TOIL-001", service="api")
        eng.record_toil(task_id="TOIL-002", service="web")
        results = eng.list_toils(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_toil(task_id="TOIL-001", team="sre")
        eng.record_toil(task_id="TOIL-002", team="platform")
        results = eng.list_toils(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_toil(task_id=f"TOIL-{i}")
        assert len(eng.list_toils(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_progress
# ---------------------------------------------------------------------------


class TestAddProgress:
    def test_basic(self):
        eng = _engine()
        p = eng.add_progress(
            task_id="TOIL-001",
            toil_category=ToilCategory.INCIDENT_TRIAGE,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Triage within limits",
        )
        assert p.task_id == "TOIL-001"
        assert p.toil_category == ToilCategory.INCIDENT_TRIAGE
        assert p.value == 75.0
        assert p.threshold == 80.0
        assert p.breached is False
        assert p.description == "Triage within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_progress(task_id=f"TOIL-{i}")
        assert len(eng._progress) == 2


# ---------------------------------------------------------------------------
# analyze_automation_coverage
# ---------------------------------------------------------------------------


class TestAnalyzeAutomationCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_toil(
            task_id="TOIL-001",
            toil_category=ToilCategory.MANUAL_DEPLOYMENT,
            time_savings=60.0,
        )
        eng.record_toil(
            task_id="TOIL-002",
            toil_category=ToilCategory.MANUAL_DEPLOYMENT,
            time_savings=100.0,
        )
        result = eng.analyze_automation_coverage()
        assert "manual_deployment" in result
        assert result["manual_deployment"]["count"] == 2
        assert result["manual_deployment"]["avg_time_savings"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_automation_coverage() == {}


# ---------------------------------------------------------------------------
# identify_manual_tasks
# ---------------------------------------------------------------------------


class TestIdentifyManualTasks:
    def test_detects_manual(self):
        eng = _engine()
        eng.record_toil(
            task_id="TOIL-001",
            automation_status=AutomationStatus.MANUAL,
        )
        eng.record_toil(
            task_id="TOIL-002",
            automation_status=AutomationStatus.FULLY_AUTOMATED,
        )
        results = eng.identify_manual_tasks()
        assert len(results) == 1
        assert results[0]["task_id"] == "TOIL-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_manual_tasks() == []


# ---------------------------------------------------------------------------
# rank_by_time_savings
# ---------------------------------------------------------------------------


class TestRankByTimeSavings:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_toil(task_id="TOIL-001", service="api", time_savings=90.0)
        eng.record_toil(task_id="TOIL-002", service="api", time_savings=80.0)
        eng.record_toil(task_id="TOIL-003", service="web", time_savings=50.0)
        results = eng.rank_by_time_savings()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_time_savings"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_time_savings() == []


# ---------------------------------------------------------------------------
# detect_automation_gaps
# ---------------------------------------------------------------------------


class TestDetectAutomationGaps:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_progress(task_id="TOIL-001", value=val)
        result = eng.detect_automation_gaps()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_progress(task_id="TOIL-001", value=val)
        result = eng.detect_automation_gaps()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_automation_gaps()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_toil(
            task_id="TOIL-001",
            toil_category=ToilCategory.MANUAL_DEPLOYMENT,
            automation_status=AutomationStatus.MANUAL,
            time_savings=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ToilAutomationReport)
        assert report.total_records == 1
        assert report.manual_tasks == 1
        assert report.avg_time_savings == 50.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_toil(task_id="TOIL-001")
        eng.add_progress(task_id="TOIL-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._progress) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_progress"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_toil(
            task_id="TOIL-001",
            toil_category=ToilCategory.LOG_ANALYSIS,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_tasks"] == 1
        assert "log_analysis" in stats["category_distribution"]
