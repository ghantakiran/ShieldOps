"""Tests for shieldops.analytics.review_velocity — CodeReviewVelocityTracker."""

from __future__ import annotations

from shieldops.analytics.review_velocity import (
    CodeReviewVelocityTracker,
    ReviewBottleneck,
    ReviewCycleRecord,
    ReviewerLoad,
    ReviewSize,
    ReviewStage,
    ReviewVelocityReport,
)


def _engine(**kw) -> CodeReviewVelocityTracker:
    return CodeReviewVelocityTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ReviewStage (5)
    def test_stage_awaiting_review(self):
        assert ReviewStage.AWAITING_REVIEW == "awaiting_review"

    def test_stage_in_review(self):
        assert ReviewStage.IN_REVIEW == "in_review"

    def test_stage_changes_requested(self):
        assert ReviewStage.CHANGES_REQUESTED == "changes_requested"

    def test_stage_approved(self):
        assert ReviewStage.APPROVED == "approved"

    def test_stage_merged(self):
        assert ReviewStage.MERGED == "merged"

    # ReviewSize (5)
    def test_size_trivial(self):
        assert ReviewSize.TRIVIAL == "trivial"

    def test_size_small(self):
        assert ReviewSize.SMALL == "small"

    def test_size_medium(self):
        assert ReviewSize.MEDIUM == "medium"

    def test_size_large(self):
        assert ReviewSize.LARGE == "large"

    def test_size_extra_large(self):
        assert ReviewSize.EXTRA_LARGE == "extra_large"

    # ReviewBottleneck (5)
    def test_bottleneck_reviewer_availability(self):
        assert ReviewBottleneck.REVIEWER_AVAILABILITY == "reviewer_availability"

    def test_bottleneck_large_diff(self):
        assert ReviewBottleneck.LARGE_DIFF == "large_diff"

    def test_bottleneck_missing_context(self):
        assert ReviewBottleneck.MISSING_CONTEXT == "missing_context"

    def test_bottleneck_ci_failure(self):
        assert ReviewBottleneck.CI_FAILURE == "ci_failure"

    def test_bottleneck_approval_policy(self):
        assert ReviewBottleneck.APPROVAL_POLICY == "approval_policy"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_review_cycle_record_defaults(self):
        r = ReviewCycleRecord()
        assert r.id
        assert r.pr_number == ""
        assert r.author == ""
        assert r.reviewer == ""
        assert r.stage == ReviewStage.AWAITING_REVIEW
        assert r.size == ReviewSize.MEDIUM
        assert r.cycle_time_hours == 0.0
        assert r.lines_changed == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_reviewer_load_defaults(self):
        r = ReviewerLoad()
        assert r.id
        assert r.reviewer == ""
        assert r.active_reviews == 0
        assert r.avg_turnaround_hours == 0.0
        assert r.bottleneck == ReviewBottleneck.REVIEWER_AVAILABILITY
        assert r.details == ""
        assert r.created_at > 0

    def test_review_velocity_report_defaults(self):
        r = ReviewVelocityReport()
        assert r.total_reviews == 0
        assert r.total_reviewer_loads == 0
        assert r.avg_cycle_time_hours == 0.0
        assert r.by_stage == {}
        assert r.by_size == {}
        assert r.slow_review_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_review_cycle
# -------------------------------------------------------------------


class TestRecordReviewCycle:
    def test_basic(self):
        eng = _engine()
        r = eng.record_review_cycle("PR-101", author="alice", cycle_time_hours=4.5)
        assert r.pr_number == "PR-101"
        assert r.author == "alice"
        assert r.cycle_time_hours == 4.5

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_review_cycle(
            "PR-202",
            author="bob",
            reviewer="carol",
            stage=ReviewStage.APPROVED,
            size=ReviewSize.LARGE,
            cycle_time_hours=72.0,
            lines_changed=500,
            details="Large refactor",
        )
        assert r.stage == ReviewStage.APPROVED
        assert r.size == ReviewSize.LARGE
        assert r.lines_changed == 500

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_review_cycle(f"PR-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_review
# -------------------------------------------------------------------


class TestGetReview:
    def test_found(self):
        eng = _engine()
        r = eng.record_review_cycle("PR-1")
        assert eng.get_review(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_review("nonexistent") is None


# -------------------------------------------------------------------
# list_reviews
# -------------------------------------------------------------------


class TestListReviews:
    def test_list_all(self):
        eng = _engine()
        eng.record_review_cycle("PR-1", author="alice")
        eng.record_review_cycle("PR-2", author="bob")
        assert len(eng.list_reviews()) == 2

    def test_filter_by_author(self):
        eng = _engine()
        eng.record_review_cycle("PR-1", author="alice")
        eng.record_review_cycle("PR-2", author="bob")
        results = eng.list_reviews(author="alice")
        assert len(results) == 1
        assert results[0].author == "alice"

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_review_cycle("PR-1", stage=ReviewStage.MERGED)
        eng.record_review_cycle("PR-2", stage=ReviewStage.IN_REVIEW)
        results = eng.list_reviews(stage=ReviewStage.MERGED)
        assert len(results) == 1
        assert results[0].pr_number == "PR-1"


# -------------------------------------------------------------------
# record_reviewer_load
# -------------------------------------------------------------------


class TestRecordReviewerLoad:
    def test_basic(self):
        eng = _engine()
        ld = eng.record_reviewer_load(
            "carol",
            active_reviews=5,
            avg_turnaround_hours=8.0,
            bottleneck=ReviewBottleneck.LARGE_DIFF,
            details="Overloaded",
        )
        assert ld.reviewer == "carol"
        assert ld.active_reviews == 5
        assert ld.avg_turnaround_hours == 8.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_reviewer_load(f"reviewer-{i}")
        assert len(eng._loads) == 2


# -------------------------------------------------------------------
# analyze_review_velocity
# -------------------------------------------------------------------


class TestAnalyzeReviewVelocity:
    def test_with_data(self):
        eng = _engine()
        eng.record_review_cycle(
            "PR-1", author="alice", cycle_time_hours=10.0, stage=ReviewStage.MERGED
        )
        eng.record_review_cycle(
            "PR-2", author="alice", cycle_time_hours=20.0, stage=ReviewStage.APPROVED
        )
        result = eng.analyze_review_velocity("alice")
        assert result["author"] == "alice"
        assert result["total_reviews"] == 2
        assert result["avg_cycle_time_hours"] == 15.0
        assert result["merged_count"] == 1
        assert result["merge_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_review_velocity("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_slow_reviews
# -------------------------------------------------------------------


class TestIdentifySlowReviews:
    def test_with_slow(self):
        eng = _engine(max_cycle_hours=48.0)
        eng.record_review_cycle("PR-1", author="alice", cycle_time_hours=72.0)
        eng.record_review_cycle("PR-2", author="bob", cycle_time_hours=24.0)
        results = eng.identify_slow_reviews()
        assert len(results) == 1
        assert results[0]["pr_number"] == "PR-1"
        assert results[0]["cycle_time_hours"] == 72.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_reviews() == []


# -------------------------------------------------------------------
# rank_reviewers_by_load
# -------------------------------------------------------------------


class TestRankReviewersByLoad:
    def test_with_data(self):
        eng = _engine()
        eng.record_reviewer_load("alice", active_reviews=2)
        eng.record_reviewer_load("bob", active_reviews=8)
        eng.record_reviewer_load("carol", active_reviews=5)
        results = eng.rank_reviewers_by_load()
        assert len(results) == 3
        assert results[0]["reviewer"] == "bob"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_reviewers_by_load() == []


# -------------------------------------------------------------------
# detect_bottlenecks
# -------------------------------------------------------------------


class TestDetectBottlenecks:
    def test_with_data(self):
        eng = _engine()
        eng.record_reviewer_load("alice", bottleneck=ReviewBottleneck.LARGE_DIFF)
        eng.record_reviewer_load("bob", bottleneck=ReviewBottleneck.LARGE_DIFF)
        eng.record_reviewer_load("carol", bottleneck=ReviewBottleneck.CI_FAILURE)
        results = eng.detect_bottlenecks()
        assert len(results) == 2
        assert results[0]["bottleneck"] == "large_diff"
        assert results[0]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.detect_bottlenecks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_cycle_hours=48.0)
        eng.record_review_cycle(
            "PR-1", stage=ReviewStage.MERGED, cycle_time_hours=10.0, size=ReviewSize.SMALL
        )
        eng.record_review_cycle(
            "PR-2", stage=ReviewStage.IN_REVIEW, cycle_time_hours=72.0, size=ReviewSize.LARGE
        )
        eng.record_reviewer_load("alice", active_reviews=3)
        report = eng.generate_report()
        assert report.total_reviews == 2
        assert report.total_reviewer_loads == 1
        assert report.by_stage != {}
        assert report.by_size != {}
        assert report.slow_review_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_reviews == 0
        assert report.avg_cycle_time_hours == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_review_cycle("PR-1")
        eng.record_reviewer_load("alice")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._loads) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_reviews"] == 0
        assert stats["total_reviewer_loads"] == 0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_review_cycle("PR-1", author="alice", stage=ReviewStage.MERGED)
        eng.record_review_cycle("PR-2", author="bob", stage=ReviewStage.IN_REVIEW)
        eng.record_reviewer_load("alice")
        stats = eng.get_stats()
        assert stats["total_reviews"] == 2
        assert stats["total_reviewer_loads"] == 1
        assert stats["unique_authors"] == 2
        assert stats["max_cycle_hours"] == 48.0
