"""Service ownership registry.

Maps teams to services with escalation contacts, tracks orphaned services,
and provides service-to-team lookups.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class OwnershipStatus(enum.StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ORPHANED = "orphaned"


# ── Models ───────────────────────────────────────────────────────────


class EscalationContact(BaseModel):
    name: str
    email: str = ""
    slack_channel: str = ""
    phone: str = ""
    role: str = "primary"


class TeamInfo(BaseModel):
    team_id: str
    name: str
    slack_channel: str = ""
    email: str = ""
    manager: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceOwner(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service_id: str
    service_name: str = ""
    team: TeamInfo
    status: OwnershipStatus = OwnershipStatus.ACTIVE
    escalation_contacts: list[EscalationContact] = Field(default_factory=list)
    description: str = ""
    repository_url: str = ""
    documentation_url: str = ""
    tier: str = "tier-3"
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Registry ─────────────────────────────────────────────────────────


class ServiceOwnershipRegistry:
    """Track service ownership and escalation paths.

    Parameters
    ----------
    max_entries:
        Maximum ownership entries to store.
    """

    def __init__(self, max_entries: int = 5000) -> None:
        self._owners: dict[str, ServiceOwner] = {}
        self._max_entries = max_entries

    def register_owner(
        self,
        service_id: str,
        team_id: str,
        team_name: str,
        service_name: str = "",
        escalation_contacts: list[dict[str, Any]] | None = None,
        description: str = "",
        repository_url: str = "",
        documentation_url: str = "",
        tier: str = "tier-3",
        tags: list[str] | None = None,
        team_slack: str = "",
        team_email: str = "",
        team_manager: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ServiceOwner:
        if len(self._owners) >= self._max_entries and service_id not in self._owners:
            raise ValueError(f"Maximum entries limit reached: {self._max_entries}")
        contacts = [EscalationContact(**c) for c in (escalation_contacts or [])]
        team = TeamInfo(
            team_id=team_id,
            name=team_name,
            slack_channel=team_slack,
            email=team_email,
            manager=team_manager,
        )
        owner = ServiceOwner(
            service_id=service_id,
            service_name=service_name or service_id,
            team=team,
            escalation_contacts=contacts,
            description=description,
            repository_url=repository_url,
            documentation_url=documentation_url,
            tier=tier,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._owners[service_id] = owner
        logger.info("service_owner_registered", service_id=service_id, team=team_name)
        return owner

    def get_owner(self, service_id: str) -> ServiceOwner | None:
        return self._owners.get(service_id)

    def get_team_services(self, team_id: str) -> list[ServiceOwner]:
        return [o for o in self._owners.values() if o.team.team_id == team_id]

    def find_orphaned_services(self) -> list[ServiceOwner]:
        return [o for o in self._owners.values() if o.status == OwnershipStatus.ORPHANED]

    def get_escalation_path(self, service_id: str) -> list[EscalationContact]:
        owner = self._owners.get(service_id)
        if owner is None:
            return []
        return owner.escalation_contacts

    def update_status(self, service_id: str, status: OwnershipStatus) -> ServiceOwner | None:
        owner = self._owners.get(service_id)
        if owner is None:
            return None
        owner.status = status
        owner.updated_at = time.time()
        return owner

    def list_owners(
        self,
        status: OwnershipStatus | None = None,
        limit: int = 100,
    ) -> list[ServiceOwner]:
        owners = sorted(self._owners.values(), key=lambda o: o.created_at, reverse=True)
        if status:
            owners = [o for o in owners if o.status == status]
        return owners[:limit]

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        teams: set[str] = set()
        for o in self._owners.values():
            by_status[o.status.value] = by_status.get(o.status.value, 0) + 1
            teams.add(o.team.team_id)
        return {
            "total_services": len(self._owners),
            "total_teams": len(teams),
            "by_status": by_status,
        }
