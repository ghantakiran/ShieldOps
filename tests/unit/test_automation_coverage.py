"""Tests for shieldops.operations.automation_coverage — AutomationCoverageAnalyzer.

Covers:
- ProcessCategory, AutomationLevel, CoverageGap enums
- ProcessRecord, AutomationGoal, CoverageReport model defaults
- register_process (basic, unique IDs, coverage calc, eviction)
- get_process (found, not found)
- list_processes (all, filter category, filter level, limit)
- create_goal (basic, on track)
- calculate_coverage (all, by category, empty)
- identify_automation_gaps (found, none)
- rank_by_automation_potential (basic, empty)
- estimate_automation_roi (found, not found)
- generate_coverage_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.operations.automation_coverage import (
    AutomationCoverageAnalyzer,
    AutomationGoal,
    AutomationLevel,
    CoverageGap,
    CoverageReport,
    ProcessCategory,
    ProcessRecord,
)


def _engine(**kw) -> AutomationCoverageAnalyzer:
    return AutomationCoverageAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ProcessCategory (5 values)

    def test_cat_deployment(self):
        assert ProcessCategory.DEPLOYMENT == "deployment"

    def test_cat_incident_response(self):
        assert ProcessCategory.INCIDENT_RESPONSE == "incident_response"

    def test_cat_provisioning(self):
        assert ProcessCategory.PROVISIONING == "provisioning"

    def test_cat_monitoring(self):
        assert ProcessCategory.MONITORING == "monitoring"

    def test_cat_maintenance(self):
        assert ProcessCategory.MAINTENANCE == "maintenance"

    # AutomationLevel (5 values)

    def test_level_fully_manual(self):
        assert AutomationLevel.FULLY_MANUAL == "fully_manual"

    def test_level_partially_automated(self):
        assert AutomationLevel.PARTIALLY_AUTOMATED == "partially_automated"

    def test_level_mostly_automated(self):
        assert AutomationLevel.MOSTLY_AUTOMATED == "mostly_automated"

    def test_level_fully_automated(self):
        assert AutomationLevel.FULLY_AUTOMATED == "fully_automated"

    def test_level_self_healing(self):
        assert AutomationLevel.SELF_HEALING == "self_healing"

    # CoverageGap (5 values)

    def test_gap_no_runbook(self):
        assert CoverageGap.NO_RUNBOOK == "no_runbook"

    def test_gap_manual_steps(self):
        assert CoverageGap.MANUAL_STEPS == "manual_steps"

    def test_gap_no_monitoring(self):
        assert CoverageGap.NO_MONITORING == "no_monitoring"

    def test_gap_no_rollback(self):
        assert CoverageGap.NO_ROLLBACK == "no_rollback"

    def test_gap_no_testing(self):
        assert CoverageGap.NO_TESTING == "no_testing"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_process_record_defaults(self):
        p = ProcessRecord(process_name="deploy-api")
        assert p.id
        assert p.process_name == "deploy-api"
        assert p.category == (ProcessCategory.DEPLOYMENT)
        assert p.service_name == ""
        assert p.automation_level == (AutomationLevel.FULLY_MANUAL)
        assert p.manual_steps == 0
        assert p.automated_steps == 0
        assert p.coverage_pct == 0.0
        assert p.gaps == []
        assert p.last_assessed_at > 0
        assert p.created_at > 0

    def test_automation_goal_defaults(self):
        g = AutomationGoal(target_coverage_pct=90.0)
        assert g.id
        assert g.category == (ProcessCategory.DEPLOYMENT)
        assert g.target_coverage_pct == 90.0
        assert g.current_coverage_pct == 0.0
        assert g.on_track is False
        assert g.deadline == ""
        assert g.created_at > 0

    def test_coverage_report_defaults(self):
        r = CoverageReport()
        assert r.total_processes == 0
        assert r.avg_coverage_pct == 0.0
        assert r.fully_automated_count == 0
        assert r.by_category == {}
        assert r.by_level == {}
        assert r.gap_summary == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# register_process
# -------------------------------------------------------------------


class TestRegisterProcess:
    def test_basic(self):
        e = _engine()
        p = e.register_process(
            process_name="deploy-api",
            category=ProcessCategory.DEPLOYMENT,
            service_name="api-svc",
            manual_steps=5,
            automated_steps=15,
        )
        assert p.process_name == "deploy-api"
        assert p.category == (ProcessCategory.DEPLOYMENT)
        assert p.service_name == "api-svc"
        assert p.coverage_pct == 75.0

    def test_unique_ids(self):
        e = _engine()
        p1 = e.register_process(process_name="a")
        p2 = e.register_process(process_name="b")
        assert p1.id != p2.id

    def test_coverage_calculation(self):
        e = _engine()
        p = e.register_process(
            manual_steps=0,
            automated_steps=10,
        )
        assert p.coverage_pct == 100.0

    def test_evicts_at_max(self):
        e = _engine(max_processes=2)
        p1 = e.register_process(process_name="a")
        e.register_process(process_name="b")
        e.register_process(process_name="c")
        procs = e.list_processes()
        ids = {p.id for p in procs}
        assert p1.id not in ids
        assert len(procs) == 2


# -------------------------------------------------------------------
# get_process
# -------------------------------------------------------------------


class TestGetProcess:
    def test_found(self):
        e = _engine()
        p = e.register_process(
            process_name="deploy",
        )
        assert e.get_process(p.id) is not None
        assert e.get_process(p.id).process_name == "deploy"

    def test_not_found(self):
        e = _engine()
        assert e.get_process("nonexistent") is None


# -------------------------------------------------------------------
# list_processes
# -------------------------------------------------------------------


class TestListProcesses:
    def test_list_all(self):
        e = _engine()
        e.register_process(process_name="a")
        e.register_process(process_name="b")
        e.register_process(process_name="c")
        assert len(e.list_processes()) == 3

    def test_filter_by_category(self):
        e = _engine()
        e.register_process(
            category=ProcessCategory.DEPLOYMENT,
        )
        e.register_process(
            category=ProcessCategory.MONITORING,
        )
        filtered = e.list_processes(
            category=ProcessCategory.DEPLOYMENT,
        )
        assert len(filtered) == 1
        assert filtered[0].category == (ProcessCategory.DEPLOYMENT)

    def test_filter_by_level(self):
        e = _engine()
        e.register_process(
            automation_level=(AutomationLevel.FULLY_AUTOMATED),
        )
        e.register_process(
            automation_level=(AutomationLevel.FULLY_MANUAL),
        )
        filtered = e.list_processes(
            automation_level=(AutomationLevel.FULLY_AUTOMATED),
        )
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.register_process(
                process_name=f"p-{i}",
            )
        assert len(e.list_processes(limit=3)) == 3


# -------------------------------------------------------------------
# create_goal
# -------------------------------------------------------------------


class TestCreateGoal:
    def test_basic(self):
        e = _engine()
        g = e.create_goal(
            category=ProcessCategory.DEPLOYMENT,
            target_pct=90.0,
            deadline="2026-12-31",
        )
        assert g.category == (ProcessCategory.DEPLOYMENT)
        assert g.target_coverage_pct == 90.0
        assert g.deadline == "2026-12-31"

    def test_on_track(self):
        e = _engine()
        e.register_process(
            category=ProcessCategory.MONITORING,
            manual_steps=1,
            automated_steps=9,
        )
        g = e.create_goal(
            category=ProcessCategory.MONITORING,
            target_pct=80.0,
        )
        assert g.on_track is True
        assert g.current_coverage_pct == 90.0


# -------------------------------------------------------------------
# calculate_coverage
# -------------------------------------------------------------------


class TestCalculateCoverage:
    def test_all(self):
        e = _engine()
        e.register_process(
            manual_steps=5,
            automated_steps=5,
        )
        e.register_process(
            manual_steps=0,
            automated_steps=10,
        )
        result = e.calculate_coverage()
        assert result["category"] == "all"
        assert result["process_count"] == 2
        assert result["coverage_pct"] == 75.0

    def test_by_category(self):
        e = _engine()
        e.register_process(
            category=ProcessCategory.DEPLOYMENT,
            manual_steps=2,
            automated_steps=8,
        )
        result = e.calculate_coverage(
            ProcessCategory.DEPLOYMENT,
        )
        assert result["category"] == "deployment"
        assert result["coverage_pct"] == 80.0

    def test_empty(self):
        e = _engine()
        result = e.calculate_coverage()
        assert result["process_count"] == 0
        assert result["coverage_pct"] == 0.0


# -------------------------------------------------------------------
# identify_automation_gaps
# -------------------------------------------------------------------


class TestIdentifyAutomationGaps:
    def test_found(self):
        e = _engine()
        e.register_process(
            process_name="deploy",
            gaps=["no_rollback", "no_testing"],
        )
        e.register_process(process_name="monitor")
        gaps = e.identify_automation_gaps()
        assert len(gaps) == 1
        assert gaps[0]["process_name"] == "deploy"
        assert len(gaps[0]["gaps"]) == 2

    def test_none(self):
        e = _engine()
        e.register_process(process_name="clean")
        assert e.identify_automation_gaps() == []


# -------------------------------------------------------------------
# rank_by_automation_potential
# -------------------------------------------------------------------


class TestRankByAutomationPotential:
    def test_basic(self):
        e = _engine()
        e.register_process(
            process_name="manual-heavy",
            manual_steps=8,
            automated_steps=2,
        )
        e.register_process(
            process_name="auto-heavy",
            manual_steps=1,
            automated_steps=9,
        )
        ranked = e.rank_by_automation_potential()
        assert len(ranked) == 2
        assert ranked[0]["process_name"] == "manual-heavy"
        assert ranked[0]["automation_potential_pct"] > ranked[1]["automation_potential_pct"]

    def test_empty(self):
        e = _engine()
        assert e.rank_by_automation_potential() == []


# -------------------------------------------------------------------
# estimate_automation_roi
# -------------------------------------------------------------------


class TestEstimateAutomationRoi:
    def test_found(self):
        e = _engine()
        p = e.register_process(
            process_name="deploy",
            manual_steps=10,
            automated_steps=5,
        )
        result = e.estimate_automation_roi(p.id)
        assert result is not None
        assert result["process_name"] == "deploy"
        assert result["manual_steps"] == 10
        assert result["estimated_manual_cost_hrs"] == 20.0
        assert result["breakeven_runs"] > 0

    def test_not_found(self):
        e = _engine()
        assert e.estimate_automation_roi("bad") is None


# -------------------------------------------------------------------
# generate_coverage_report
# -------------------------------------------------------------------


class TestGenerateCoverageReport:
    def test_populated(self):
        e = _engine()
        e.register_process(
            process_name="deploy",
            category=ProcessCategory.DEPLOYMENT,
            automation_level=(AutomationLevel.FULLY_AUTOMATED),
            manual_steps=0,
            automated_steps=10,
            gaps=["no_testing"],
        )
        e.register_process(
            process_name="provision",
            category=ProcessCategory.PROVISIONING,
            automation_level=(AutomationLevel.FULLY_MANUAL),
            manual_steps=8,
            automated_steps=2,
        )
        report = e.generate_coverage_report()
        assert report.total_processes == 2
        assert report.fully_automated_count == 1
        assert report.avg_coverage_pct > 0
        assert "deployment" in report.by_category
        assert "fully_automated" in report.by_level
        assert "no_testing" in report.gap_summary
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_coverage_report()
        assert report.total_processes == 0
        assert report.avg_coverage_pct == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        e.register_process(process_name="a")
        e.register_process(process_name="b")
        e.create_goal(target_pct=80.0)
        count = e.clear_data()
        assert count == 2
        assert e.list_processes() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_processes"] == 0
        assert stats["total_goals"] == 0
        assert stats["max_processes"] == 100000
        assert stats["target_coverage_pct"] == 80.0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.register_process(
            automation_level=(AutomationLevel.FULLY_AUTOMATED),
        )
        e.register_process(
            automation_level=(AutomationLevel.FULLY_MANUAL),
        )
        e.create_goal(target_pct=90.0)
        stats = e.get_stats()
        assert stats["total_processes"] == 2
        assert stats["total_goals"] == 1
        assert stats["level_distribution"]["fully_automated"] == 1
        assert stats["level_distribution"]["fully_manual"] == 1
