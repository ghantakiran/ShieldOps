"""Tests for shieldops.changes.freeze_validator — ChangeFreezeValidator."""

from __future__ import annotations

from shieldops.changes.freeze_validator import (
    ChangeFreezeValidator,
    FreezeRecord,
    FreezeStatus,
    FreezeType,
    FreezeValidatorReport,
    FreezeViolation,
    FreezeViolationRecord,
)


def _engine(**kw) -> ChangeFreezeValidator:
    return ChangeFreezeValidator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FreezeType (5)
    def test_type_full(self):
        assert FreezeType.FULL_FREEZE == "full_freeze"

    def test_type_partial(self):
        assert FreezeType.PARTIAL_FREEZE == "partial_freeze"

    def test_type_soft(self):
        assert FreezeType.SOFT_FREEZE == "soft_freeze"

    def test_type_emergency(self):
        assert FreezeType.EMERGENCY_ONLY == "emergency_only"

    def test_type_maintenance(self):
        assert FreezeType.MAINTENANCE_WINDOW == "maintenance_window"

    # FreezeViolation (5)
    def test_violation_unauthorized(self):
        assert FreezeViolation.UNAUTHORIZED_DEPLOY == "unauthorized_deploy"

    def test_violation_skipped(self):
        assert FreezeViolation.SKIPPED_APPROVAL == "skipped_approval"

    def test_violation_bypass(self):
        assert FreezeViolation.BYPASS_POLICY == "bypass_policy"

    def test_violation_emergency(self):
        assert FreezeViolation.EMERGENCY_OVERRIDE == "emergency_override"

    def test_violation_scheduled(self):
        assert FreezeViolation.SCHEDULED_CONFLICT == "scheduled_conflict"

    # FreezeStatus (5)
    def test_status_active(self):
        assert FreezeStatus.ACTIVE == "active"

    def test_status_upcoming(self):
        assert FreezeStatus.UPCOMING == "upcoming"

    def test_status_expired(self):
        assert FreezeStatus.EXPIRED == "expired"

    def test_status_cancelled(self):
        assert FreezeStatus.CANCELLED == "cancelled"

    def test_status_extended(self):
        assert FreezeStatus.EXTENDED == "extended"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_freeze_record_defaults(self):
        r = FreezeRecord()
        assert r.id
        assert r.freeze_name == ""
        assert r.freeze_type == FreezeType.FULL_FREEZE
        assert r.status == FreezeStatus.ACTIVE
        assert r.team == ""
        assert r.environment == ""
        assert r.start_time == 0.0
        assert r.end_time == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_violation_record_defaults(self):
        v = FreezeViolationRecord()
        assert v.id
        assert v.freeze_id == ""
        assert v.violation_type == FreezeViolation.UNAUTHORIZED_DEPLOY
        assert v.deployer == ""
        assert v.service == ""
        assert v.severity_score == 0.0
        assert v.created_at > 0

    def test_report_defaults(self):
        r = FreezeValidatorReport()
        assert r.total_records == 0
        assert r.total_violations == 0
        assert r.violation_rate_pct == 0.0
        assert r.by_freeze_type == {}
        assert r.by_violation_type == {}
        assert r.by_status == {}
        assert r.top_violators == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_freeze
# -------------------------------------------------------------------


class TestRecordFreeze:
    def test_basic(self):
        eng = _engine()
        r = eng.record_freeze(
            "year-end-freeze",
            freeze_type=FreezeType.FULL_FREEZE,
            status=FreezeStatus.ACTIVE,
        )
        assert r.freeze_name == "year-end-freeze"
        assert r.freeze_type == FreezeType.FULL_FREEZE

    def test_with_team(self):
        eng = _engine()
        r = eng.record_freeze("sprint-freeze", team="platform")
        assert r.team == "platform"

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
        r = eng.record_freeze("freeze-a")
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

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_freeze("a", freeze_type=FreezeType.FULL_FREEZE)
        eng.record_freeze("b", freeze_type=FreezeType.SOFT_FREEZE)
        results = eng.list_freezes(freeze_type=FreezeType.FULL_FREEZE)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_freeze("a", status=FreezeStatus.ACTIVE)
        eng.record_freeze("b", status=FreezeStatus.EXPIRED)
        results = eng.list_freezes(status=FreezeStatus.ACTIVE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_violation
# -------------------------------------------------------------------


class TestAddViolation:
    def test_basic(self):
        eng = _engine()
        v = eng.add_violation(
            "freeze-1",
            violation_type=(FreezeViolation.UNAUTHORIZED_DEPLOY),
            deployer="dev-a",
            severity_score=7.5,
        )
        assert v.freeze_id == "freeze-1"
        assert v.deployer == "dev-a"
        assert v.severity_score == 7.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_violation(f"freeze-{i}", deployer=f"dev-{i}")
        assert len(eng._violations) == 2


# -------------------------------------------------------------------
# analyze_freeze_compliance
# -------------------------------------------------------------------


class TestAnalyzeFreezeCompliance:
    def test_with_data(self):
        eng = _engine(max_violation_rate_pct=60.0)
        eng.record_freeze("freeze-a")
        eng.record_freeze("freeze-b")
        eng.add_violation("freeze-a", deployer="dev-a")
        result = eng.analyze_freeze_compliance()
        assert result["total_freezes"] == 2
        assert result["total_violations"] == 1
        assert result["within_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_freeze_compliance()
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_frequent_violators
# -------------------------------------------------------------------


class TestIdentifyFrequentViolators:
    def test_with_frequent(self):
        eng = _engine()
        eng.add_violation("f-1", deployer="repeat-offender")
        eng.add_violation("f-2", deployer="repeat-offender")
        eng.add_violation("f-3", deployer="one-timer")
        results = eng.identify_frequent_violators()
        assert len(results) == 1
        assert results[0]["deployer"] == "repeat-offender"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_frequent_violators() == []


# -------------------------------------------------------------------
# rank_by_severity_score
# -------------------------------------------------------------------


class TestRankBySeverityScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_violation(
            "f-1",
            deployer="dev-a",
            severity_score=3.0,
        )
        eng.add_violation(
            "f-2",
            deployer="dev-b",
            severity_score=9.0,
        )
        results = eng.rank_by_severity_score()
        assert results[0]["avg_severity_score"] == 9.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity_score() == []


# -------------------------------------------------------------------
# detect_violation_trends
# -------------------------------------------------------------------


class TestDetectViolationTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(4):
            eng.add_violation("f-1", deployer="serial-deployer")
        eng.add_violation("f-2", deployer="one-off")
        results = eng.detect_violation_trends()
        assert len(results) == 1
        assert results[0]["deployer"] == "serial-deployer"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_violation_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_violation_rate_pct=5.0)
        eng.record_freeze("freeze-a")
        eng.add_violation(
            "freeze-a",
            deployer="dev-a",
            severity_score=9.0,
        )
        report = eng.generate_report()
        assert isinstance(report, FreezeValidatorReport)
        assert report.total_records == 1
        assert report.total_violations == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "acceptable limits" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_freeze("freeze-a")
        eng.add_violation("freeze-a", deployer="dev-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._violations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_freezes"] == 0
        assert stats["total_violations"] == 0
        assert stats["freeze_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_freeze("a", freeze_type=FreezeType.FULL_FREEZE)
        eng.record_freeze("b", freeze_type=FreezeType.SOFT_FREEZE)
        eng.add_violation("a", deployer="dev-a")
        stats = eng.get_stats()
        assert stats["total_freezes"] == 2
        assert stats["total_violations"] == 1
        assert stats["unique_teams"] == 1
