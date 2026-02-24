"""Tests for shieldops.incidents.oncall_optimizer — OnCallRotationOptimizer."""

from __future__ import annotations

from shieldops.incidents.oncall_optimizer import (
    CoverageGap,
    FairnessMetric,
    OnCallRotationOptimizer,
    RotationMember,
    RotationReport,
    RotationSchedule,
    RotationStrategy,
)


def _engine(**kw) -> OnCallRotationOptimizer:
    return OnCallRotationOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RotationStrategy (5)
    def test_strategy_round_robin(self):
        assert RotationStrategy.ROUND_ROBIN == "round_robin"

    def test_strategy_timezone_follow(self):
        assert RotationStrategy.TIMEZONE_FOLLOW == "timezone_follow"

    def test_strategy_skill_based(self):
        assert RotationStrategy.SKILL_BASED == "skill_based"

    def test_strategy_load_balanced(self):
        assert RotationStrategy.LOAD_BALANCED == "load_balanced"

    def test_strategy_hybrid(self):
        assert RotationStrategy.HYBRID == "hybrid"

    # FairnessMetric (5)
    def test_fairness_equal_hours(self):
        assert FairnessMetric.EQUAL_HOURS == "equal_hours"

    def test_fairness_equal_pages(self):
        assert FairnessMetric.EQUAL_PAGES == "equal_pages"

    def test_fairness_equal_severity(self):
        assert FairnessMetric.EQUAL_SEVERITY == "equal_severity"

    def test_fairness_equal_after_hours(self):
        assert FairnessMetric.EQUAL_AFTER_HOURS == "equal_after_hours"

    def test_fairness_composite(self):
        assert FairnessMetric.COMPOSITE == "composite"

    # CoverageGap (5)
    def test_gap_timezone_uncovered(self):
        assert CoverageGap.TIMEZONE_UNCOVERED == "timezone_uncovered"

    def test_gap_skill_missing(self):
        assert CoverageGap.SKILL_MISSING == "skill_missing"

    def test_gap_single_point(self):
        assert CoverageGap.SINGLE_POINT == "single_point"

    def test_gap_consecutive_days(self):
        assert CoverageGap.CONSECUTIVE_DAYS == "consecutive_days"

    def test_gap_holiday_uncovered(self):
        assert CoverageGap.HOLIDAY_UNCOVERED == "holiday_uncovered"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rotation_member_defaults(self):
        m = RotationMember()
        assert m.id
        assert m.name == ""
        assert m.email == ""
        assert m.timezone == "UTC"
        assert m.skills == []
        assert m.total_hours == 0.0
        assert m.total_pages == 0
        assert m.consecutive_days == 0
        assert m.is_available is True

    def test_rotation_schedule_defaults(self):
        s = RotationSchedule()
        assert s.id
        assert s.strategy == RotationStrategy.ROUND_ROBIN
        assert s.members == []
        assert s.fairness_score == 0.0
        assert s.gaps == []

    def test_rotation_report_defaults(self):
        r = RotationReport()
        assert r.total_members == 0
        assert r.total_schedules == 0
        assert r.avg_fairness_score == 0.0
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# register_member
# ---------------------------------------------------------------------------


class TestRegisterMember:
    def test_basic_register(self):
        eng = _engine()
        m = eng.register_member(name="Alice", email="alice@test.com", timezone="US/Eastern")
        assert m.name == "Alice"
        assert m.email == "alice@test.com"
        assert m.timezone == "US/Eastern"

    def test_unique_ids(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice")
        m2 = eng.register_member(name="Bob")
        assert m1.id != m2.id

    def test_skills(self):
        eng = _engine()
        m = eng.register_member(name="Alice", skills=["k8s", "aws"])
        assert m.skills == ["k8s", "aws"]

    def test_eviction_at_max(self):
        eng = _engine(max_members=3)
        for i in range(5):
            eng.register_member(name=f"Member-{i}")
        assert len(eng._members) == 3


# ---------------------------------------------------------------------------
# get_member
# ---------------------------------------------------------------------------


class TestGetMember:
    def test_found(self):
        eng = _engine()
        m = eng.register_member(name="Alice")
        assert eng.get_member(m.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_member("nonexistent") is None


# ---------------------------------------------------------------------------
# list_members
# ---------------------------------------------------------------------------


class TestListMembers:
    def test_list_all(self):
        eng = _engine()
        eng.register_member(name="Alice")
        eng.register_member(name="Bob")
        assert len(eng.list_members()) == 2

    def test_filter_timezone(self):
        eng = _engine()
        eng.register_member(name="Alice", timezone="US/Eastern")
        eng.register_member(name="Bob", timezone="Europe/London")
        results = eng.list_members(timezone="US/Eastern")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_filter_available(self):
        eng = _engine()
        eng.register_member(name="Alice")
        bob = eng.register_member(name="Bob")
        bob.is_available = False
        results = eng.list_members(is_available=True)
        assert len(results) == 1
        assert results[0].name == "Alice"


# ---------------------------------------------------------------------------
# generate_schedule
# ---------------------------------------------------------------------------


class TestGenerateSchedule:
    def test_basic_schedule(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice")
        m2 = eng.register_member(name="Bob")
        s = eng.generate_schedule(
            strategy=RotationStrategy.ROUND_ROBIN,
            member_ids=[m1.id, m2.id],
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        assert s.strategy == RotationStrategy.ROUND_ROBIN
        assert len(s.members) == 2
        assert s.start_date == "2026-01-01"

    def test_fairness_score_equal_hours(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice")
        m2 = eng.register_member(name="Bob")
        # Both have 0 hours, so std_dev = 0 => score = 100
        s = eng.generate_schedule(
            strategy=RotationStrategy.LOAD_BALANCED,
            member_ids=[m1.id, m2.id],
        )
        assert s.fairness_score == 100.0

    def test_fairness_score_unequal_hours(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice")
        m2 = eng.register_member(name="Bob")
        eng.track_actual_load(m1.id, hours=20.0)
        eng.track_actual_load(m2.id, hours=0.0)
        s = eng.generate_schedule(
            strategy=RotationStrategy.LOAD_BALANCED,
            member_ids=[m1.id, m2.id],
        )
        # std_dev = 10, score = max(0, 100 - 10*10) = 0
        assert s.fairness_score == 0.0

    def test_gaps_consecutive_days(self):
        eng = _engine(max_consecutive_days=5)
        m1 = eng.register_member(name="Alice")
        m1.consecutive_days = 8
        s = eng.generate_schedule(
            strategy=RotationStrategy.ROUND_ROBIN,
            member_ids=[m1.id],
        )
        assert any("consecutive_days" in g for g in s.gaps)


# ---------------------------------------------------------------------------
# calculate_fairness_score
# ---------------------------------------------------------------------------


class TestCalculateFairnessScore:
    def test_schedule_not_found(self):
        eng = _engine()
        result = eng.calculate_fairness_score("nonexistent")
        assert result["fairness_score"] == 0.0

    def test_with_data(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice")
        m2 = eng.register_member(name="Bob")
        eng.track_actual_load(m1.id, hours=10.0)
        eng.track_actual_load(m2.id, hours=10.0)
        s = eng.generate_schedule(
            strategy=RotationStrategy.ROUND_ROBIN,
            member_ids=[m1.id, m2.id],
        )
        result = eng.calculate_fairness_score(s.id)
        assert result["fairness_score"] == 100.0
        assert result["member_hours"]["Alice"] == 10.0
        assert result["max_deviation"] == 0.0


# ---------------------------------------------------------------------------
# detect_coverage_gaps
# ---------------------------------------------------------------------------


class TestDetectCoverageGaps:
    def test_no_gaps(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice", timezone="UTC")
        m2 = eng.register_member(name="Bob", timezone="UTC")
        s = eng.generate_schedule(
            strategy=RotationStrategy.ROUND_ROBIN,
            member_ids=[m1.id, m2.id],
        )
        gaps = eng.detect_coverage_gaps(schedule_id=s.id)
        # Two members in same timezone, neither over consecutive days
        assert not any("consecutive_days" in g for g in gaps)

    def test_single_point_timezone(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice", timezone="US/Eastern")
        m2 = eng.register_member(name="Bob", timezone="Europe/London")
        s = eng.generate_schedule(
            strategy=RotationStrategy.ROUND_ROBIN,
            member_ids=[m1.id, m2.id],
        )
        gaps = eng.detect_coverage_gaps(schedule_id=s.id)
        assert any("single_point" in g for g in gaps)

    def test_skill_missing(self):
        eng = _engine()
        eng.register_member(name="Alice", skills=["k8s"])
        eng.register_member(name="Bob", skills=[])
        gaps = eng.detect_coverage_gaps()
        assert any("skill_missing" in g for g in gaps)


# ---------------------------------------------------------------------------
# optimize_handoffs
# ---------------------------------------------------------------------------


class TestOptimizeHandoffs:
    def test_empty(self):
        eng = _engine()
        assert eng.optimize_handoffs() == []

    def test_with_timezone_members(self):
        eng = _engine()
        eng.register_member(name="Alice", timezone="US/Eastern")
        eng.register_member(name="Bob", timezone="US/Pacific")
        handoffs = eng.optimize_handoffs()
        assert len(handoffs) == 1
        assert "from_member" in handoffs[0]
        assert "to_member" in handoffs[0]
        assert "suggested_time" in handoffs[0]


# ---------------------------------------------------------------------------
# track_actual_load
# ---------------------------------------------------------------------------


class TestTrackActualLoad:
    def test_success(self):
        eng = _engine()
        m = eng.register_member(name="Alice")
        result = eng.track_actual_load(m.id, hours=8.0, pages=3)
        assert result is not None
        assert result.total_hours == 8.0
        assert result.total_pages == 3

    def test_cumulative(self):
        eng = _engine()
        m = eng.register_member(name="Alice")
        eng.track_actual_load(m.id, hours=4.0, pages=1)
        eng.track_actual_load(m.id, hours=6.0, pages=2)
        assert m.total_hours == 10.0
        assert m.total_pages == 3

    def test_not_found(self):
        eng = _engine()
        assert eng.track_actual_load("bad-id", hours=1.0) is None


# ---------------------------------------------------------------------------
# generate_rotation_report
# ---------------------------------------------------------------------------


class TestGenerateRotationReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_rotation_report()
        assert report.total_members == 0
        assert report.total_schedules == 0

    def test_with_data(self):
        eng = _engine()
        m1 = eng.register_member(name="Alice", timezone="UTC")
        m2 = eng.register_member(name="Bob", timezone="US/Eastern")
        eng.generate_schedule(
            strategy=RotationStrategy.ROUND_ROBIN,
            member_ids=[m1.id, m2.id],
        )
        report = eng.generate_rotation_report()
        assert report.total_members == 2
        assert report.total_schedules == 1
        assert RotationStrategy.ROUND_ROBIN in report.by_strategy


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.register_member(name="Alice")
        eng.generate_schedule(
            strategy=RotationStrategy.ROUND_ROBIN,
            member_ids=[],
        )
        eng.clear_data()
        assert len(eng._members) == 0
        assert len(eng._schedules) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_members"] == 0
        assert stats["total_schedules"] == 0

    def test_populated(self):
        eng = _engine()
        eng.register_member(name="Alice", timezone="UTC", skills=["k8s"])
        eng.register_member(name="Bob", timezone="US/Eastern", skills=["aws"])
        stats = eng.get_stats()
        assert stats["total_members"] == 2
        assert stats["available_members"] == 2
        assert "UTC" in stats["timezone_distribution"]
        assert "k8s" in stats["skill_distribution"]
