"""Tests for shieldops.config.flag_lifecycle — FeatureFlagLifecycleManager."""

from __future__ import annotations

from shieldops.config.flag_lifecycle import (
    CleanupReason,
    FeatureFlagLifecycleManager,
    FlagCleanupCandidate,
    FlagLifecycleRecord,
    FlagLifecycleReport,
    FlagLifecycleStage,
    FlagRisk,
)


def _engine(**kw) -> FeatureFlagLifecycleManager:
    return FeatureFlagLifecycleManager(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FlagLifecycleStage (5)
    def test_stage_created(self):
        assert FlagLifecycleStage.CREATED == "created"

    def test_stage_active(self):
        assert FlagLifecycleStage.ACTIVE == "active"

    def test_stage_stale(self):
        assert FlagLifecycleStage.STALE == "stale"

    def test_stage_deprecated(self):
        assert FlagLifecycleStage.DEPRECATED == "deprecated"

    def test_stage_ready_for_removal(self):
        assert FlagLifecycleStage.READY_FOR_REMOVAL == "ready_for_removal"

    # FlagRisk (5)
    def test_risk_critical(self):
        assert FlagRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert FlagRisk.HIGH == "high"

    def test_risk_medium(self):
        assert FlagRisk.MEDIUM == "medium"

    def test_risk_low(self):
        assert FlagRisk.LOW == "low"

    def test_risk_none(self):
        assert FlagRisk.NONE == "none"

    # CleanupReason (5)
    def test_reason_fully_rolled_out(self):
        assert CleanupReason.FULLY_ROLLED_OUT == "fully_rolled_out"

    def test_reason_experiment_complete(self):
        assert CleanupReason.EXPERIMENT_COMPLETE == "experiment_complete"

    def test_reason_never_enabled(self):
        assert CleanupReason.NEVER_ENABLED == "never_enabled"

    def test_reason_abandoned(self):
        assert CleanupReason.ABANDONED == "abandoned"

    def test_reason_superseded(self):
        assert CleanupReason.SUPERSEDED == "superseded"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_flag_lifecycle_record_defaults(self):
        r = FlagLifecycleRecord()
        assert r.id
        assert r.flag_name == ""
        assert r.owner == ""
        assert r.stage == FlagLifecycleStage.CREATED
        assert r.risk == FlagRisk.LOW
        assert r.age_days == 0
        assert r.references_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_flag_cleanup_candidate_defaults(self):
        r = FlagCleanupCandidate()
        assert r.id
        assert r.flag_name == ""
        assert r.reason == CleanupReason.FULLY_ROLLED_OUT
        assert r.risk == FlagRisk.LOW
        assert r.tech_debt_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_flag_lifecycle_report_defaults(self):
        r = FlagLifecycleReport()
        assert r.total_flags == 0
        assert r.total_cleanup_candidates == 0
        assert r.avg_age_days == 0.0
        assert r.by_stage == {}
        assert r.by_risk == {}
        assert r.stale_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_flag
# -------------------------------------------------------------------


class TestRecordFlag:
    def test_basic(self):
        eng = _engine()
        r = eng.record_flag("enable_dark_mode", owner="team-ui", age_days=5)
        assert r.flag_name == "enable_dark_mode"
        assert r.owner == "team-ui"
        assert r.age_days == 5
        assert r.stage == FlagLifecycleStage.CREATED  # <7 days

    def test_auto_stage_from_age(self):
        eng = _engine(stale_days_threshold=90)
        r = eng.record_flag("old_flag", age_days=100)
        assert r.stage == FlagLifecycleStage.STALE

    def test_explicit_stage_overrides(self):
        eng = _engine()
        r = eng.record_flag("f1", stage=FlagLifecycleStage.DEPRECATED, age_days=5)
        assert r.stage == FlagLifecycleStage.DEPRECATED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_flag(f"flag-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_flag
# -------------------------------------------------------------------


class TestGetFlag:
    def test_found(self):
        eng = _engine()
        r = eng.record_flag("my_flag")
        assert eng.get_flag(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_flag("nonexistent") is None


# -------------------------------------------------------------------
# list_flags
# -------------------------------------------------------------------


class TestListFlags:
    def test_list_all(self):
        eng = _engine()
        eng.record_flag("flag-a")
        eng.record_flag("flag-b")
        assert len(eng.list_flags()) == 2

    def test_filter_by_flag_name(self):
        eng = _engine()
        eng.record_flag("flag-a")
        eng.record_flag("flag-b")
        results = eng.list_flags(flag_name="flag-a")
        assert len(results) == 1
        assert results[0].flag_name == "flag-a"

    def test_filter_by_stage(self):
        eng = _engine(stale_days_threshold=90)
        eng.record_flag("young", age_days=3)
        eng.record_flag("old", age_days=100)
        results = eng.list_flags(stage=FlagLifecycleStage.STALE)
        assert len(results) == 1
        assert results[0].flag_name == "old"


# -------------------------------------------------------------------
# record_cleanup_candidate
# -------------------------------------------------------------------


class TestRecordCleanupCandidate:
    def test_basic(self):
        eng = _engine()
        c = eng.record_cleanup_candidate(
            "old_flag",
            reason=CleanupReason.ABANDONED,
            tech_debt_score=8.5,
        )
        assert c.flag_name == "old_flag"
        assert c.reason == CleanupReason.ABANDONED
        assert c.tech_debt_score == 8.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_cleanup_candidate(f"flag-{i}")
        assert len(eng._candidates) == 2


# -------------------------------------------------------------------
# identify_stale_flags
# -------------------------------------------------------------------


class TestIdentifyStaleFlags:
    def test_with_stale(self):
        eng = _engine(stale_days_threshold=90)
        eng.record_flag("fresh", age_days=10)
        eng.record_flag("stale-1", age_days=100, owner="team-a")
        eng.record_flag("stale-2", age_days=200, owner="team-b")
        results = eng.identify_stale_flags()
        assert len(results) == 2
        # Sorted by age desc, 200 first
        assert results[0]["flag_name"] == "stale-2"
        assert results[0]["age_days"] == 200

    def test_empty(self):
        eng = _engine()
        assert eng.identify_stale_flags() == []

    def test_none_stale(self):
        eng = _engine(stale_days_threshold=90)
        eng.record_flag("f1", age_days=10)
        eng.record_flag("f2", age_days=50)
        assert eng.identify_stale_flags() == []


# -------------------------------------------------------------------
# identify_cleanup_candidates
# -------------------------------------------------------------------


class TestIdentifyCleanupCandidates:
    def test_with_candidates(self):
        eng = _engine()
        eng.record_cleanup_candidate("f1", tech_debt_score=3.0)
        eng.record_cleanup_candidate("f2", tech_debt_score=9.0)
        results = eng.identify_cleanup_candidates()
        assert len(results) == 2
        # Sorted by tech_debt_score desc
        assert results[0]["flag_name"] == "f2"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_cleanup_candidates() == []


# -------------------------------------------------------------------
# calculate_tech_debt_score
# -------------------------------------------------------------------


class TestCalculateTechDebtScore:
    def test_with_data(self):
        eng = _engine(stale_days_threshold=90)
        eng.record_flag("f1", age_days=100, references_count=5)
        eng.record_flag("f2", age_days=10, references_count=3)
        result = eng.calculate_tech_debt_score()
        assert result["total_flags"] == 2
        assert result["stale_flags"] == 1
        # debt = (100*5) / 2 = 250.0
        assert result["tech_debt_score"] == 250.0
        assert result["stale_pct"] == 50.0

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_tech_debt_score()
        assert result["total_flags"] == 0
        assert result["tech_debt_score"] == 0.0


# -------------------------------------------------------------------
# analyze_owner_responsibility
# -------------------------------------------------------------------


class TestAnalyzeOwnerResponsibility:
    def test_with_data(self):
        eng = _engine(stale_days_threshold=90)
        eng.record_flag("f1", owner="alice", age_days=100)
        eng.record_flag("f2", owner="alice", age_days=10)
        eng.record_flag("f3", owner="bob", age_days=200)
        eng.record_flag("f4", owner="bob", age_days=150)
        results = eng.analyze_owner_responsibility()
        assert len(results) == 2
        # bob has 2 stale, alice has 1 stale -> sorted desc
        assert results[0]["owner"] == "bob"
        assert results[0]["stale_flags"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_owner_responsibility() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(stale_days_threshold=90)
        eng.record_flag("f1", age_days=100, risk=FlagRisk.HIGH)
        eng.record_flag("f2", age_days=10, risk=FlagRisk.LOW)
        eng.record_cleanup_candidate("f1")
        report = eng.generate_report()
        assert report.total_flags == 2
        assert report.total_cleanup_candidates == 1
        assert report.stale_count == 1
        assert report.by_stage != {}
        assert report.by_risk != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_flags == 0
        assert report.avg_age_days == 0.0
        assert "well-managed" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_flag("f1")
        eng.record_cleanup_candidate("f1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._candidates) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_flags"] == 0
        assert stats["total_cleanup_candidates"] == 0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        eng = _engine(stale_days_threshold=90)
        eng.record_flag("f1", age_days=100)
        eng.record_flag("f2", age_days=5)
        eng.record_cleanup_candidate("f1")
        stats = eng.get_stats()
        assert stats["total_flags"] == 2
        assert stats["total_cleanup_candidates"] == 1
        assert stats["unique_flags"] == 2
        assert stats["stale_days_threshold"] == 90
