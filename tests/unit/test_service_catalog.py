"""Tests for shieldops.topology.service_catalog — ServiceCatalogManager."""

from __future__ import annotations

import time

from shieldops.topology.service_catalog import (
    CatalogStats,
    DocumentationType,
    ServiceCatalogManager,
    ServiceEntry,
    ServiceLifecycle,
    ServiceSearchResult,
    ServiceTier,
)


def _engine(**kw) -> ServiceCatalogManager:
    return ServiceCatalogManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_tier_0(self):
        assert ServiceTier.TIER_0 == "tier_0"

    def test_tier_1(self):
        assert ServiceTier.TIER_1 == "tier_1"

    def test_tier_2(self):
        assert ServiceTier.TIER_2 == "tier_2"

    def test_tier_3(self):
        assert ServiceTier.TIER_3 == "tier_3"

    def test_lifecycle_incubating(self):
        assert ServiceLifecycle.INCUBATING == "incubating"

    def test_lifecycle_active(self):
        assert ServiceLifecycle.ACTIVE == "active"

    def test_lifecycle_deprecated(self):
        assert ServiceLifecycle.DEPRECATED == "deprecated"

    def test_lifecycle_decommissioned(self):
        assert ServiceLifecycle.DECOMMISSIONED == "decommissioned"

    def test_doc_openapi(self):
        assert DocumentationType.OPENAPI == "openapi"

    def test_doc_grpc(self):
        assert DocumentationType.GRPC == "grpc"

    def test_doc_graphql(self):
        assert DocumentationType.GRAPHQL == "graphql"

    def test_doc_runbook(self):
        assert DocumentationType.RUNBOOK == "runbook"

    def test_doc_architecture(self):
        assert DocumentationType.ARCHITECTURE == "architecture"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_service_entry_defaults(self):
        entry = ServiceEntry(name="auth-svc")
        assert entry.id
        assert entry.name == "auth-svc"
        assert entry.tier == ServiceTier.TIER_2
        assert entry.lifecycle == ServiceLifecycle.INCUBATING
        assert entry.owner == ""
        assert entry.dependencies == []
        assert entry.created_at > 0

    def test_search_result_defaults(self):
        result = ServiceSearchResult()
        assert result.services == []
        assert result.total == 0

    def test_catalog_stats_defaults(self):
        stats = CatalogStats()
        assert stats.total_services == 0
        assert stats.stale_count == 0


# ---------------------------------------------------------------------------
# register_service
# ---------------------------------------------------------------------------


class TestRegisterService:
    def test_basic_register(self):
        eng = _engine()
        entry = eng.register_service("auth-svc")
        assert entry.name == "auth-svc"
        assert eng.get_service(entry.id) is not None

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.register_service("svc-a")
        e2 = eng.register_service("svc-b")
        assert e1.id != e2.id

    def test_custom_fields(self):
        eng = _engine()
        entry = eng.register_service(
            "auth-svc", tier=ServiceTier.TIER_0, owner="team-a", team="platform"
        )
        assert entry.tier == ServiceTier.TIER_0
        assert entry.owner == "team-a"

    def test_evicts_at_max(self):
        eng = _engine(max_services=2)
        e1 = eng.register_service("svc-1")
        eng.register_service("svc-2")
        eng.register_service("svc-3")
        assert eng.get_service(e1.id) is None


# ---------------------------------------------------------------------------
# get_service / update_service
# ---------------------------------------------------------------------------


class TestGetService:
    def test_found(self):
        eng = _engine()
        entry = eng.register_service("svc-a")
        assert eng.get_service(entry.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_service("nonexistent") is None


class TestUpdateService:
    def test_basic_update(self):
        eng = _engine()
        entry = eng.register_service("svc-a")
        updated = eng.update_service(entry.id, owner="new-owner")
        assert updated is not None
        assert updated.owner == "new-owner"

    def test_update_not_found(self):
        eng = _engine()
        assert eng.update_service("nonexistent", owner="x") is None


# ---------------------------------------------------------------------------
# decommission_service
# ---------------------------------------------------------------------------


class TestDecommissionService:
    def test_decommission(self):
        eng = _engine()
        entry = eng.register_service("svc-a")
        result = eng.decommission_service(entry.id)
        assert result is not None
        assert result.lifecycle == ServiceLifecycle.DECOMMISSIONED

    def test_decommission_not_found(self):
        eng = _engine()
        assert eng.decommission_service("nonexistent") is None


# ---------------------------------------------------------------------------
# search_services
# ---------------------------------------------------------------------------


class TestSearchServices:
    def test_search_by_query(self):
        eng = _engine()
        eng.register_service("auth-service", description="Authentication service")
        eng.register_service("billing-service", description="Billing")
        result = eng.search_services(query="auth")
        assert result.total == 1

    def test_search_by_tier(self):
        eng = _engine()
        eng.register_service("svc-a", tier=ServiceTier.TIER_0)
        eng.register_service("svc-b", tier=ServiceTier.TIER_2)
        result = eng.search_services(tier=ServiceTier.TIER_0)
        assert result.total == 1

    def test_search_by_team(self):
        eng = _engine()
        eng.register_service("svc-a", team="platform")
        eng.register_service("svc-b", team="infra")
        result = eng.search_services(team="platform")
        assert result.total == 1


# ---------------------------------------------------------------------------
# dependencies / dependents
# ---------------------------------------------------------------------------


class TestDependencies:
    def test_list_dependencies(self):
        eng = _engine()
        dep = eng.register_service("dep-svc")
        main = eng.register_service("main-svc", dependencies=[dep.id])
        deps = eng.list_dependencies(main.id)
        assert len(deps) == 1
        assert deps[0].id == dep.id

    def test_get_dependents(self):
        eng = _engine()
        dep = eng.register_service("dep-svc")
        eng.register_service("main-svc", dependencies=[dep.id])
        dependents = eng.get_dependents(dep.id)
        assert len(dependents) == 1

    def test_list_dependencies_not_found(self):
        eng = _engine()
        assert eng.list_dependencies("nonexistent") == []


# ---------------------------------------------------------------------------
# stale services
# ---------------------------------------------------------------------------


class TestStaleServices:
    def test_stale_detection(self):
        eng = _engine(stale_days=0)
        entry = eng.register_service("svc-a")
        entry.updated_at = time.time() - 86400
        stale = eng.get_stale_services()
        assert len(stale) == 1

    def test_no_stale(self):
        eng = _engine(stale_days=9999)
        eng.register_service("svc-a")
        assert eng.get_stale_services() == []


# ---------------------------------------------------------------------------
# validate / stats
# ---------------------------------------------------------------------------


class TestValidateCatalog:
    def test_complete_service(self):
        eng = _engine()
        eng.register_service(
            "svc-a",
            owner="team-a",
            description="A service",
            documentation={"openapi": "https://docs.example.com"},
        )
        result = eng.validate_catalog_completeness()
        assert result["issues"] == []
        assert result["completeness_score"] == 100.0

    def test_incomplete_service(self):
        eng = _engine()
        eng.register_service("svc-a")
        result = eng.validate_catalog_completeness()
        assert len(result["issues"]) > 0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_services"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.register_service("svc-a", tier=ServiceTier.TIER_0)
        eng.register_service("svc-b", tier=ServiceTier.TIER_2)
        stats = eng.get_stats()
        assert stats["total_services"] == 2
        assert stats["tier_distribution"][ServiceTier.TIER_0] == 1
