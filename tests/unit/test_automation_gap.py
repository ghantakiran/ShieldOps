"""Tests for shieldops.operations.automation_gap — AutomationGapIdentifier."""

from __future__ import annotations

from shieldops.operations.automation_gap import (
    AutomationCandidate,
    AutomationFeasibility,
    AutomationGapIdentifier,
    AutomationGapRecord,
    AutomationGapReport,
    GapCategory,
    GapImpact,
)


def _engine(**kw) -> AutomationGapIdentifier:
    return AutomationGapIdentifier(**kw)


class TestEnums:
    def test_cat_manual(self):
        assert GapCategory.MANUAL_PROCESS == "manual_process"

    def test_cat_repetitive(self):
        assert GapCategory.REPETITIVE_TASK == "repetitive_task"

    def test_cat_error_prone(self):
        assert GapCategory.ERROR_PRONE == "error_prone"

    def test_cat_time_consuming(self):
        assert GapCategory.TIME_CONSUMING == "time_consuming"

    def test_cat_compliance(self):
        assert GapCategory.COMPLIANCE_REQUIRED == "compliance_required"

    def test_feas_easy(self):
        assert AutomationFeasibility.EASY == "easy"

    def test_feas_moderate(self):
        assert AutomationFeasibility.MODERATE == "moderate"

    def test_feas_difficult(self):
        assert AutomationFeasibility.DIFFICULT == "difficult"

    def test_feas_research(self):
        assert AutomationFeasibility.REQUIRES_RESEARCH == "requires_research"

    def test_feas_not_feasible(self):
        assert AutomationFeasibility.NOT_FEASIBLE == "not_feasible"

    def test_impact_critical(self):
        assert GapImpact.CRITICAL == "critical"

    def test_impact_high(self):
        assert GapImpact.HIGH == "high"

    def test_impact_medium(self):
        assert GapImpact.MEDIUM == "medium"

    def test_impact_low(self):
        assert GapImpact.LOW == "low"

    def test_impact_minimal(self):
        assert GapImpact.MINIMAL == "minimal"


class TestModels:
    def test_gap_record_defaults(self):
        r = AutomationGapRecord()
        assert r.id
        assert r.gap_name == ""
        assert r.category == GapCategory.MANUAL_PROCESS
        assert r.feasibility == AutomationFeasibility.MODERATE
        assert r.impact == GapImpact.MEDIUM
        assert r.hours_per_week == 0.0
        assert r.roi_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_candidate_defaults(self):
        r = AutomationCandidate()
        assert r.id
        assert r.candidate_name == ""
        assert r.gap_name == ""
        assert r.feasibility == AutomationFeasibility.MODERATE
        assert r.estimated_savings_hours == 0.0
        assert r.implementation_effort_days == 0.0
        assert r.created_at > 0

    def test_gap_report_defaults(self):
        r = AutomationGapReport()
        assert r.total_gaps == 0
        assert r.total_candidates == 0
        assert r.avg_roi_score == 0.0
        assert r.by_category == {}
        assert r.by_feasibility == {}
        assert r.quick_win_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordGap:
    def test_basic(self):
        eng = _engine()
        r = eng.record_gap("deploy-manual", roi_score=80.0)
        assert r.gap_name == "deploy-manual"
        assert r.roi_score == 80.0

    def test_with_category(self):
        eng = _engine()
        r = eng.record_gap("g1", category=GapCategory.REPETITIVE_TASK)
        assert r.category == GapCategory.REPETITIVE_TASK

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(f"g-{i}")
        assert len(eng._records) == 3


class TestGetGap:
    def test_found(self):
        eng = _engine()
        r = eng.record_gap("g1")
        assert eng.get_gap(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_gap("nonexistent") is None


class TestListGaps:
    def test_list_all(self):
        eng = _engine()
        eng.record_gap("g1")
        eng.record_gap("g2")
        assert len(eng.list_gaps()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_gap("g1", category=GapCategory.MANUAL_PROCESS)
        eng.record_gap("g2", category=GapCategory.ERROR_PRONE)
        results = eng.list_gaps(category=GapCategory.MANUAL_PROCESS)
        assert len(results) == 1

    def test_filter_by_feasibility(self):
        eng = _engine()
        eng.record_gap("g1", feasibility=AutomationFeasibility.EASY)
        eng.record_gap("g2", feasibility=AutomationFeasibility.DIFFICULT)
        results = eng.list_gaps(feasibility=AutomationFeasibility.EASY)
        assert len(results) == 1


class TestAddCandidate:
    def test_basic(self):
        eng = _engine()
        c = eng.add_candidate(
            "auto-deploy",
            gap_name="deploy-manual",
            estimated_savings_hours=10.0,
        )
        assert c.candidate_name == "auto-deploy"
        assert c.estimated_savings_hours == 10.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_candidate(f"c-{i}")
        assert len(eng._candidates) == 2


class TestAnalyzeGapCategory:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap("g1", category=GapCategory.MANUAL_PROCESS, roi_score=80.0)
        result = eng.analyze_gap_category("manual_process")
        assert result["category"] == "manual_process"
        assert result["total_gaps"] == 1

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_gap_category("ghost")
        assert result["status"] == "no_data"


class TestIdentifyQuickWins:
    def test_with_quick_wins(self):
        eng = _engine(min_roi_score=50.0)
        eng.record_gap(
            "g1",
            feasibility=AutomationFeasibility.EASY,
            roi_score=80.0,
        )
        eng.record_gap(
            "g2",
            feasibility=AutomationFeasibility.DIFFICULT,
            roi_score=90.0,
        )
        results = eng.identify_quick_wins()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_quick_wins() == []


class TestRankByRoi:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap("g1", roi_score=30.0)
        eng.record_gap("g2", roi_score=90.0)
        results = eng.rank_by_roi()
        assert results[0]["roi_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_roi() == []


class TestDetectRepetitivePatterns:
    def test_with_repetitive(self):
        eng = _engine()
        eng.record_gap("g1", category=GapCategory.REPETITIVE_TASK, hours_per_week=10.0)
        eng.record_gap("g2", category=GapCategory.MANUAL_PROCESS)
        results = eng.detect_repetitive_patterns()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_repetitive_patterns() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_roi_score=50.0)
        eng.record_gap(
            "g1",
            feasibility=AutomationFeasibility.EASY,
            roi_score=80.0,
            impact=GapImpact.HIGH,
        )
        eng.add_candidate("c1")
        report = eng.generate_report()
        assert report.total_gaps == 1
        assert report.total_candidates == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_gaps == 0
        assert "No significant" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_gap("g1")
        eng.add_candidate("c1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._candidates) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_gaps"] == 0
        assert stats["total_candidates"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_gap("g1", category=GapCategory.MANUAL_PROCESS)
        eng.record_gap("g2", category=GapCategory.ERROR_PRONE)
        eng.add_candidate("c1")
        stats = eng.get_stats()
        assert stats["total_gaps"] == 2
        assert stats["total_candidates"] == 1
        assert stats["unique_gaps"] == 2
