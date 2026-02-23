"""Access Certification Manager — periodic access reviews, grant recertification, revocation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CertificationStatus(StrEnum):
    PENDING = "pending"
    CERTIFIED = "certified"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ReviewCycle(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class AccessScope(StrEnum):
    READ_ONLY = "read_only"
    OPERATOR = "operator"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
    SERVICE_ACCOUNT = "service_account"


# --- Models ---


class AccessGrant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user: str
    resource: str
    scope: AccessScope = AccessScope.READ_ONLY
    status: CertificationStatus = CertificationStatus.PENDING
    granted_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    certified_at: float | None = None
    certified_by: str = ""


class CertificationCampaign(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    cycle: ReviewCycle = ReviewCycle.QUARTERLY
    scope_filter: str = ""
    total_grants: int = 0
    certified_count: int = 0
    revoked_count: int = 0
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


class CertificationDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    grant_id: str
    campaign_id: str = ""
    decision: CertificationStatus
    reviewer: str = ""
    comment: str = ""
    decided_at: float = Field(default_factory=time.time)


# --- Engine ---


class AccessCertificationManager:
    """Periodic access reviews, grant recertification, revocation, SOC2/SOX compliance."""

    def __init__(
        self,
        max_grants: int = 50000,
        default_expiry_days: int = 90,
    ) -> None:
        self._max_grants = max_grants
        self._default_expiry_days = default_expiry_days
        self._grants: dict[str, AccessGrant] = {}
        self._campaigns: dict[str, CertificationCampaign] = {}
        self._decisions: list[CertificationDecision] = []
        logger.info(
            "access_certification.initialized",
            max_grants=max_grants,
            default_expiry_days=default_expiry_days,
        )

    def register_grant(
        self,
        user: str,
        resource: str,
        scope: AccessScope = AccessScope.READ_ONLY,
        expires_at: float | None = None,
    ) -> AccessGrant:
        if expires_at is None:
            expires_at = time.time() + (self._default_expiry_days * 86400)
        grant = AccessGrant(
            user=user,
            resource=resource,
            scope=scope,
            expires_at=expires_at,
        )
        self._grants[grant.id] = grant
        if len(self._grants) > self._max_grants:
            oldest = next(iter(self._grants))
            del self._grants[oldest]
        logger.info(
            "access_certification.grant_registered",
            grant_id=grant.id,
            user=user,
            resource=resource,
        )
        return grant

    def get_grant(self, grant_id: str) -> AccessGrant | None:
        return self._grants.get(grant_id)

    def list_grants(
        self,
        user: str | None = None,
        resource: str | None = None,
        status: CertificationStatus | None = None,
        scope: AccessScope | None = None,
    ) -> list[AccessGrant]:
        results = list(self._grants.values())
        if user is not None:
            results = [g for g in results if g.user == user]
        if resource is not None:
            results = [g for g in results if g.resource == resource]
        if status is not None:
            results = [g for g in results if g.status == status]
        if scope is not None:
            results = [g for g in results if g.scope == scope]
        return results

    def create_campaign(
        self,
        name: str,
        cycle: ReviewCycle = ReviewCycle.QUARTERLY,
        scope_filter: str = "",
    ) -> CertificationCampaign:
        grants = list(self._grants.values())
        if scope_filter:
            grants = [g for g in grants if g.scope == scope_filter]
        campaign = CertificationCampaign(
            name=name,
            cycle=cycle,
            scope_filter=scope_filter,
            total_grants=len(grants),
        )
        self._campaigns[campaign.id] = campaign
        logger.info(
            "access_certification.campaign_created",
            campaign_id=campaign.id,
            name=name,
            total_grants=len(grants),
        )
        return campaign

    def certify_grant(
        self,
        grant_id: str,
        reviewer: str = "",
        campaign_id: str = "",
        comment: str = "",
    ) -> CertificationDecision | None:
        grant = self._grants.get(grant_id)
        if grant is None:
            return None
        grant.status = CertificationStatus.CERTIFIED
        grant.certified_at = time.time()
        grant.certified_by = reviewer
        grant.expires_at = time.time() + (self._default_expiry_days * 86400)
        decision = CertificationDecision(
            grant_id=grant_id,
            campaign_id=campaign_id,
            decision=CertificationStatus.CERTIFIED,
            reviewer=reviewer,
            comment=comment,
        )
        self._decisions.append(decision)
        if campaign_id and campaign_id in self._campaigns:
            self._campaigns[campaign_id].certified_count += 1
        logger.info(
            "access_certification.grant_certified",
            grant_id=grant_id,
            reviewer=reviewer,
        )
        return decision

    def revoke_grant(
        self,
        grant_id: str,
        reviewer: str = "",
        campaign_id: str = "",
        comment: str = "",
    ) -> CertificationDecision | None:
        grant = self._grants.get(grant_id)
        if grant is None:
            return None
        grant.status = CertificationStatus.REVOKED
        decision = CertificationDecision(
            grant_id=grant_id,
            campaign_id=campaign_id,
            decision=CertificationStatus.REVOKED,
            reviewer=reviewer,
            comment=comment,
        )
        self._decisions.append(decision)
        if campaign_id and campaign_id in self._campaigns:
            self._campaigns[campaign_id].revoked_count += 1
        logger.info(
            "access_certification.grant_revoked",
            grant_id=grant_id,
            reviewer=reviewer,
        )
        return decision

    def get_campaign(self, campaign_id: str) -> CertificationCampaign | None:
        return self._campaigns.get(campaign_id)

    def list_campaigns(
        self,
        cycle: ReviewCycle | None = None,
    ) -> list[CertificationCampaign]:
        results = list(self._campaigns.values())
        if cycle is not None:
            results = [c for c in results if c.cycle == cycle]
        return results

    def get_expired_grants(self) -> list[AccessGrant]:
        now = time.time()
        expired: list[AccessGrant] = []
        for grant in self._grants.values():
            if (
                grant.expires_at is not None
                and grant.expires_at < now
                and grant.status != CertificationStatus.REVOKED
            ):
                grant.status = CertificationStatus.EXPIRED
                expired.append(grant)
        return expired

    def get_stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        scope_counts: dict[str, int] = {}
        for g in self._grants.values():
            status_counts[g.status] = status_counts.get(g.status, 0) + 1
            scope_counts[g.scope] = scope_counts.get(g.scope, 0) + 1
        return {
            "total_grants": len(self._grants),
            "total_campaigns": len(self._campaigns),
            "total_decisions": len(self._decisions),
            "status_distribution": status_counts,
            "scope_distribution": scope_counts,
        }
