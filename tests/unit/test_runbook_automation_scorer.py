"""Tests for shieldops.operations.runbook_automation_scorer — RunbookAutomationScorer."""

from __future__ import annotations

from shieldops.operations.runbook_automation_scorer import (
    AutomationBarrier,
    AutomationBenefit,
    AutomationLevel,
    AutomationMetric,
    AutomationRecord,
    RunbookAutomationReport,
    RunbookAutomationScorer,
)


def _engine(**kw) -> RunbookAutomationScorer:
    return RunbookAutomationScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_fully_automated(self):
        assert AutomationLevel.FULLY_AUTOMATED == "fully_automated"

    def test_level_mostly_automated(self):
        assert AutomationLevel.MOSTLY_AUTOMATED == "mostly_automated"

    def test_level_partially_automated(self):
        assert AutomationLevel.PARTIALLY_AUTOMATED == "partially_automated"

    def test_level_manual_with_tooling(self):
        assert AutomationLevel.MANUAL_WITH_TOOLING == "manual_with_tooling"

    def test_level_fully_manual(self):
        assert AutomationLevel.FULLY_MANUAL == "fully_manual"

    def test_barrier_complexity(self):
        assert AutomationBarrier.COMPLEXITY == "complexity"

    def test_barrier_approval_required(self):
        assert AutomationBarrier.APPROVAL_REQUIRED == "approval_required"

    def test_barrier_legacy_system(self):
        assert AutomationBarrier.LEGACY_SYSTEM == "legacy_system"

    def test_barrier_risk_level(self):
        assert AutomationBarrier.RISK_LEVEL == "risk_level"

    def test_barrier_resource_constraint(self):
        assert AutomationBarrier.RESOURCE_CONSTRAINT == "resource_constraint"

    def test_benefit_time_savings(self):
        assert AutomationBenefit.TIME_SAVINGS == "time_savings"

    def test_benefit_error_reduction(self):
        assert AutomationBenefit.ERROR_REDUCTION == "error_reduction"

    def test_benefit_consistency(self):
        assert AutomationBenefit.CONSISTENCY == "consistency"

    def test_benefit_scalability(self):
        assert AutomationBenefit.SCALABILITY == "scalability"

    def test_benefit_cost_reduction(self):
        assert AutomationBenefit.COST_REDUCTION == "cost_reduction"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_automation_record_defaults(self):
        r = AutomationRecord()
        assert r.id
        assert r.runbook_id == ""
        assert r.automation_level == AutomationLevel.FULLY_MANUAL
        assert r.automation_barrier == AutomationBarrier.COMPLEXITY
        assert r.automation_benefit == AutomationBenefit.TIME_SAVINGS
        assert r.automation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_automation_metric_defaults(self):
        m = AutomationMetric()
        assert m.id
        assert m.runbook_id == ""
        assert m.automation_level == AutomationLevel.FULLY_MANUAL
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_automation_report_defaults(self):
        r = RunbookAutomationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.manual_count == 0
        assert r.avg_automation_score == 0.0
        assert r.by_level == {}
        assert r.by_barrier == {}
        assert r.by_benefit == {}
        assert r.top_manual == []
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
            runbook_id="RB-001",
            automation_level=AutomationLevel.FULLY_AUTOMATED,
            automation_barrier=AutomationBarrier.COMPLEXITY,
            automation_benefit=AutomationBenefit.TIME_SAVINGS,
            automation_score=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.runbook_id == "RB-001"
        assert r.automation_level == AutomationLevel.FULLY_AUTOMATED
        assert r.automation_barrier == AutomationBarrier.COMPLEXITY
        assert r.automation_benefit == AutomationBenefit.TIME_SAVINGS
        assert r.automation_score == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_automation(runbook_id=f"RB-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_automation
# ---------------------------------------------------------------------------


class TestGetAutomation:
    def test_found(self):
        eng = _engine()
        r = eng.record_automation(
            runbook_id="RB-001",
            automation_level=AutomationLevel.FULLY_AUTOMATED,
        )
        result = eng.get_automation(r.id)
        assert result is not None
        assert result.automation_level == AutomationLevel.FULLY_AUTOMATED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_automation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_automations
# ---------------------------------------------------------------------------


class TestListAutomations:
    def test_list_all(self):
        eng = _engine()
        eng.record_automation(runbook_id="RB-001")
        eng.record_automation(runbook_id="RB-002")
        assert len(eng.list_automations()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_automation(
            runbook_id="RB-001",
            automation_level=AutomationLevel.FULLY_AUTOMATED,
        )
        eng.record_automation(
            runbook_id="RB-002",
            automation_level=AutomationLevel.FULLY_MANUAL,
        )
        results = eng.list_automations(
            automation_level=AutomationLevel.FULLY_AUTOMATED,
        )
        assert len(results) == 1

    def test_filter_by_barrier(self):
        eng = _engine()
        eng.record_automation(
            runbook_id="RB-001",
            automation_barrier=AutomationBarrier.COMPLEXITY,
        )
        eng.record_automation(
            runbook_id="RB-002",
            automation_barrier=AutomationBarrier.LEGACY_SYSTEM,
        )
        results = eng.list_automations(
            automation_barrier=AutomationBarrier.COMPLEXITY,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_automation(runbook_id="RB-001", team="sre")
        eng.record_automation(runbook_id="RB-002", team="platform")
        results = eng.list_automations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_automation(runbook_id=f"RB-{i}")
        assert len(eng.list_automations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            runbook_id="RB-001",
            automation_level=AutomationLevel.PARTIALLY_AUTOMATED,
            metric_score=55.0,
            threshold=60.0,
            breached=True,
            description="automation coverage",
        )
        assert m.runbook_id == "RB-001"
        assert m.automation_level == AutomationLevel.PARTIALLY_AUTOMATED
        assert m.metric_score == 55.0
        assert m.threshold == 60.0
        assert m.breached is True
        assert m.description == "automation coverage"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(runbook_id=f"RB-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_automation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeAutomationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_automation(
            runbook_id="RB-001",
            automation_level=AutomationLevel.FULLY_AUTOMATED,
            automation_score=95.0,
        )
        eng.record_automation(
            runbook_id="RB-002",
            automation_level=AutomationLevel.FULLY_AUTOMATED,
            automation_score=85.0,
        )
        result = eng.analyze_automation_distribution()
        assert "fully_automated" in result
        assert result["fully_automated"]["count"] == 2
        assert result["fully_automated"]["avg_automation_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_automation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_manual_runbooks
# ---------------------------------------------------------------------------


class TestIdentifyManualRunbooks:
    def test_detects_manual(self):
        eng = _engine()
        eng.record_automation(
            runbook_id="RB-001",
            automation_level=AutomationLevel.FULLY_MANUAL,
        )
        eng.record_automation(
            runbook_id="RB-002",
            automation_level=AutomationLevel.FULLY_AUTOMATED,
        )
        results = eng.identify_manual_runbooks()
        assert len(results) == 1
        assert results[0]["runbook_id"] == "RB-001"

    def test_detects_manual_with_tooling(self):
        eng = _engine()
        eng.record_automation(
            runbook_id="RB-001",
            automation_level=AutomationLevel.MANUAL_WITH_TOOLING,
        )
        results = eng.identify_manual_runbooks()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_manual_runbooks() == []


# ---------------------------------------------------------------------------
# rank_by_automation
# ---------------------------------------------------------------------------


class TestRankByAutomation:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_automation(runbook_id="RB-001", service="api", automation_score=90.0)
        eng.record_automation(runbook_id="RB-002", service="web", automation_score=30.0)
        results = eng.rank_by_automation()
        assert len(results) == 2
        assert results[0]["service"] == "web"
        assert results[0]["avg_automation_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_automation() == []


# ---------------------------------------------------------------------------
# detect_automation_trends
# ---------------------------------------------------------------------------


class TestDetectAutomationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(runbook_id="RB-001", metric_score=50.0)
        result = eng.detect_automation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(runbook_id="RB-001", metric_score=20.0)
        eng.add_metric(runbook_id="RB-002", metric_score=20.0)
        eng.add_metric(runbook_id="RB-003", metric_score=80.0)
        eng.add_metric(runbook_id="RB-004", metric_score=80.0)
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
        eng = _engine()
        eng.record_automation(
            runbook_id="RB-001",
            automation_level=AutomationLevel.FULLY_MANUAL,
            automation_barrier=AutomationBarrier.COMPLEXITY,
            automation_benefit=AutomationBenefit.TIME_SAVINGS,
            automation_score=10.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RunbookAutomationReport)
        assert report.total_records == 1
        assert report.manual_count == 1
        assert len(report.top_manual) == 1
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
        eng.record_automation(runbook_id="RB-001")
        eng.add_metric(runbook_id="RB-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_automation(
            runbook_id="RB-001",
            automation_level=AutomationLevel.FULLY_AUTOMATED,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_runbooks"] == 1
        assert "fully_automated" in stats["level_distribution"]
