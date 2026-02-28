"""Tests for shieldops.changes.change_freeze — ChangeFreezeManager."""

from __future__ import annotations

from shieldops.changes.change_freeze import (
    ChangeFreezeManager,
    ChangeFreezeReport,
    ExceptionStatus,
    FreezeException,
    FreezeRecord,
    FreezeScope,
    FreezeType,
)


def _engine(**kw) -> ChangeFreezeManager:
    return ChangeFreezeManager(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FreezeType (5)
    def test_type_full(self):
        assert FreezeType.FULL == "full"

    def test_type_partial(self):
        assert FreezeType.PARTIAL == "partial"

    def test_type_emergency_only(self):
        assert FreezeType.EMERGENCY_ONLY == "emergency_only"

    def test_type_scheduled(self):
        assert FreezeType.SCHEDULED == "scheduled"

    def test_type_custom(self):
        assert FreezeType.CUSTOM == "custom"

    # FreezeScope (5)
    def test_scope_global(self):
        assert FreezeScope.GLOBAL == "global"

    def test_scope_team(self):
        assert FreezeScope.TEAM == "team"

    def test_scope_service(self):
        assert FreezeScope.SERVICE == "service"

    def test_scope_environment(self):
        assert FreezeScope.ENVIRONMENT == "environment"

    def test_scope_region(self):
        assert FreezeScope.REGION == "region"

    # ExceptionStatus (5)
    def test_status_approved(self):
        assert ExceptionStatus.APPROVED == "approved"

    def test_status_pending(self):
        assert ExceptionStatus.PENDING == "pending"

    def test_status_denied(self):
        assert ExceptionStatus.DENIED == "denied"

    def test_status_expired(self):
        assert ExceptionStatus.EXPIRED == "expired"

    def test_status_revoked(self):
        assert ExceptionStatus.REVOKED == "revoked"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_freeze_record_defaults(self):
        r = FreezeRecord()
        assert r.id
        assert r.freeze_name == ""
        assert r.freeze_type == FreezeType.FULL
        assert r.scope == FreezeScope.GLOBAL
        assert r.exception_status == ExceptionStatus.PENDING
        assert r.duration_hours == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_freeze_exception_defaults(self):
        r = FreezeException()
        assert r.id
        assert r.exception_name == ""
        assert r.freeze_type == FreezeType.FULL
        assert r.scope == FreezeScope.GLOBAL
        assert r.reason == ""
        assert r.approved_by == ""
        assert r.created_at > 0

    def test_change_freeze_report_defaults(self):
        r = ChangeFreezeReport()
        assert r.total_freezes == 0
        assert r.total_exceptions == 0
        assert r.compliance_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.exception_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_freeze
# -------------------------------------------------------------------


class TestRecordFreeze:
    def test_basic(self):
        eng = _engine()
        r = eng.record_freeze("year-end-freeze", freeze_type=FreezeType.FULL)
        assert r.freeze_name == "year-end-freeze"
        assert r.freeze_type == FreezeType.FULL

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_freeze(
            "holiday-freeze",
            freeze_type=FreezeType.PARTIAL,
            scope=FreezeScope.TEAM,
            exception_status=ExceptionStatus.APPROVED,
            duration_hours=48.0,
            details="Holiday partial freeze for team alpha",
        )
        assert r.scope == FreezeScope.TEAM
        assert r.exception_status == ExceptionStatus.APPROVED
        assert r.duration_hours == 48.0
        assert r.details == "Holiday partial freeze for team alpha"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_freeze(f"freeze-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_freeze
# -------------------------------------------------------------------


class TestGetFreeze:
    def test_found(self):
        eng = _engine()
        r = eng.record_freeze("year-end-freeze")
        assert eng.get_freeze(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_freeze("nonexistent") is None


# -------------------------------------------------------------------
# list_freezes
# -------------------------------------------------------------------


class TestListFreezes:
    def test_list_all(self):
        eng = _engine()
        eng.record_freeze("freeze-a")
        eng.record_freeze("freeze-b")
        assert len(eng.list_freezes()) == 2

    def test_filter_by_freeze_name(self):
        eng = _engine()
        eng.record_freeze("freeze-a")
        eng.record_freeze("freeze-b")
        results = eng.list_freezes(freeze_name="freeze-a")
        assert len(results) == 1
        assert results[0].freeze_name == "freeze-a"

    def test_filter_by_freeze_type(self):
        eng = _engine()
        eng.record_freeze("freeze-a", freeze_type=FreezeType.FULL)
        eng.record_freeze("freeze-b", freeze_type=FreezeType.PARTIAL)
        results = eng.list_freezes(freeze_type=FreezeType.PARTIAL)
        assert len(results) == 1
        assert results[0].freeze_name == "freeze-b"


# -------------------------------------------------------------------
# add_exception
# -------------------------------------------------------------------


class TestAddException:
    def test_basic(self):
        eng = _engine()
        e = eng.add_exception(
            "hotfix-exception",
            freeze_type=FreezeType.FULL,
            scope=FreezeScope.SERVICE,
            reason="Critical hotfix required",
            approved_by="sre-lead",
        )
        assert e.exception_name == "hotfix-exception"
        assert e.freeze_type == FreezeType.FULL
        assert e.reason == "Critical hotfix required"
        assert e.approved_by == "sre-lead"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_exception(f"exception-{i}")
        assert len(eng._exceptions) == 2


# -------------------------------------------------------------------
# analyze_freeze_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeFreezeEffectiveness:
    def test_with_data(self):
        eng = _engine(max_exception_rate_pct=10.0)
        eng.record_freeze(
            "year-end",
            exception_status=ExceptionStatus.APPROVED,
            duration_hours=24.0,
        )
        eng.record_freeze(
            "year-end",
            exception_status=ExceptionStatus.DENIED,
            duration_hours=48.0,
        )
        eng.record_freeze(
            "year-end",
            exception_status=ExceptionStatus.PENDING,
            duration_hours=36.0,
        )
        result = eng.analyze_freeze_effectiveness("year-end")
        assert result["avg_duration"] == 36.0
        assert result["record_count"] == 3
        assert result["exception_rate"] == 33.33

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_freeze_effectiveness("unknown-freeze")
        assert result["status"] == "no_data"

    def test_exception_rate_computed(self):
        eng = _engine()
        eng.record_freeze("q4-freeze", exception_status=ExceptionStatus.APPROVED)
        eng.record_freeze("q4-freeze", exception_status=ExceptionStatus.APPROVED)
        result = eng.analyze_freeze_effectiveness("q4-freeze")
        assert result["exception_rate"] == 100.0


# -------------------------------------------------------------------
# identify_frequent_exceptions
# -------------------------------------------------------------------


class TestIdentifyFrequentExceptions:
    def test_with_frequent(self):
        eng = _engine()
        eng.record_freeze("year-end", exception_status=ExceptionStatus.APPROVED)
        eng.record_freeze("year-end", exception_status=ExceptionStatus.APPROVED)
        eng.record_freeze("q4-freeze", exception_status=ExceptionStatus.DENIED)
        results = eng.identify_frequent_exceptions()
        assert len(results) == 1
        assert results[0]["freeze_name"] == "year-end"
        assert results[0]["approved_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_frequent_exceptions() == []

    def test_single_approved_not_returned(self):
        eng = _engine()
        eng.record_freeze("year-end", exception_status=ExceptionStatus.APPROVED)
        assert eng.identify_frequent_exceptions() == []


# -------------------------------------------------------------------
# rank_by_freeze_duration
# -------------------------------------------------------------------


class TestRankByFreezeDuration:
    def test_with_data(self):
        eng = _engine()
        eng.record_freeze("freeze-a", duration_hours=10.0)
        eng.record_freeze("freeze-b", duration_hours=72.0)
        results = eng.rank_by_freeze_duration()
        assert results[0]["freeze_name"] == "freeze-b"
        assert results[0]["avg_duration_hours"] == 72.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_freeze_duration() == []


# -------------------------------------------------------------------
# detect_freeze_patterns
# -------------------------------------------------------------------


class TestDetectFreezePatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_freeze("year-end")
        eng.record_freeze("q4-freeze")
        results = eng.detect_freeze_patterns()
        assert len(results) == 1
        assert results[0]["freeze_name"] == "year-end"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_freeze_patterns() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_freeze("year-end")
        assert eng.detect_freeze_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_freeze("year-end", exception_status=ExceptionStatus.APPROVED)
        eng.record_freeze("q4-freeze", exception_status=ExceptionStatus.DENIED)
        eng.add_exception("exception-1")
        report = eng.generate_report()
        assert report.total_freezes == 2
        assert report.total_exceptions == 1
        assert report.exception_count == 1
        assert report.by_type != {}
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_freezes == 0
        assert report.compliance_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_freeze("year-end")
        eng.add_exception("exception-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._exceptions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_freezes"] == 0
        assert stats["total_exceptions"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_exception_rate_pct=15.0)
        eng.record_freeze("year-end", freeze_type=FreezeType.FULL)
        eng.record_freeze("q4-freeze", freeze_type=FreezeType.PARTIAL)
        eng.add_exception("exception-1")
        stats = eng.get_stats()
        assert stats["total_freezes"] == 2
        assert stats["total_exceptions"] == 1
        assert stats["unique_freeze_names"] == 2
        assert stats["max_exception_rate_pct"] == 15.0
