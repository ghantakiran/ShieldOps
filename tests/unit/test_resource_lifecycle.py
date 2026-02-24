"""Tests for shieldops.billing.resource_lifecycle — ResourceLifecycleTracker."""

from __future__ import annotations

import time

from shieldops.billing.resource_lifecycle import (
    LifecyclePhase,
    LifecycleSummary,
    PhaseTransition,
    ResourceCategory,
    ResourceEntry,
    ResourceLifecycleTracker,
    TransitionReason,
)


def _engine(**kw) -> ResourceLifecycleTracker:
    return ResourceLifecycleTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # LifecyclePhase (6)
    def test_phase_provisioning(self):
        assert LifecyclePhase.PROVISIONING == "provisioning"

    def test_phase_active(self):
        assert LifecyclePhase.ACTIVE == "active"

    def test_phase_scaling(self):
        assert LifecyclePhase.SCALING == "scaling"

    def test_phase_deprecated(self):
        assert LifecyclePhase.DEPRECATED == "deprecated"

    def test_phase_decommissioning(self):
        assert LifecyclePhase.DECOMMISSIONING == "decommissioning"

    def test_phase_terminated(self):
        assert LifecyclePhase.TERMINATED == "terminated"

    # ResourceCategory (6)
    def test_category_compute(self):
        assert ResourceCategory.COMPUTE == "compute"

    def test_category_database(self):
        assert ResourceCategory.DATABASE == "database"

    def test_category_storage(self):
        assert ResourceCategory.STORAGE == "storage"

    def test_category_network(self):
        assert ResourceCategory.NETWORK == "network"

    def test_category_container(self):
        assert ResourceCategory.CONTAINER == "container"

    def test_category_serverless(self):
        assert ResourceCategory.SERVERLESS == "serverless"

    # TransitionReason (6)
    def test_reason_planned(self):
        assert TransitionReason.PLANNED == "planned"

    def test_reason_cost_optimization(self):
        assert TransitionReason.COST_OPTIMIZATION == "cost_optimization"

    def test_reason_end_of_life(self):
        assert TransitionReason.END_OF_LIFE == "end_of_life"

    def test_reason_security_concern(self):
        assert TransitionReason.SECURITY_CONCERN == "security_concern"

    def test_reason_migration(self):
        assert TransitionReason.MIGRATION == "migration"

    def test_reason_auto_scaling(self):
        assert TransitionReason.AUTO_SCALING == "auto_scaling"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_resource_entry_defaults(self):
        r = ResourceEntry(resource_name="test", category=ResourceCategory.COMPUTE)
        assert r.id
        assert r.phase == LifecyclePhase.PROVISIONING
        assert r.owner == ""
        assert r.environment == "production"
        assert r.monthly_cost == 0.0

    def test_phase_transition_defaults(self):
        t = PhaseTransition(
            resource_id="r1",
            from_phase=LifecyclePhase.ACTIVE,
            to_phase=LifecyclePhase.DEPRECATED,
        )
        assert t.id
        assert t.reason == TransitionReason.PLANNED
        assert t.transitioned_at > 0

    def test_lifecycle_summary_defaults(self):
        s = LifecycleSummary()
        assert s.total_resources == 0
        assert s.phase_breakdown == {}
        assert s.category_breakdown == {}
        assert s.stale_count == 0
        assert s.decommission_candidates == 0
        assert s.avg_age_days == 0.0
        assert s.total_monthly_cost == 0.0
        assert s.recommendations == []


# ---------------------------------------------------------------------------
# register_resource
# ---------------------------------------------------------------------------


class TestRegisterResource:
    def test_basic_register(self):
        eng = _engine()
        r = eng.register_resource(
            resource_name="web-server-1",
            category=ResourceCategory.COMPUTE,
            owner="team-a",
            monthly_cost=150.0,
        )
        assert r.resource_name == "web-server-1"
        assert r.category == ResourceCategory.COMPUTE
        assert r.owner == "team-a"
        assert r.monthly_cost == 150.0
        assert r.phase == LifecyclePhase.PROVISIONING

    def test_eviction_at_max(self):
        eng = _engine(max_resources=3)
        for i in range(5):
            eng.register_resource(resource_name=f"res-{i}", category=ResourceCategory.STORAGE)
        assert len(eng._resources) == 3


# ---------------------------------------------------------------------------
# get_resource
# ---------------------------------------------------------------------------


class TestGetResource:
    def test_found(self):
        eng = _engine()
        r = eng.register_resource(resource_name="db-1", category=ResourceCategory.DATABASE)
        assert eng.get_resource(r.id) is not None
        assert eng.get_resource(r.id).resource_name == "db-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_resource("nonexistent") is None


# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------


class TestListResources:
    def test_list_all(self):
        eng = _engine()
        eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        eng.register_resource(resource_name="b", category=ResourceCategory.STORAGE)
        assert len(eng.list_resources()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        eng.register_resource(resource_name="b", category=ResourceCategory.STORAGE)
        results = eng.list_resources(category=ResourceCategory.COMPUTE)
        assert len(results) == 1
        assert results[0].resource_name == "a"

    def test_filter_by_phase(self):
        eng = _engine()
        r = eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        eng.register_resource(resource_name="b", category=ResourceCategory.COMPUTE)
        eng.transition_phase(r.id, LifecyclePhase.ACTIVE)
        results = eng.list_resources(phase=LifecyclePhase.ACTIVE)
        assert len(results) == 1
        assert results[0].id == r.id


# ---------------------------------------------------------------------------
# transition_phase
# ---------------------------------------------------------------------------


class TestTransitionPhase:
    def test_success(self):
        eng = _engine()
        r = eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        t = eng.transition_phase(r.id, LifecyclePhase.ACTIVE, TransitionReason.PLANNED)
        assert t is not None
        assert t.from_phase == LifecyclePhase.PROVISIONING
        assert t.to_phase == LifecyclePhase.ACTIVE
        assert r.phase == LifecyclePhase.ACTIVE
        assert len(eng._transitions) == 1

    def test_not_found(self):
        eng = _engine()
        assert eng.transition_phase("bad-id", LifecyclePhase.ACTIVE) is None


# ---------------------------------------------------------------------------
# list_transitions
# ---------------------------------------------------------------------------


class TestListTransitions:
    def test_list_all(self):
        eng = _engine()
        r1 = eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        r2 = eng.register_resource(resource_name="b", category=ResourceCategory.STORAGE)
        eng.transition_phase(r1.id, LifecyclePhase.ACTIVE)
        eng.transition_phase(r2.id, LifecyclePhase.ACTIVE)
        assert len(eng.list_transitions()) == 2

    def test_filter_by_resource_id(self):
        eng = _engine()
        r1 = eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        r2 = eng.register_resource(resource_name="b", category=ResourceCategory.STORAGE)
        eng.transition_phase(r1.id, LifecyclePhase.ACTIVE)
        eng.transition_phase(r2.id, LifecyclePhase.ACTIVE)
        results = eng.list_transitions(resource_id=r1.id)
        assert len(results) == 1
        assert results[0].resource_id == r1.id


# ---------------------------------------------------------------------------
# detect_stale_resources
# ---------------------------------------------------------------------------


class TestDetectStaleResources:
    def test_none_recent(self):
        eng = _engine(stale_days=180)
        r = eng.register_resource(resource_name="new", category=ResourceCategory.COMPUTE)
        eng.transition_phase(r.id, LifecyclePhase.ACTIVE)
        assert len(eng.detect_stale_resources()) == 0

    def test_some_stale(self):
        eng = _engine(stale_days=180)
        r = eng.register_resource(resource_name="old", category=ResourceCategory.COMPUTE)
        eng.transition_phase(r.id, LifecyclePhase.ACTIVE)
        # Manually set created_at to 200 days ago
        r.created_at = time.time() - (200 * 86400)
        stale = eng.detect_stale_resources()
        assert len(stale) == 1
        assert stale[0].id == r.id


# ---------------------------------------------------------------------------
# get_decommission_candidates
# ---------------------------------------------------------------------------


class TestGetDecommissionCandidates:
    def test_none(self):
        eng = _engine()
        eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        assert len(eng.get_decommission_candidates()) == 0

    def test_some_deprecated(self):
        eng = _engine()
        r = eng.register_resource(resource_name="old-srv", category=ResourceCategory.COMPUTE)
        eng.transition_phase(r.id, LifecyclePhase.DEPRECATED)
        candidates = eng.get_decommission_candidates()
        assert len(candidates) == 1
        assert candidates[0].id == r.id


# ---------------------------------------------------------------------------
# compute_age_distribution
# ---------------------------------------------------------------------------


class TestComputeAgeDistribution:
    def test_empty(self):
        eng = _engine()
        dist = eng.compute_age_distribution()
        assert dist["total_resources"] == 0
        assert dist["distribution"]["0_30d"] == 0

    def test_with_data(self):
        eng = _engine()
        # Recent resource (within 30 days)
        eng.register_resource(resource_name="new", category=ResourceCategory.COMPUTE)
        # Old resource (200 days ago)
        r = eng.register_resource(resource_name="old", category=ResourceCategory.STORAGE)
        r.created_at = time.time() - (200 * 86400)
        dist = eng.compute_age_distribution()
        assert dist["total_resources"] == 2
        assert dist["distribution"]["0_30d"] == 1
        assert dist["distribution"]["180d_plus"] == 1


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    def test_basic_summary(self):
        eng = _engine()
        eng.register_resource(
            resource_name="srv-1",
            category=ResourceCategory.COMPUTE,
            monthly_cost=100.0,
        )
        eng.register_resource(
            resource_name="srv-2",
            category=ResourceCategory.DATABASE,
            monthly_cost=250.0,
        )
        summary = eng.generate_summary()
        assert summary.total_resources == 2
        assert summary.total_monthly_cost == 350.0
        assert LifecyclePhase.PROVISIONING in summary.phase_breakdown
        assert ResourceCategory.COMPUTE in summary.category_breakdown
        assert ResourceCategory.DATABASE in summary.category_breakdown


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        r = eng.register_resource(resource_name="a", category=ResourceCategory.COMPUTE)
        eng.transition_phase(r.id, LifecyclePhase.ACTIVE)
        assert len(eng._resources) == 1
        assert len(eng._transitions) == 1
        eng.clear_data()
        assert len(eng._resources) == 0
        assert len(eng._transitions) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_resources"] == 0
        assert stats["total_transitions"] == 0
        assert stats["phase_distribution"] == {}
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        r = eng.register_resource(resource_name="srv", category=ResourceCategory.COMPUTE)
        eng.transition_phase(r.id, LifecyclePhase.ACTIVE)
        stats = eng.get_stats()
        assert stats["total_resources"] == 1
        assert stats["total_transitions"] == 1
        assert stats["max_resources"] == 100000
        assert stats["stale_days"] == 180
