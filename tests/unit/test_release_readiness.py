"""Tests for shieldops.changes.release_readiness — ReleaseReadinessChecker."""

from __future__ import annotations

from shieldops.changes.release_readiness import (
    CheckPriority,
    ReadinessCategory,
    ReadinessCheck,
    ReadinessRecord,
    ReadinessStatus,
    ReleaseReadinessChecker,
    ReleaseReadinessReport,
)


def _engine(**kw) -> ReleaseReadinessChecker:
    return ReleaseReadinessChecker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ReadinessCategory (5)
    def test_category_test_coverage(self):
        assert ReadinessCategory.TEST_COVERAGE == "test_coverage"

    def test_category_security_scan(self):
        assert ReadinessCategory.SECURITY_SCAN == "security_scan"

    def test_category_performance(self):
        assert ReadinessCategory.PERFORMANCE == "performance"

    def test_category_documentation(self):
        assert ReadinessCategory.DOCUMENTATION == "documentation"

    def test_category_rollback_plan(self):
        assert ReadinessCategory.ROLLBACK_PLAN == "rollback_plan"

    # ReadinessStatus (5)
    def test_status_ready(self):
        assert ReadinessStatus.READY == "ready"

    def test_status_conditional(self):
        assert ReadinessStatus.CONDITIONAL == "conditional"

    def test_status_not_ready(self):
        assert ReadinessStatus.NOT_READY == "not_ready"

    def test_status_blocked(self):
        assert ReadinessStatus.BLOCKED == "blocked"

    def test_status_waived(self):
        assert ReadinessStatus.WAIVED == "waived"

    # CheckPriority (5)
    def test_priority_critical(self):
        assert CheckPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert CheckPriority.HIGH == "high"

    def test_priority_medium(self):
        assert CheckPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert CheckPriority.LOW == "low"

    def test_priority_optional(self):
        assert CheckPriority.OPTIONAL == "optional"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_readiness_record_defaults(self):
        r = ReadinessRecord()
        assert r.id
        assert r.release_name == ""
        assert r.category == ReadinessCategory.TEST_COVERAGE
        assert r.status == ReadinessStatus.READY
        assert r.priority == CheckPriority.CRITICAL
        assert r.score_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_readiness_check_defaults(self):
        r = ReadinessCheck()
        assert r.id
        assert r.check_name == ""
        assert r.category == ReadinessCategory.TEST_COVERAGE
        assert r.status == ReadinessStatus.READY
        assert r.min_required_score_pct == 0.0
        assert r.is_blocking is True
        assert r.created_at > 0

    def test_release_readiness_report_defaults(self):
        r = ReleaseReadinessReport()
        assert r.total_readiness_checks == 0
        assert r.total_checks == 0
        assert r.ready_rate_pct == 0.0
        assert r.by_category == {}
        assert r.by_status == {}
        assert r.blocker_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_readiness
# -------------------------------------------------------------------


class TestRecordReadiness:
    def test_basic(self):
        eng = _engine()
        r = eng.record_readiness("v2.0", category=ReadinessCategory.TEST_COVERAGE)
        assert r.release_name == "v2.0"
        assert r.category == ReadinessCategory.TEST_COVERAGE

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_readiness(
            "v3.0",
            category=ReadinessCategory.SECURITY_SCAN,
            status=ReadinessStatus.BLOCKED,
            priority=CheckPriority.HIGH,
            score_pct=45.0,
            details="Security scan incomplete",
        )
        assert r.status == ReadinessStatus.BLOCKED
        assert r.priority == CheckPriority.HIGH
        assert r.score_pct == 45.0
        assert r.details == "Security scan incomplete"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_readiness(f"rel-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_readiness
# -------------------------------------------------------------------


class TestGetReadiness:
    def test_found(self):
        eng = _engine()
        r = eng.record_readiness("v2.0")
        assert eng.get_readiness(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_readiness("nonexistent") is None


# -------------------------------------------------------------------
# list_readiness_checks
# -------------------------------------------------------------------


class TestListReadinessChecks:
    def test_list_all(self):
        eng = _engine()
        eng.record_readiness("rel-a")
        eng.record_readiness("rel-b")
        assert len(eng.list_readiness_checks()) == 2

    def test_filter_by_release_name(self):
        eng = _engine()
        eng.record_readiness("rel-a")
        eng.record_readiness("rel-b")
        results = eng.list_readiness_checks(release_name="rel-a")
        assert len(results) == 1
        assert results[0].release_name == "rel-a"

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_readiness("rel-a", category=ReadinessCategory.TEST_COVERAGE)
        eng.record_readiness("rel-b", category=ReadinessCategory.SECURITY_SCAN)
        results = eng.list_readiness_checks(category=ReadinessCategory.SECURITY_SCAN)
        assert len(results) == 1
        assert results[0].release_name == "rel-b"


# -------------------------------------------------------------------
# add_check
# -------------------------------------------------------------------


class TestAddCheck:
    def test_basic(self):
        eng = _engine()
        c = eng.add_check(
            "coverage-gate",
            category=ReadinessCategory.TEST_COVERAGE,
            status=ReadinessStatus.READY,
            min_required_score_pct=80.0,
            is_blocking=True,
        )
        assert c.check_name == "coverage-gate"
        assert c.category == ReadinessCategory.TEST_COVERAGE
        assert c.min_required_score_pct == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_check(f"check-{i}")
        assert len(eng._checks) == 2


# -------------------------------------------------------------------
# analyze_release_readiness
# -------------------------------------------------------------------


class TestAnalyzeReleaseReadiness:
    def test_with_data(self):
        eng = _engine(min_score_pct=80.0)
        eng.record_readiness("rel-a", score_pct=90.0)
        eng.record_readiness("rel-a", score_pct=70.0)
        eng.record_readiness("rel-a", score_pct=80.0)
        result = eng.analyze_release_readiness("rel-a")
        assert result["avg_score"] == 80.0
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_release_readiness("unknown-rel")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_score_pct=80.0)
        eng.record_readiness("rel-a", score_pct=90.0)
        eng.record_readiness("rel-a", score_pct=85.0)
        result = eng.analyze_release_readiness("rel-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_blockers
# -------------------------------------------------------------------


class TestIdentifyBlockers:
    def test_with_blockers(self):
        eng = _engine()
        eng.record_readiness("rel-a", status=ReadinessStatus.BLOCKED)
        eng.record_readiness("rel-a", status=ReadinessStatus.NOT_READY)
        eng.record_readiness("rel-b", status=ReadinessStatus.READY)
        results = eng.identify_blockers()
        assert len(results) == 1
        assert results[0]["release_name"] == "rel-a"
        assert results[0]["blocker_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_blockers() == []

    def test_single_blocker_not_returned(self):
        eng = _engine()
        eng.record_readiness("rel-a", status=ReadinessStatus.BLOCKED)
        assert eng.identify_blockers() == []


# -------------------------------------------------------------------
# rank_by_readiness_score
# -------------------------------------------------------------------


class TestRankByReadinessScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_readiness("rel-a", score_pct=30.0)
        eng.record_readiness("rel-b", score_pct=95.0)
        results = eng.rank_by_readiness_score()
        assert results[0]["release_name"] == "rel-b"
        assert results[0]["avg_score_pct"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_readiness_score() == []


# -------------------------------------------------------------------
# detect_readiness_trends
# -------------------------------------------------------------------


class TestDetectReadinessTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_readiness("rel-a")
        eng.record_readiness("rel-b")
        results = eng.detect_readiness_trends()
        assert len(results) == 1
        assert results[0]["release_name"] == "rel-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_readiness_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_readiness("rel-a")
        assert eng.detect_readiness_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_readiness("rel-a", status=ReadinessStatus.BLOCKED)
        eng.record_readiness("rel-b", status=ReadinessStatus.READY)
        eng.add_check("check-1")
        report = eng.generate_report()
        assert report.total_readiness_checks == 2
        assert report.total_checks == 1
        assert report.by_category != {}
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_readiness_checks == 0
        assert report.ready_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_readiness("rel-a")
        eng.add_check("check-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._checks) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_readiness_checks"] == 0
        assert stats["total_checks"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_score_pct=80.0)
        eng.record_readiness("rel-a", category=ReadinessCategory.TEST_COVERAGE)
        eng.record_readiness("rel-b", category=ReadinessCategory.SECURITY_SCAN)
        eng.add_check("check-1")
        stats = eng.get_stats()
        assert stats["total_readiness_checks"] == 2
        assert stats["total_checks"] == 1
        assert stats["unique_releases"] == 2
        assert stats["min_score_pct"] == 80.0
