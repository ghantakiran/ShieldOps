"""Tests for shieldops.changes.change_conflict_detector — ChangeConflictDetector."""

from __future__ import annotations

import time

from shieldops.changes.change_conflict_detector import (
    ChangeConflict,
    ChangeConflictDetector,
    ConflictReport,
    ConflictSeverity,
    ConflictType,
    PlannedChange,
    ResolutionStrategy,
)


def _engine(**kw) -> ChangeConflictDetector:
    return ChangeConflictDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ConflictType (5)
    def test_type_dependency_conflict(self):
        assert ConflictType.DEPENDENCY_CONFLICT == "dependency_conflict"

    def test_type_resource_contention(self):
        assert ConflictType.RESOURCE_CONTENTION == "resource_contention"

    def test_type_maintenance_overlap(self):
        assert ConflictType.MAINTENANCE_OVERLAP == "maintenance_overlap"

    def test_type_migration_collision(self):
        assert ConflictType.MIGRATION_COLLISION == "migration_collision"

    def test_type_freeze_violation(self):
        assert ConflictType.FREEZE_VIOLATION == "freeze_violation"

    # ConflictSeverity (5)
    def test_severity_advisory(self):
        assert ConflictSeverity.ADVISORY == "advisory"

    def test_severity_low(self):
        assert ConflictSeverity.LOW == "low"

    def test_severity_medium(self):
        assert ConflictSeverity.MEDIUM == "medium"

    def test_severity_high(self):
        assert ConflictSeverity.HIGH == "high"

    def test_severity_blocking(self):
        assert ConflictSeverity.BLOCKING == "blocking"

    # ResolutionStrategy (5)
    def test_strategy_reschedule_first(self):
        assert ResolutionStrategy.RESCHEDULE_FIRST == "reschedule_first"

    def test_strategy_reschedule_second(self):
        assert ResolutionStrategy.RESCHEDULE_SECOND == "reschedule_second"

    def test_strategy_merge_changes(self):
        assert ResolutionStrategy.MERGE_CHANGES == "merge_changes"

    def test_strategy_serialize_changes(self):
        assert ResolutionStrategy.SERIALIZE_CHANGES == "serialize_changes"

    def test_strategy_manual_coordination(self):
        assert ResolutionStrategy.MANUAL_COORDINATION == "manual_coordination"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_planned_change_defaults(self):
        c = PlannedChange()
        assert c.id
        assert c.change_name == ""
        assert c.service_name == ""
        assert c.owner == ""
        assert c.start_at == 0.0
        assert c.end_at == 0.0
        assert c.resources == []
        assert c.dependencies == []
        assert c.status == "planned"
        assert c.created_at > 0

    def test_change_conflict_defaults(self):
        c = ChangeConflict()
        assert c.id
        assert c.change_a_id == ""
        assert c.change_b_id == ""
        assert c.conflict_type == ConflictType.MAINTENANCE_OVERLAP
        assert c.severity == ConflictSeverity.LOW
        assert c.resolution == ResolutionStrategy.MANUAL_COORDINATION
        assert c.resolved is False
        assert c.description == ""
        assert c.created_at > 0

    def test_conflict_report_defaults(self):
        r = ConflictReport()
        assert r.total_changes == 0
        assert r.total_conflicts == 0
        assert r.total_resolved == 0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_resolution == {}
        assert r.blocking_conflicts == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_change
# ---------------------------------------------------------------------------


class TestRegisterChange:
    def test_basic_registration(self):
        eng = _engine()
        now = time.time()
        c = eng.register_change(
            change_name="deploy-api-v2",
            service_name="api-gateway",
            owner="platform",
            start_at=now,
            end_at=now + 3600,
            resources=["k8s-cluster-1"],
            dependencies=["auth-service"],
        )
        assert c.change_name == "deploy-api-v2"
        assert c.service_name == "api-gateway"
        assert c.owner == "platform"
        assert c.resources == ["k8s-cluster-1"]
        assert c.dependencies == ["auth-service"]
        assert c.status == "planned"

    def test_defaults(self):
        eng = _engine()
        c = eng.register_change(change_name="simple-change")
        assert c.service_name == ""
        assert c.resources == []
        assert c.dependencies == []

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.register_change(change_name=f"change-{i}")
        assert len(eng._changes) == 3


# ---------------------------------------------------------------------------
# get_change
# ---------------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        eng = _engine()
        c = eng.register_change(change_name="deploy-api")
        result = eng.get_change(c.id)
        assert result is not None
        assert result.change_name == "deploy-api"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_change("nonexistent") is None


# ---------------------------------------------------------------------------
# list_changes
# ---------------------------------------------------------------------------


class TestListChanges:
    def test_list_all(self):
        eng = _engine()
        eng.register_change(change_name="deploy-api")
        eng.register_change(change_name="migrate-db")
        assert len(eng.list_changes()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_change(change_name="deploy-api", service_name="api-gateway")
        eng.register_change(change_name="migrate-db", service_name="database")
        results = eng.list_changes(service_name="database")
        assert len(results) == 1
        assert results[0].change_name == "migrate-db"


# ---------------------------------------------------------------------------
# detect_conflicts
# ---------------------------------------------------------------------------


class TestDetectConflicts:
    def test_time_overlap_conflict(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="deploy-api",
            service_name="api",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="deploy-worker",
            service_name="worker",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        conflicts = eng.detect_conflicts(c1.id)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.MAINTENANCE_OVERLAP

    def test_no_conflict(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="deploy-api",
            start_at=now,
            end_at=now + 3600,
        )
        eng.register_change(
            change_name="deploy-worker",
            start_at=now + 7200,
            end_at=now + 10800,
        )
        conflicts = eng.detect_conflicts(c1.id)
        assert len(conflicts) == 0

    def test_nonexistent_change(self):
        eng = _engine()
        assert eng.detect_conflicts("nonexistent") == []

    def test_resource_contention_with_overlap(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="deploy-api",
            start_at=now,
            end_at=now + 7200,
            resources=["k8s-cluster-1"],
        )
        eng.register_change(
            change_name="scale-worker",
            start_at=now + 3600,
            end_at=now + 10800,
            resources=["k8s-cluster-1"],
        )
        conflicts = eng.detect_conflicts(c1.id)
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.RESOURCE_CONTENTION
        assert conflicts[0].severity == ConflictSeverity.BLOCKING


# ---------------------------------------------------------------------------
# detect_all_conflicts
# ---------------------------------------------------------------------------


class TestDetectAllConflicts:
    def test_pairwise_detection(self):
        eng = _engine()
        now = time.time()
        eng.register_change(
            change_name="c1",
            service_name="api",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="c2",
            service_name="worker",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        eng.register_change(
            change_name="c3",
            service_name="db",
            start_at=now + 20000,
            end_at=now + 30000,
        )
        conflicts = eng.detect_all_conflicts()
        # Only c1-c2 overlap; c3 does not overlap with either
        assert len(conflicts) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_all_conflicts() == []


# ---------------------------------------------------------------------------
# get_conflict
# ---------------------------------------------------------------------------


class TestGetConflict:
    def test_found(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="c1",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="c2",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        conflicts = eng.detect_conflicts(c1.id)
        result = eng.get_conflict(conflicts[0].id)
        assert result is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_conflict("nonexistent") is None


# ---------------------------------------------------------------------------
# list_conflicts
# ---------------------------------------------------------------------------


class TestListConflicts:
    def test_list_all(self):
        eng = _engine()
        now = time.time()
        eng.register_change(change_name="c1", start_at=now, end_at=now + 7200)
        eng.register_change(
            change_name="c2",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        eng.detect_all_conflicts()
        assert len(eng.list_conflicts()) >= 1

    def test_filter_by_severity(self):
        eng = _engine()
        now = time.time()
        eng.register_change(change_name="c1", start_at=now, end_at=now + 7200)
        eng.register_change(
            change_name="c2",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        eng.detect_all_conflicts()
        # Time-only overlap is LOW severity
        results = eng.list_conflicts(severity=ConflictSeverity.LOW)
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# resolve_conflict
# ---------------------------------------------------------------------------


class TestResolveConflict:
    def test_resolve_successfully(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="c1",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="c2",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        conflicts = eng.detect_conflicts(c1.id)
        result = eng.resolve_conflict(
            conflicts[0].id,
            resolution=ResolutionStrategy.SERIALIZE_CHANGES,
        )
        assert result is True
        assert conflicts[0].resolved is True
        assert conflicts[0].resolution == ResolutionStrategy.SERIALIZE_CHANGES

    def test_not_found(self):
        eng = _engine()
        assert eng.resolve_conflict("nonexistent") is False


# ---------------------------------------------------------------------------
# suggest_reschedule
# ---------------------------------------------------------------------------


class TestSuggestReschedule:
    def test_suggest_for_conflict(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="deploy-api",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="deploy-worker",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        conflicts = eng.detect_conflicts(c1.id)
        result = eng.suggest_reschedule(conflicts[0].id)
        assert result["found"] is True
        assert "suggestion" in result
        assert result["suggested_start_at"] > 0
        assert result["strategy"] == ResolutionStrategy.SERIALIZE_CHANGES.value

    def test_not_found(self):
        eng = _engine()
        result = eng.suggest_reschedule("nonexistent")
        assert result["found"] is False


# ---------------------------------------------------------------------------
# generate_conflict_report
# ---------------------------------------------------------------------------


class TestGenerateConflictReport:
    def test_basic_report(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="c1",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="c2",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        eng.detect_conflicts(c1.id)
        report = eng.generate_conflict_report()
        assert isinstance(report, ConflictReport)
        assert report.total_changes == 2
        assert report.total_conflicts >= 1
        assert len(report.by_type) > 0
        assert len(report.by_severity) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_conflict_report()
        assert report.total_changes == 0
        assert report.total_conflicts == 0
        assert "No change conflicts detected" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="c1",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="c2",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        eng.detect_conflicts(c1.id)
        count = eng.clear_data()
        assert count >= 3  # 2 changes + at least 1 conflict
        assert len(eng._changes) == 0
        assert len(eng._conflicts) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_changes"] == 0
        assert stats["total_conflicts"] == 0
        assert stats["severity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        now = time.time()
        c1 = eng.register_change(
            change_name="c1",
            start_at=now,
            end_at=now + 7200,
        )
        eng.register_change(
            change_name="c2",
            start_at=now + 3600,
            end_at=now + 10800,
        )
        eng.detect_conflicts(c1.id)
        stats = eng.get_stats()
        assert stats["total_changes"] == 2
        assert stats["total_conflicts"] >= 1
        assert stats["lookahead_hours"] == 168
