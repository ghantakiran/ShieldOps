"""Tests for shieldops.security.purple_team_exercise_tracker — PurpleTeamExerciseTracker."""

from __future__ import annotations

from shieldops.security.purple_team_exercise_tracker import (
    ControlEffectiveness,
    ExerciseAnalysis,
    ExerciseOutcome,
    ExerciseRecord,
    ExerciseReport,
    ExerciseType,
    PurpleTeamExerciseTracker,
)


def _engine(**kw) -> PurpleTeamExerciseTracker:
    return PurpleTeamExerciseTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_full_simulation(self):
        assert ExerciseType.FULL_SIMULATION == "full_simulation"

    def test_type_tabletop(self):
        assert ExerciseType.TABLETOP == "tabletop"

    def test_type_adversary_emulation(self):
        assert ExerciseType.ADVERSARY_EMULATION == "adversary_emulation"

    def test_type_control_validation(self):
        assert ExerciseType.CONTROL_VALIDATION == "control_validation"

    def test_type_detection_test(self):
        assert ExerciseType.DETECTION_TEST == "detection_test"

    def test_outcome_all_detected(self):
        assert ExerciseOutcome.ALL_DETECTED == "all_detected"

    def test_outcome_mostly_detected(self):
        assert ExerciseOutcome.MOSTLY_DETECTED == "mostly_detected"

    def test_outcome_partially_detected(self):
        assert ExerciseOutcome.PARTIALLY_DETECTED == "partially_detected"

    def test_outcome_mostly_missed(self):
        assert ExerciseOutcome.MOSTLY_MISSED == "mostly_missed"

    def test_outcome_all_missed(self):
        assert ExerciseOutcome.ALL_MISSED == "all_missed"

    def test_effectiveness_excellent(self):
        assert ControlEffectiveness.EXCELLENT == "excellent"

    def test_effectiveness_good(self):
        assert ControlEffectiveness.GOOD == "good"

    def test_effectiveness_moderate(self):
        assert ControlEffectiveness.MODERATE == "moderate"

    def test_effectiveness_weak(self):
        assert ControlEffectiveness.WEAK == "weak"

    def test_effectiveness_ineffective(self):
        assert ControlEffectiveness.INEFFECTIVE == "ineffective"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_exercise_record_defaults(self):
        r = ExerciseRecord()
        assert r.id
        assert r.exercise_name == ""
        assert r.exercise_type == ExerciseType.FULL_SIMULATION
        assert r.exercise_outcome == ExerciseOutcome.ALL_DETECTED
        assert r.control_effectiveness == ControlEffectiveness.EXCELLENT
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_exercise_analysis_defaults(self):
        c = ExerciseAnalysis()
        assert c.id
        assert c.exercise_name == ""
        assert c.exercise_type == ExerciseType.FULL_SIMULATION
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_exercise_report_defaults(self):
        r = ExerciseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.by_effectiveness == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_exercise
# ---------------------------------------------------------------------------


class TestRecordExercise:
    def test_basic(self):
        eng = _engine()
        r = eng.record_exercise(
            exercise_name="apt-sim-001",
            exercise_type=ExerciseType.ADVERSARY_EMULATION,
            exercise_outcome=ExerciseOutcome.MOSTLY_DETECTED,
            control_effectiveness=ControlEffectiveness.GOOD,
            effectiveness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.exercise_name == "apt-sim-001"
        assert r.exercise_type == ExerciseType.ADVERSARY_EMULATION
        assert r.exercise_outcome == ExerciseOutcome.MOSTLY_DETECTED
        assert r.control_effectiveness == ControlEffectiveness.GOOD
        assert r.effectiveness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_exercise(exercise_name=f"E-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_exercise
# ---------------------------------------------------------------------------


class TestGetExercise:
    def test_found(self):
        eng = _engine()
        r = eng.record_exercise(
            exercise_name="apt-sim-001",
            control_effectiveness=ControlEffectiveness.EXCELLENT,
        )
        result = eng.get_exercise(r.id)
        assert result is not None
        assert result.control_effectiveness == ControlEffectiveness.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_exercise("nonexistent") is None


# ---------------------------------------------------------------------------
# list_exercises
# ---------------------------------------------------------------------------


class TestListExercises:
    def test_list_all(self):
        eng = _engine()
        eng.record_exercise(exercise_name="E-001")
        eng.record_exercise(exercise_name="E-002")
        assert len(eng.list_exercises()) == 2

    def test_filter_by_exercise_type(self):
        eng = _engine()
        eng.record_exercise(
            exercise_name="E-001",
            exercise_type=ExerciseType.FULL_SIMULATION,
        )
        eng.record_exercise(
            exercise_name="E-002",
            exercise_type=ExerciseType.TABLETOP,
        )
        results = eng.list_exercises(exercise_type=ExerciseType.FULL_SIMULATION)
        assert len(results) == 1

    def test_filter_by_exercise_outcome(self):
        eng = _engine()
        eng.record_exercise(
            exercise_name="E-001",
            exercise_outcome=ExerciseOutcome.ALL_DETECTED,
        )
        eng.record_exercise(
            exercise_name="E-002",
            exercise_outcome=ExerciseOutcome.ALL_MISSED,
        )
        results = eng.list_exercises(
            exercise_outcome=ExerciseOutcome.ALL_DETECTED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_exercise(exercise_name="E-001", team="security")
        eng.record_exercise(exercise_name="E-002", team="platform")
        results = eng.list_exercises(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_exercise(exercise_name=f"E-{i}")
        assert len(eng.list_exercises(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            exercise_name="apt-sim-001",
            exercise_type=ExerciseType.ADVERSARY_EMULATION,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="effectiveness gap detected",
        )
        assert a.exercise_name == "apt-sim-001"
        assert a.exercise_type == ExerciseType.ADVERSARY_EMULATION
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(exercise_name=f"E-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_type_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_exercise(
            exercise_name="E-001",
            exercise_type=ExerciseType.FULL_SIMULATION,
            effectiveness_score=90.0,
        )
        eng.record_exercise(
            exercise_name="E-002",
            exercise_type=ExerciseType.FULL_SIMULATION,
            effectiveness_score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "full_simulation" in result
        assert result["full_simulation"]["count"] == 2
        assert result["full_simulation"]["avg_effectiveness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness_exercises
# ---------------------------------------------------------------------------


class TestIdentifyLowEffectivenessExercises:
    def test_detects_below_threshold(self):
        eng = _engine(exercise_effectiveness_threshold=80.0)
        eng.record_exercise(exercise_name="E-001", effectiveness_score=60.0)
        eng.record_exercise(exercise_name="E-002", effectiveness_score=90.0)
        results = eng.identify_low_effectiveness_exercises()
        assert len(results) == 1
        assert results[0]["exercise_name"] == "E-001"

    def test_sorted_ascending(self):
        eng = _engine(exercise_effectiveness_threshold=80.0)
        eng.record_exercise(exercise_name="E-001", effectiveness_score=50.0)
        eng.record_exercise(exercise_name="E-002", effectiveness_score=30.0)
        results = eng.identify_low_effectiveness_exercises()
        assert len(results) == 2
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness_exercises() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness_score
# ---------------------------------------------------------------------------


class TestRankByEffectivenessScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_exercise(exercise_name="E-001", service="auth-svc", effectiveness_score=90.0)
        eng.record_exercise(exercise_name="E-002", service="api-gw", effectiveness_score=50.0)
        results = eng.rank_by_effectiveness_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_effectiveness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness_score() == []


# ---------------------------------------------------------------------------
# detect_effectiveness_trends
# ---------------------------------------------------------------------------


class TestDetectEffectivenessTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(exercise_name="E-001", analysis_score=50.0)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(exercise_name="E-001", analysis_score=20.0)
        eng.add_analysis(exercise_name="E-002", analysis_score=20.0)
        eng.add_analysis(exercise_name="E-003", analysis_score=80.0)
        eng.add_analysis(exercise_name="E-004", analysis_score=80.0)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(exercise_effectiveness_threshold=80.0)
        eng.record_exercise(
            exercise_name="apt-sim-001",
            exercise_type=ExerciseType.ADVERSARY_EMULATION,
            exercise_outcome=ExerciseOutcome.MOSTLY_DETECTED,
            control_effectiveness=ControlEffectiveness.GOOD,
            effectiveness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ExerciseReport)
        assert report.total_records == 1
        assert report.low_effectiveness_count == 1
        assert len(report.top_low_effectiveness) == 1
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
        eng.record_exercise(exercise_name="E-001")
        eng.add_analysis(exercise_name="E-001")
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
        eng.record_exercise(
            exercise_name="E-001",
            exercise_type=ExerciseType.FULL_SIMULATION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "full_simulation" in stats["type_distribution"]
