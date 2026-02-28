"""Tests for shieldops.topology.deprecation_tracker — ServiceDeprecationTracker."""

from __future__ import annotations

from shieldops.topology.deprecation_tracker import (
    DeprecationImpact,
    DeprecationRecord,
    DeprecationStage,
    DeprecationTrackerReport,
    MigrationPlan,
    MigrationStatus,
    ServiceDeprecationTracker,
)


def _engine(**kw) -> ServiceDeprecationTracker:
    return ServiceDeprecationTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DeprecationStage (5)
    def test_stage_announced(self):
        assert DeprecationStage.ANNOUNCED == "announced"

    def test_stage_migration_period(self):
        assert DeprecationStage.MIGRATION_PERIOD == "migration_period"

    def test_stage_sunset_warning(self):
        assert DeprecationStage.SUNSET_WARNING == "sunset_warning"

    def test_stage_end_of_life(self):
        assert DeprecationStage.END_OF_LIFE == "end_of_life"

    def test_stage_decommissioned(self):
        assert DeprecationStage.DECOMMISSIONED == "decommissioned"

    # DeprecationImpact (5)
    def test_impact_critical(self):
        assert DeprecationImpact.CRITICAL == "critical"

    def test_impact_high(self):
        assert DeprecationImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert DeprecationImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert DeprecationImpact.LOW == "low"

    def test_impact_minimal(self):
        assert DeprecationImpact.MINIMAL == "minimal"

    # MigrationStatus (5)
    def test_migration_not_started(self):
        assert MigrationStatus.NOT_STARTED == "not_started"

    def test_migration_planning(self):
        assert MigrationStatus.PLANNING == "planning"

    def test_migration_in_progress(self):
        assert MigrationStatus.IN_PROGRESS == "in_progress"

    def test_migration_nearly_complete(self):
        assert MigrationStatus.NEARLY_COMPLETE == "nearly_complete"

    def test_migration_completed(self):
        assert MigrationStatus.COMPLETED == "completed"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_deprecation_record_defaults(self):
        r = DeprecationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.stage == DeprecationStage.ANNOUNCED
        assert r.impact == DeprecationImpact.MODERATE
        assert r.migration_status == MigrationStatus.NOT_STARTED
        assert r.eol_date == 0.0
        assert r.dependent_services == []
        assert r.details == ""
        assert r.created_at > 0

    def test_migration_plan_defaults(self):
        r = MigrationPlan()
        assert r.id
        assert r.service_name == ""
        assert r.target_service == ""
        assert r.migration_status == MigrationStatus.NOT_STARTED
        assert r.planned_completion_date == 0.0
        assert r.owner_team == ""
        assert r.notes == ""
        assert r.created_at > 0

    def test_deprecation_tracker_report_defaults(self):
        r = DeprecationTrackerReport()
        assert r.total_deprecations == 0
        assert r.total_migration_plans == 0
        assert r.overdue_count == 0
        assert r.by_stage == {}
        assert r.by_impact == {}
        assert r.by_migration_status == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_deprecation
# -------------------------------------------------------------------


class TestRecordDeprecation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_deprecation(
            "svc-v1",
            stage=DeprecationStage.ANNOUNCED,
            impact=DeprecationImpact.HIGH,
        )
        assert r.service_name == "svc-v1"
        assert r.stage == DeprecationStage.ANNOUNCED
        assert r.impact == DeprecationImpact.HIGH

    def test_with_dependents(self):
        eng = _engine()
        r = eng.record_deprecation(
            "svc-old",
            dependent_services=["svc-a", "svc-b"],
        )
        assert r.dependent_services == ["svc-a", "svc-b"]

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_deprecation(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_deprecation
# -------------------------------------------------------------------


class TestGetDeprecation:
    def test_found(self):
        eng = _engine()
        r = eng.record_deprecation("svc-a")
        assert eng.get_deprecation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_deprecation("nonexistent") is None


# -------------------------------------------------------------------
# list_deprecations
# -------------------------------------------------------------------


class TestListDeprecations:
    def test_list_all(self):
        eng = _engine()
        eng.record_deprecation("svc-a")
        eng.record_deprecation("svc-b")
        assert len(eng.list_deprecations()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_deprecation("svc-a")
        eng.record_deprecation("svc-b")
        results = eng.list_deprecations(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_deprecation("svc-a", stage=DeprecationStage.END_OF_LIFE)
        eng.record_deprecation("svc-b", stage=DeprecationStage.ANNOUNCED)
        results = eng.list_deprecations(stage=DeprecationStage.END_OF_LIFE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_migration_plan
# -------------------------------------------------------------------


class TestAddMigrationPlan:
    def test_basic(self):
        eng = _engine()
        p = eng.add_migration_plan(
            "svc-old",
            target_service="svc-new",
            migration_status=MigrationStatus.IN_PROGRESS,
            owner_team="platform",
        )
        assert p.service_name == "svc-old"
        assert p.target_service == "svc-new"
        assert p.owner_team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_migration_plan(f"svc-{i}")
        assert len(eng._migration_plans) == 2


# -------------------------------------------------------------------
# analyze_deprecation_by_stage
# -------------------------------------------------------------------


class TestAnalyzeDeprecationByStage:
    def test_with_data(self):
        eng = _engine()
        eng.record_deprecation(
            "svc-a", stage=DeprecationStage.END_OF_LIFE, impact=DeprecationImpact.CRITICAL
        )
        eng.record_deprecation("svc-b", stage=DeprecationStage.ANNOUNCED)
        result = eng.analyze_deprecation_by_stage()
        assert result["total_deprecations"] == 2
        assert "end_of_life" in result["by_stage"]

    def test_empty(self):
        eng = _engine()
        result = eng.analyze_deprecation_by_stage()
        assert result["total_deprecations"] == 0
        assert result["by_stage"] == {}


# -------------------------------------------------------------------
# identify_overdue_migrations
# -------------------------------------------------------------------


class TestIdentifyOverdueMigrations:
    def test_with_overdue(self):
        import time

        eng = _engine()
        past_eol = time.time() - 86400 * 10  # 10 days ago
        eng.record_deprecation(
            "svc-old",
            eol_date=past_eol,
            migration_status=MigrationStatus.NOT_STARTED,
        )
        results = eng.identify_overdue_migrations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-old"

    def test_completed_migration_excluded(self):
        import time

        eng = _engine()
        past_eol = time.time() - 86400 * 5
        eng.record_deprecation(
            "svc-done",
            eol_date=past_eol,
            migration_status=MigrationStatus.COMPLETED,
        )
        results = eng.identify_overdue_migrations()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_migrations() == []


# -------------------------------------------------------------------
# rank_by_urgency
# -------------------------------------------------------------------


class TestRankByUrgency:
    def test_with_data(self):
        eng = _engine()
        eng.record_deprecation(
            "svc-a", stage=DeprecationStage.END_OF_LIFE, impact=DeprecationImpact.CRITICAL
        )
        eng.record_deprecation(
            "svc-b", stage=DeprecationStage.ANNOUNCED, impact=DeprecationImpact.MINIMAL
        )
        results = eng.rank_by_urgency()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["urgency_score"] > results[1]["urgency_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_urgency() == []


# -------------------------------------------------------------------
# detect_deprecation_risks
# -------------------------------------------------------------------


class TestDetectDeprecationRisks:
    def test_with_risks(self):
        eng = _engine()
        eng.record_deprecation(
            "svc-risky",
            stage=DeprecationStage.END_OF_LIFE,
            impact=DeprecationImpact.CRITICAL,
            migration_status=MigrationStatus.NOT_STARTED,
            dependent_services=["svc-x", "svc-y"],
        )
        results = eng.detect_deprecation_risks()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-risky"

    def test_no_risks_for_completed(self):
        eng = _engine()
        eng.record_deprecation(
            "svc-safe",
            stage=DeprecationStage.END_OF_LIFE,
            impact=DeprecationImpact.CRITICAL,
            migration_status=MigrationStatus.COMPLETED,
        )
        assert eng.detect_deprecation_risks() == []

    def test_empty(self):
        eng = _engine()
        assert eng.detect_deprecation_risks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_deprecation("svc-a", stage=DeprecationStage.ANNOUNCED)
        eng.record_deprecation(
            "svc-b",
            stage=DeprecationStage.END_OF_LIFE,
            impact=DeprecationImpact.CRITICAL,
            migration_status=MigrationStatus.NOT_STARTED,
        )
        eng.add_migration_plan("svc-a", target_service="svc-new")
        report = eng.generate_report()
        assert report.total_deprecations == 2
        assert report.total_migration_plans == 1
        assert report.by_stage != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_deprecations == 0
        assert "on track" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_deprecation("svc-a")
        eng.add_migration_plan("svc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._migration_plans) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_deprecations"] == 0
        assert stats["total_migration_plans"] == 0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_deprecation("svc-a", stage=DeprecationStage.ANNOUNCED)
        eng.record_deprecation("svc-b", stage=DeprecationStage.END_OF_LIFE)
        eng.add_migration_plan("svc-a")
        stats = eng.get_stats()
        assert stats["total_deprecations"] == 2
        assert stats["total_migration_plans"] == 1
        assert stats["unique_services"] == 2
