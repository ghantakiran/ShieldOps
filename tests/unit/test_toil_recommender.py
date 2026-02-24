"""Tests for shieldops.operations.toil_recommender — ToilAutomationRecommender."""

from __future__ import annotations

from shieldops.operations.toil_recommender import (
    AutomationCategory,
    AutomationDifficulty,
    AutomationRecommendation,
    ROITimeframe,
    ToilAutomationRecommender,
    ToilPattern,
    ToilRecommenderReport,
)


def _engine(**kw) -> ToilAutomationRecommender:
    return ToilAutomationRecommender(**kw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestAutomationDifficulty:
    """Test every AutomationDifficulty member."""

    def test_trivial(self):
        assert AutomationDifficulty.TRIVIAL == "trivial"

    def test_easy(self):
        assert AutomationDifficulty.EASY == "easy"

    def test_moderate(self):
        assert AutomationDifficulty.MODERATE == "moderate"

    def test_hard(self):
        assert AutomationDifficulty.HARD == "hard"

    def test_requires_platform_change(self):
        assert AutomationDifficulty.REQUIRES_PLATFORM_CHANGE == "requires_platform_change"


class TestAutomationCategory:
    """Test every AutomationCategory member."""

    def test_script(self):
        assert AutomationCategory.SCRIPT == "script"

    def test_runbook(self):
        assert AutomationCategory.RUNBOOK == "runbook"

    def test_pipeline(self):
        assert AutomationCategory.PIPELINE == "pipeline"

    def test_self_service(self):
        assert AutomationCategory.SELF_SERVICE == "self_service"

    def test_ai_agent(self):
        assert AutomationCategory.AI_AGENT == "ai_agent"


class TestROITimeframe:
    """Test every ROITimeframe member."""

    def test_one_month(self):
        assert ROITimeframe.ONE_MONTH == "one_month"

    def test_three_months(self):
        assert ROITimeframe.THREE_MONTHS == "three_months"

    def test_six_months(self):
        assert ROITimeframe.SIX_MONTHS == "six_months"

    def test_one_year(self):
        assert ROITimeframe.ONE_YEAR == "one_year"

    def test_two_years(self):
        assert ROITimeframe.TWO_YEARS == "two_years"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test model defaults."""

    def test_toil_pattern_defaults(self):
        m = ToilPattern()
        assert m.id
        assert m.task_name == ""
        assert m.team == ""
        assert m.frequency_per_week == 0.0
        assert m.time_per_occurrence_minutes == 0.0
        assert m.automation_difficulty == AutomationDifficulty.MODERATE
        assert m.is_automatable is True
        assert m.monthly_hours == 0.0

    def test_automation_recommendation_defaults(self):
        m = AutomationRecommendation()
        assert m.id
        assert m.pattern_id == ""
        assert m.category == AutomationCategory.SCRIPT
        assert m.estimated_implementation_hours == 0.0
        assert m.roi_multiplier == 0.0
        assert m.timeframe == ROITimeframe.SIX_MONTHS

    def test_toil_recommender_report_defaults(self):
        m = ToilRecommenderReport()
        assert m.total_patterns == 0
        assert m.total_monthly_toil_hours == 0.0
        assert m.automatable_count == 0
        assert m.by_difficulty == {}
        assert m.quick_wins == []
        assert m.recommendations == []


# ---------------------------------------------------------------------------
# record_toil_pattern
# ---------------------------------------------------------------------------


class TestRecordToilPattern:
    """Test ToilAutomationRecommender.record_toil_pattern."""

    def test_basic_monthly_hours_calculation(self):
        eng = _engine()
        pat = eng.record_toil_pattern(
            task_name="restart-pods",
            team="sre",
            frequency_per_week=5.0,
            time_per_occurrence_minutes=30.0,
            automation_difficulty=AutomationDifficulty.EASY,
        )
        assert pat.task_name == "restart-pods"
        assert pat.team == "sre"
        # monthly_hours = 5 * 4.33 * 30 / 60 = 10.825
        expected = round(5.0 * 4.33 * 30.0 / 60.0, 2)
        assert pat.monthly_hours == expected

    def test_eviction(self):
        eng = _engine(max_patterns=2)
        eng.record_toil_pattern(task_name="a")
        eng.record_toil_pattern(task_name="b")
        eng.record_toil_pattern(task_name="c")
        patterns = eng.list_patterns()
        assert len(patterns) == 2
        assert patterns[0].task_name == "b"
        assert patterns[1].task_name == "c"


# ---------------------------------------------------------------------------
# get_pattern
# ---------------------------------------------------------------------------


class TestGetPattern:
    """Test ToilAutomationRecommender.get_pattern."""

    def test_found(self):
        eng = _engine()
        pat = eng.record_toil_pattern(task_name="deploy-check")
        found = eng.get_pattern(pat.id)
        assert found is not None
        assert found.task_name == "deploy-check"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_pattern("nonexistent") is None


# ---------------------------------------------------------------------------
# list_patterns
# ---------------------------------------------------------------------------


class TestListPatterns:
    """Test ToilAutomationRecommender.list_patterns."""

    def test_all(self):
        eng = _engine()
        eng.record_toil_pattern(task_name="a")
        eng.record_toil_pattern(task_name="b")
        assert len(eng.list_patterns()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_toil_pattern(task_name="x", team="sre")
        eng.record_toil_pattern(task_name="y", team="dev")
        eng.record_toil_pattern(task_name="z", team="sre")
        result = eng.list_patterns(team="sre")
        assert len(result) == 2
        assert all(p.team == "sre" for p in result)

    def test_filter_by_difficulty(self):
        eng = _engine()
        eng.record_toil_pattern(task_name="a", automation_difficulty=AutomationDifficulty.TRIVIAL)
        eng.record_toil_pattern(task_name="b", automation_difficulty=AutomationDifficulty.HARD)
        result = eng.list_patterns(difficulty=AutomationDifficulty.TRIVIAL)
        assert len(result) == 1
        assert result[0].task_name == "a"


# ---------------------------------------------------------------------------
# recommend_automation
# ---------------------------------------------------------------------------


class TestRecommendAutomation:
    """Test ToilAutomationRecommender.recommend_automation."""

    def test_trivial_maps_to_script_with_4h(self):
        eng = _engine()
        pat = eng.record_toil_pattern(
            task_name="clear-cache",
            frequency_per_week=10.0,
            time_per_occurrence_minutes=15.0,
            automation_difficulty=AutomationDifficulty.TRIVIAL,
        )
        rec = eng.recommend_automation(pat.id)
        assert rec is not None
        assert rec.category == AutomationCategory.SCRIPT
        assert rec.estimated_implementation_hours == 4.0
        assert rec.estimated_monthly_savings_hours == pat.monthly_hours

    def test_hard_maps_to_self_service_with_80h(self):
        eng = _engine()
        pat = eng.record_toil_pattern(
            task_name="provision-env",
            frequency_per_week=2.0,
            time_per_occurrence_minutes=60.0,
            automation_difficulty=AutomationDifficulty.HARD,
        )
        rec = eng.recommend_automation(pat.id)
        assert rec is not None
        assert rec.category == AutomationCategory.SELF_SERVICE
        assert rec.estimated_implementation_hours == 80.0

    def test_not_found_returns_none(self):
        eng = _engine()
        assert eng.recommend_automation("does-not-exist") is None

    def test_roi_multiplier_and_timeframe(self):
        eng = _engine()
        # TRIVIAL with very high monthly hours -> quick breakeven -> ONE_MONTH timeframe
        pat = eng.record_toil_pattern(
            task_name="high-freq",
            frequency_per_week=40.0,
            time_per_occurrence_minutes=60.0,
            automation_difficulty=AutomationDifficulty.TRIVIAL,
        )
        rec = eng.recommend_automation(pat.id)
        assert rec is not None
        # monthly_hours = 40 * 4.33 * 60 / 60 = 173.2
        # impl = 4h, breakeven = 4/173.2 ~ 0.023 months -> ONE_MONTH
        assert rec.timeframe == ROITimeframe.ONE_MONTH
        assert rec.roi_multiplier > 1.0


# ---------------------------------------------------------------------------
# estimate_roi
# ---------------------------------------------------------------------------


class TestEstimateROI:
    """Test ToilAutomationRecommender.estimate_roi."""

    def test_basic_roi_calculation(self):
        eng = _engine()
        pat = eng.record_toil_pattern(
            task_name="log-rotate",
            frequency_per_week=7.0,
            time_per_occurrence_minutes=10.0,
            automation_difficulty=AutomationDifficulty.TRIVIAL,
        )
        roi = eng.estimate_roi(pat.id)
        assert roi["pattern_id"] == pat.id
        assert roi["implementation_hours"] == 4.0
        assert roi["monthly_savings_hours"] == pat.monthly_hours
        # ROI = (monthly_savings * 12) / impl_hours
        expected_roi = round((pat.monthly_hours * 12) / 4.0, 2)
        assert roi["roi_multiplier"] == expected_roi
        assert roi["breakeven_months"] > 0

    def test_not_found(self):
        eng = _engine()
        roi = eng.estimate_roi("missing")
        assert roi["monthly_savings_hours"] == 0.0
        assert roi["roi_multiplier"] == 0.0


# ---------------------------------------------------------------------------
# rank_by_roi
# ---------------------------------------------------------------------------


class TestRankByROI:
    """Test ToilAutomationRecommender.rank_by_roi."""

    def test_multiple_patterns_sorted_descending(self):
        eng = _engine()
        # High ROI pattern: frequent + trivial
        eng.record_toil_pattern(
            task_name="high-roi",
            frequency_per_week=20.0,
            time_per_occurrence_minutes=30.0,
            automation_difficulty=AutomationDifficulty.TRIVIAL,
        )
        # Low ROI pattern: infrequent + hard
        eng.record_toil_pattern(
            task_name="low-roi",
            frequency_per_week=1.0,
            time_per_occurrence_minutes=5.0,
            automation_difficulty=AutomationDifficulty.HARD,
        )
        ranked = eng.rank_by_roi()
        assert len(ranked) == 2
        assert ranked[0].roi_multiplier >= ranked[1].roi_multiplier


# ---------------------------------------------------------------------------
# calculate_time_saved
# ---------------------------------------------------------------------------


class TestCalculateTimeSaved:
    """Test ToilAutomationRecommender.calculate_time_saved."""

    def test_all_teams(self):
        eng = _engine()
        eng.record_toil_pattern(
            task_name="a", team="sre", frequency_per_week=5.0, time_per_occurrence_minutes=10.0
        )
        eng.record_toil_pattern(
            task_name="b", team="dev", frequency_per_week=3.0, time_per_occurrence_minutes=20.0
        )
        result = eng.calculate_time_saved()
        assert result["team"] == "all"
        assert result["total_monthly_toil_hours"] > 0
        assert result["automatable_hours"] > 0

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_toil_pattern(
            task_name="a", team="sre", frequency_per_week=5.0, time_per_occurrence_minutes=10.0
        )
        eng.record_toil_pattern(
            task_name="b", team="dev", frequency_per_week=3.0, time_per_occurrence_minutes=20.0
        )
        result = eng.calculate_time_saved(team="sre")
        assert result["team"] == "sre"
        expected_monthly = round(5.0 * 4.33 * 10.0 / 60.0, 2)
        assert result["total_monthly_toil_hours"] == expected_monthly


# ---------------------------------------------------------------------------
# identify_quick_wins
# ---------------------------------------------------------------------------


class TestIdentifyQuickWins:
    """Test ToilAutomationRecommender.identify_quick_wins."""

    def test_trivial_and_easy_with_sufficient_hours(self):
        eng = _engine()
        # Quick win: TRIVIAL, high hours
        eng.record_toil_pattern(
            task_name="quick",
            frequency_per_week=10.0,
            time_per_occurrence_minutes=30.0,
            automation_difficulty=AutomationDifficulty.TRIVIAL,
        )
        # Quick win: EASY, high hours
        eng.record_toil_pattern(
            task_name="easy-win",
            frequency_per_week=5.0,
            time_per_occurrence_minutes=20.0,
            automation_difficulty=AutomationDifficulty.EASY,
        )
        # Not a quick win: HARD
        eng.record_toil_pattern(
            task_name="hard-task",
            frequency_per_week=10.0,
            time_per_occurrence_minutes=30.0,
            automation_difficulty=AutomationDifficulty.HARD,
        )
        # Not a quick win: TRIVIAL but monthly_hours <= 1
        eng.record_toil_pattern(
            task_name="tiny",
            frequency_per_week=0.1,
            time_per_occurrence_minutes=1.0,
            automation_difficulty=AutomationDifficulty.TRIVIAL,
        )
        wins = eng.identify_quick_wins()
        assert len(wins) == 2
        names = {w.task_name for w in wins}
        assert "quick" in names
        assert "easy-win" in names


# ---------------------------------------------------------------------------
# generate_recommender_report
# ---------------------------------------------------------------------------


class TestGenerateRecommenderReport:
    """Test ToilAutomationRecommender.generate_recommender_report."""

    def test_basic(self):
        eng = _engine()
        eng.record_toil_pattern(
            task_name="task-a",
            team="sre",
            frequency_per_week=5.0,
            time_per_occurrence_minutes=15.0,
            automation_difficulty=AutomationDifficulty.EASY,
        )
        eng.record_toil_pattern(
            task_name="task-b",
            team="dev",
            frequency_per_week=3.0,
            time_per_occurrence_minutes=10.0,
            automation_difficulty=AutomationDifficulty.HARD,
            is_automatable=False,
        )
        report = eng.generate_recommender_report()
        assert isinstance(report, ToilRecommenderReport)
        assert report.total_patterns == 2
        assert report.automatable_count == 1
        assert report.total_monthly_toil_hours > 0
        assert "easy" in report.by_difficulty
        assert "hard" in report.by_difficulty

    def test_report_includes_non_automatable_recommendation(self):
        eng = _engine()
        eng.record_toil_pattern(task_name="manual", is_automatable=False)
        report = eng.generate_recommender_report()
        assert any("non-automatable" in r for r in report.recommendations)

    def test_report_quick_wins_listed(self):
        eng = _engine()
        eng.record_toil_pattern(
            task_name="easy-task",
            frequency_per_week=10.0,
            time_per_occurrence_minutes=20.0,
            automation_difficulty=AutomationDifficulty.TRIVIAL,
        )
        report = eng.generate_recommender_report()
        assert len(report.quick_wins) == 1
        assert "easy-task" in report.quick_wins[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    """Test ToilAutomationRecommender.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.record_toil_pattern(task_name="x")
        pat = eng.record_toil_pattern(task_name="y")
        eng.recommend_automation(pat.id)
        eng.clear_data()
        assert eng.list_patterns() == []
        stats = eng.get_stats()
        assert stats["total_patterns"] == 0
        assert stats["total_recommendations"] == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Test ToilAutomationRecommender.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_patterns"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["unique_teams"] == 0
        assert stats["automatable_count"] == 0
        assert stats["total_monthly_toil_hours"] == 0.0

    def test_populated(self):
        eng = _engine()
        pat = eng.record_toil_pattern(
            task_name="a",
            team="sre",
            frequency_per_week=5.0,
            time_per_occurrence_minutes=10.0,
        )
        eng.record_toil_pattern(task_name="b", team="dev", is_automatable=False)
        eng.recommend_automation(pat.id)
        stats = eng.get_stats()
        assert stats["total_patterns"] == 2
        assert stats["total_recommendations"] == 1
        assert stats["unique_teams"] == 2
        assert stats["automatable_count"] == 1
        assert stats["total_monthly_toil_hours"] > 0
