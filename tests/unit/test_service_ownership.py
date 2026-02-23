"""Tests for the service ownership registry module.

Covers:
- OwnershipStatus enum values
- EscalationContact model defaults
- TeamInfo model defaults
- ServiceOwner model defaults
- ServiceOwnershipRegistry creation
- register_owner() with full params, minimal, max limit, update existing
- get_owner() found and not found
- get_team_services() with results and empty
- find_orphaned_services() with orphaned and non-orphaned
- get_escalation_path() with contacts, empty, not found
- update_status() to each status, not found
- list_owners() with/without status filter, limit
- get_stats() counts
"""

from __future__ import annotations

import pytest

from shieldops.topology.ownership import (
    EscalationContact,
    OwnershipStatus,
    ServiceOwner,
    ServiceOwnershipRegistry,
    TeamInfo,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def registry() -> ServiceOwnershipRegistry:
    """Return a fresh ServiceOwnershipRegistry."""
    return ServiceOwnershipRegistry()


@pytest.fixture()
def populated_registry() -> ServiceOwnershipRegistry:
    """Return a registry with several owners pre-registered."""
    reg = ServiceOwnershipRegistry()
    reg.register_owner(
        service_id="api-gateway",
        team_id="platform",
        team_name="Platform Team",
        service_name="API Gateway",
        tier="tier-1",
        tags=["critical", "public"],
        escalation_contacts=[
            {"name": "Alice", "email": "alice@example.com", "role": "primary"},
            {"name": "Bob", "email": "bob@example.com", "role": "secondary"},
        ],
    )
    reg.register_owner(
        service_id="user-service",
        team_id="platform",
        team_name="Platform Team",
        service_name="User Service",
        tier="tier-2",
    )
    reg.register_owner(
        service_id="billing",
        team_id="payments",
        team_name="Payments Team",
        service_name="Billing Service",
        tier="tier-1",
    )
    return reg


# ── Enum Tests ───────────────────────────────────────────────────


class TestOwnershipStatusEnum:
    def test_active_value(self) -> None:
        assert OwnershipStatus.ACTIVE == "active"

    def test_deprecated_value(self) -> None:
        assert OwnershipStatus.DEPRECATED == "deprecated"

    def test_orphaned_value(self) -> None:
        assert OwnershipStatus.ORPHANED == "orphaned"

    def test_all_members_present(self) -> None:
        members = {m.value for m in OwnershipStatus}
        assert members == {"active", "deprecated", "orphaned"}


# ── Model Tests ──────────────────────────────────────────────────


class TestEscalationContactModel:
    def test_minimal_creation(self) -> None:
        contact = EscalationContact(name="Jane")
        assert contact.name == "Jane"
        assert contact.email == ""
        assert contact.slack_channel == ""
        assert contact.phone == ""
        assert contact.role == "primary"

    def test_full_creation(self) -> None:
        contact = EscalationContact(
            name="Jane",
            email="jane@example.com",
            slack_channel="#ops",
            phone="+1-555-0100",
            role="secondary",
        )
        assert contact.email == "jane@example.com"
        assert contact.slack_channel == "#ops"
        assert contact.phone == "+1-555-0100"
        assert contact.role == "secondary"


class TestTeamInfoModel:
    def test_minimal_creation(self) -> None:
        team = TeamInfo(team_id="t1", name="Team One")
        assert team.team_id == "t1"
        assert team.name == "Team One"
        assert team.slack_channel == ""
        assert team.email == ""
        assert team.manager == ""
        assert team.metadata == {}

    def test_full_creation(self) -> None:
        team = TeamInfo(
            team_id="t2",
            name="Team Two",
            slack_channel="#team2",
            email="team2@example.com",
            manager="John",
            metadata={"region": "us-east-1"},
        )
        assert team.slack_channel == "#team2"
        assert team.manager == "John"
        assert team.metadata == {"region": "us-east-1"}


class TestServiceOwnerModel:
    def test_defaults(self) -> None:
        team = TeamInfo(team_id="t1", name="T1")
        owner = ServiceOwner(service_id="svc-1", team=team)
        assert owner.service_id == "svc-1"
        assert owner.service_name == ""
        assert owner.status == OwnershipStatus.ACTIVE
        assert owner.escalation_contacts == []
        assert owner.description == ""
        assert owner.repository_url == ""
        assert owner.documentation_url == ""
        assert owner.tier == "tier-3"
        assert owner.tags == []
        assert owner.metadata == {}
        assert owner.created_at > 0
        assert owner.updated_at > 0
        assert len(owner.id) == 12

    def test_id_auto_generated_unique(self) -> None:
        team = TeamInfo(team_id="t1", name="T1")
        owner1 = ServiceOwner(service_id="svc-1", team=team)
        owner2 = ServiceOwner(service_id="svc-2", team=team)
        assert owner1.id != owner2.id


# ── Registry Creation ────────────────────────────────────────────


class TestRegistryCreation:
    def test_default_max_entries(self) -> None:
        reg = ServiceOwnershipRegistry()
        assert reg._max_entries == 5000

    def test_custom_max_entries(self) -> None:
        reg = ServiceOwnershipRegistry(max_entries=10)
        assert reg._max_entries == 10

    def test_starts_empty(self) -> None:
        reg = ServiceOwnershipRegistry()
        assert len(reg._owners) == 0


# ── register_owner ───────────────────────────────────────────────


class TestRegisterOwner:
    def test_minimal_params(self, registry: ServiceOwnershipRegistry) -> None:
        owner = registry.register_owner(
            service_id="svc-1",
            team_id="team-a",
            team_name="Team A",
        )
        assert owner.service_id == "svc-1"
        assert owner.service_name == "svc-1", "service_name defaults to service_id"
        assert owner.team.team_id == "team-a"
        assert owner.team.name == "Team A"
        assert owner.status == OwnershipStatus.ACTIVE
        assert owner.tier == "tier-3"

    def test_full_params(self, registry: ServiceOwnershipRegistry) -> None:
        owner = registry.register_owner(
            service_id="svc-2",
            team_id="team-b",
            team_name="Team B",
            service_name="My Service",
            escalation_contacts=[{"name": "Alice", "email": "a@b.com"}],
            description="A critical service",
            repository_url="https://github.com/org/repo",
            documentation_url="https://docs.example.com",
            tier="tier-1",
            tags=["critical"],
            team_slack="#team-b",
            team_email="team-b@example.com",
            team_manager="Boss",
            metadata={"owner_type": "internal"},
        )
        assert owner.service_name == "My Service"
        assert owner.description == "A critical service"
        assert owner.repository_url == "https://github.com/org/repo"
        assert owner.documentation_url == "https://docs.example.com"
        assert owner.tier == "tier-1"
        assert owner.tags == ["critical"]
        assert owner.team.slack_channel == "#team-b"
        assert owner.team.email == "team-b@example.com"
        assert owner.team.manager == "Boss"
        assert owner.metadata == {"owner_type": "internal"}
        assert len(owner.escalation_contacts) == 1
        assert owner.escalation_contacts[0].name == "Alice"

    def test_update_existing_service(self, registry: ServiceOwnershipRegistry) -> None:
        registry.register_owner(service_id="svc-1", team_id="team-a", team_name="Team A")
        owner2 = registry.register_owner(service_id="svc-1", team_id="team-b", team_name="Team B")
        assert owner2.team.team_id == "team-b"
        assert registry.get_owner("svc-1").team.team_id == "team-b"
        assert len(registry._owners) == 1, "Should replace, not add"

    def test_max_limit_raises(self) -> None:
        reg = ServiceOwnershipRegistry(max_entries=2)
        reg.register_owner(service_id="s1", team_id="t1", team_name="T1")
        reg.register_owner(service_id="s2", team_id="t1", team_name="T1")
        with pytest.raises(ValueError, match="Maximum entries limit reached"):
            reg.register_owner(service_id="s3", team_id="t1", team_name="T1")

    def test_max_limit_allows_update_existing(self) -> None:
        reg = ServiceOwnershipRegistry(max_entries=2)
        reg.register_owner(service_id="s1", team_id="t1", team_name="T1")
        reg.register_owner(service_id="s2", team_id="t1", team_name="T1")
        # Updating s1 should NOT raise
        owner = reg.register_owner(service_id="s1", team_id="t2", team_name="T2")
        assert owner.team.team_id == "t2"

    def test_multiple_escalation_contacts(self, registry: ServiceOwnershipRegistry) -> None:
        owner = registry.register_owner(
            service_id="svc-1",
            team_id="team-a",
            team_name="Team A",
            escalation_contacts=[
                {"name": "Alice", "role": "primary"},
                {"name": "Bob", "role": "secondary"},
                {"name": "Charlie", "role": "manager"},
            ],
        )
        assert len(owner.escalation_contacts) == 3
        assert owner.escalation_contacts[2].name == "Charlie"

    def test_returns_service_owner_instance(self, registry: ServiceOwnershipRegistry) -> None:
        owner = registry.register_owner(service_id="svc-1", team_id="t1", team_name="T1")
        assert isinstance(owner, ServiceOwner)


# ── get_owner ────────────────────────────────────────────────────


class TestGetOwner:
    def test_found(self, populated_registry: ServiceOwnershipRegistry) -> None:
        owner = populated_registry.get_owner("api-gateway")
        assert owner is not None
        assert owner.service_id == "api-gateway"
        assert owner.service_name == "API Gateway"

    def test_not_found(self, populated_registry: ServiceOwnershipRegistry) -> None:
        result = populated_registry.get_owner("nonexistent-service")
        assert result is None

    def test_empty_registry(self, registry: ServiceOwnershipRegistry) -> None:
        assert registry.get_owner("anything") is None


# ── get_team_services ────────────────────────────────────────────


class TestGetTeamServices:
    def test_returns_matching_services(self, populated_registry: ServiceOwnershipRegistry) -> None:
        services = populated_registry.get_team_services("platform")
        assert len(services) == 2
        svc_ids = {s.service_id for s in services}
        assert svc_ids == {"api-gateway", "user-service"}

    def test_returns_single_service(self, populated_registry: ServiceOwnershipRegistry) -> None:
        services = populated_registry.get_team_services("payments")
        assert len(services) == 1
        assert services[0].service_id == "billing"

    def test_no_matching_team(self, populated_registry: ServiceOwnershipRegistry) -> None:
        services = populated_registry.get_team_services("nonexistent")
        assert services == []

    def test_empty_registry(self, registry: ServiceOwnershipRegistry) -> None:
        assert registry.get_team_services("any-team") == []


# ── find_orphaned_services ───────────────────────────────────────


class TestFindOrphanedServices:
    def test_no_orphaned(self, populated_registry: ServiceOwnershipRegistry) -> None:
        orphaned = populated_registry.find_orphaned_services()
        assert orphaned == []

    def test_with_orphaned(self, populated_registry: ServiceOwnershipRegistry) -> None:
        populated_registry.update_status("api-gateway", OwnershipStatus.ORPHANED)
        orphaned = populated_registry.find_orphaned_services()
        assert len(orphaned) == 1
        assert orphaned[0].service_id == "api-gateway"

    def test_multiple_orphaned(self, populated_registry: ServiceOwnershipRegistry) -> None:
        populated_registry.update_status("api-gateway", OwnershipStatus.ORPHANED)
        populated_registry.update_status("billing", OwnershipStatus.ORPHANED)
        orphaned = populated_registry.find_orphaned_services()
        assert len(orphaned) == 2

    def test_deprecated_not_orphaned(self, populated_registry: ServiceOwnershipRegistry) -> None:
        populated_registry.update_status("api-gateway", OwnershipStatus.DEPRECATED)
        orphaned = populated_registry.find_orphaned_services()
        assert orphaned == []


# ── get_escalation_path ──────────────────────────────────────────


class TestGetEscalationPath:
    def test_with_contacts(self, populated_registry: ServiceOwnershipRegistry) -> None:
        contacts = populated_registry.get_escalation_path("api-gateway")
        assert len(contacts) == 2
        assert contacts[0].name == "Alice"
        assert contacts[1].name == "Bob"
        assert all(isinstance(c, EscalationContact) for c in contacts)

    def test_empty_contacts(self, populated_registry: ServiceOwnershipRegistry) -> None:
        contacts = populated_registry.get_escalation_path("user-service")
        assert contacts == []

    def test_not_found(self, populated_registry: ServiceOwnershipRegistry) -> None:
        contacts = populated_registry.get_escalation_path("nonexistent")
        assert contacts == []

    def test_empty_registry(self, registry: ServiceOwnershipRegistry) -> None:
        assert registry.get_escalation_path("anything") == []


# ── update_status ────────────────────────────────────────────────


class TestUpdateStatus:
    def test_to_deprecated(self, populated_registry: ServiceOwnershipRegistry) -> None:
        owner = populated_registry.update_status("api-gateway", OwnershipStatus.DEPRECATED)
        assert owner is not None
        assert owner.status == OwnershipStatus.DEPRECATED

    def test_to_orphaned(self, populated_registry: ServiceOwnershipRegistry) -> None:
        owner = populated_registry.update_status("api-gateway", OwnershipStatus.ORPHANED)
        assert owner is not None
        assert owner.status == OwnershipStatus.ORPHANED

    def test_to_active(self, populated_registry: ServiceOwnershipRegistry) -> None:
        populated_registry.update_status("api-gateway", OwnershipStatus.ORPHANED)
        owner = populated_registry.update_status("api-gateway", OwnershipStatus.ACTIVE)
        assert owner is not None
        assert owner.status == OwnershipStatus.ACTIVE

    def test_updates_updated_at(self, populated_registry: ServiceOwnershipRegistry) -> None:
        owner_before = populated_registry.get_owner("api-gateway")
        ts_before = owner_before.updated_at
        owner_after = populated_registry.update_status("api-gateway", OwnershipStatus.DEPRECATED)
        assert owner_after.updated_at >= ts_before

    def test_not_found(self, populated_registry: ServiceOwnershipRegistry) -> None:
        result = populated_registry.update_status("no-such-svc", OwnershipStatus.ACTIVE)
        assert result is None

    def test_persists_in_get_owner(self, populated_registry: ServiceOwnershipRegistry) -> None:
        populated_registry.update_status("billing", OwnershipStatus.DEPRECATED)
        owner = populated_registry.get_owner("billing")
        assert owner.status == OwnershipStatus.DEPRECATED


# ── list_owners ──────────────────────────────────────────────────


class TestListOwners:
    def test_all_owners(self, populated_registry: ServiceOwnershipRegistry) -> None:
        owners = populated_registry.list_owners()
        assert len(owners) == 3

    def test_filter_by_status_active(self, populated_registry: ServiceOwnershipRegistry) -> None:
        populated_registry.update_status("api-gateway", OwnershipStatus.DEPRECATED)
        owners = populated_registry.list_owners(status=OwnershipStatus.ACTIVE)
        assert len(owners) == 2
        assert all(o.status == OwnershipStatus.ACTIVE for o in owners)

    def test_filter_by_status_deprecated(
        self, populated_registry: ServiceOwnershipRegistry
    ) -> None:
        populated_registry.update_status("api-gateway", OwnershipStatus.DEPRECATED)
        owners = populated_registry.list_owners(status=OwnershipStatus.DEPRECATED)
        assert len(owners) == 1
        assert owners[0].service_id == "api-gateway"

    def test_filter_no_match(self, populated_registry: ServiceOwnershipRegistry) -> None:
        owners = populated_registry.list_owners(status=OwnershipStatus.ORPHANED)
        assert owners == []

    def test_limit(self, populated_registry: ServiceOwnershipRegistry) -> None:
        owners = populated_registry.list_owners(limit=1)
        assert len(owners) == 1

    def test_sorted_by_created_at_desc(self, registry: ServiceOwnershipRegistry) -> None:
        registry.register_owner(service_id="s1", team_id="t1", team_name="T1")
        registry.register_owner(service_id="s2", team_id="t1", team_name="T1")
        registry.register_owner(service_id="s3", team_id="t1", team_name="T1")
        owners = registry.list_owners()
        for i in range(len(owners) - 1):
            assert owners[i].created_at >= owners[i + 1].created_at

    def test_empty_registry(self, registry: ServiceOwnershipRegistry) -> None:
        assert registry.list_owners() == []


# ── get_stats ────────────────────────────────────────────────────


class TestGetStats:
    def test_empty_registry(self, registry: ServiceOwnershipRegistry) -> None:
        stats = registry.get_stats()
        assert stats["total_services"] == 0
        assert stats["total_teams"] == 0
        assert stats["by_status"] == {}

    def test_populated(self, populated_registry: ServiceOwnershipRegistry) -> None:
        stats = populated_registry.get_stats()
        assert stats["total_services"] == 3
        assert stats["total_teams"] == 2
        assert stats["by_status"]["active"] == 3

    def test_mixed_statuses(self, populated_registry: ServiceOwnershipRegistry) -> None:
        populated_registry.update_status("api-gateway", OwnershipStatus.DEPRECATED)
        populated_registry.update_status("billing", OwnershipStatus.ORPHANED)
        stats = populated_registry.get_stats()
        assert stats["by_status"]["active"] == 1
        assert stats["by_status"]["deprecated"] == 1
        assert stats["by_status"]["orphaned"] == 1

    def test_counts_unique_teams(self, registry: ServiceOwnershipRegistry) -> None:
        registry.register_owner(service_id="s1", team_id="t1", team_name="T1")
        registry.register_owner(service_id="s2", team_id="t1", team_name="T1")
        stats = registry.get_stats()
        assert stats["total_teams"] == 1
