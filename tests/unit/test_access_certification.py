"""Tests for shieldops.compliance.access_certification — AccessCertificationManager."""

from __future__ import annotations

import time

from shieldops.compliance.access_certification import (
    AccessCertificationManager,
    AccessGrant,
    AccessScope,
    CertificationCampaign,
    CertificationDecision,
    CertificationStatus,
    ReviewCycle,
)


def _engine(**kw) -> AccessCertificationManager:
    return AccessCertificationManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_pending(self):
        assert CertificationStatus.PENDING == "pending"

    def test_status_certified(self):
        assert CertificationStatus.CERTIFIED == "certified"

    def test_status_revoked(self):
        assert CertificationStatus.REVOKED == "revoked"

    def test_status_expired(self):
        assert CertificationStatus.EXPIRED == "expired"

    def test_cycle_monthly(self):
        assert ReviewCycle.MONTHLY == "monthly"

    def test_cycle_quarterly(self):
        assert ReviewCycle.QUARTERLY == "quarterly"

    def test_cycle_semi_annual(self):
        assert ReviewCycle.SEMI_ANNUAL == "semi_annual"

    def test_cycle_annual(self):
        assert ReviewCycle.ANNUAL == "annual"

    def test_scope_read_only(self):
        assert AccessScope.READ_ONLY == "read_only"

    def test_scope_operator(self):
        assert AccessScope.OPERATOR == "operator"

    def test_scope_admin(self):
        assert AccessScope.ADMIN == "admin"

    def test_scope_superadmin(self):
        assert AccessScope.SUPERADMIN == "superadmin"

    def test_scope_service_account(self):
        assert AccessScope.SERVICE_ACCOUNT == "service_account"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_grant_defaults(self):
        g = AccessGrant(user="alice", resource="db-prod")
        assert g.id
        assert g.scope == AccessScope.READ_ONLY
        assert g.status == CertificationStatus.PENDING
        assert g.certified_at is None

    def test_campaign_defaults(self):
        c = CertificationCampaign(name="Q1 Review")
        assert c.cycle == ReviewCycle.QUARTERLY
        assert c.total_grants == 0

    def test_decision_defaults(self):
        d = CertificationDecision(grant_id="g-1", decision=CertificationStatus.CERTIFIED)
        assert d.reviewer == ""


# ---------------------------------------------------------------------------
# register_grant
# ---------------------------------------------------------------------------


class TestRegisterGrant:
    def test_basic_register(self):
        eng = _engine()
        grant = eng.register_grant("alice", "db-prod")
        assert grant.user == "alice"
        assert grant.resource == "db-prod"
        assert grant.expires_at is not None

    def test_unique_ids(self):
        eng = _engine()
        g1 = eng.register_grant("alice", "db")
        g2 = eng.register_grant("bob", "db")
        assert g1.id != g2.id

    def test_custom_expiry(self):
        eng = _engine()
        future = time.time() + 86400 * 365
        grant = eng.register_grant("alice", "db", expires_at=future)
        assert grant.expires_at == future

    def test_evicts_at_max(self):
        eng = _engine(max_grants=2)
        g1 = eng.register_grant("u1", "r1")
        eng.register_grant("u2", "r2")
        eng.register_grant("u3", "r3")
        assert eng.get_grant(g1.id) is None


# ---------------------------------------------------------------------------
# list_grants
# ---------------------------------------------------------------------------


class TestListGrants:
    def test_list_all(self):
        eng = _engine()
        eng.register_grant("alice", "db")
        eng.register_grant("bob", "db")
        assert len(eng.list_grants()) == 2

    def test_filter_by_user(self):
        eng = _engine()
        eng.register_grant("alice", "db")
        eng.register_grant("bob", "db")
        results = eng.list_grants(user="alice")
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.register_grant("alice", "db", scope=AccessScope.ADMIN)
        eng.register_grant("bob", "db", scope=AccessScope.READ_ONLY)
        results = eng.list_grants(scope=AccessScope.ADMIN)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# create_campaign
# ---------------------------------------------------------------------------


class TestCreateCampaign:
    def test_basic_campaign(self):
        eng = _engine()
        eng.register_grant("alice", "db")
        eng.register_grant("bob", "db")
        campaign = eng.create_campaign("Q1 Review")
        assert campaign.total_grants == 2

    def test_scope_filter(self):
        eng = _engine()
        eng.register_grant("alice", "db", scope=AccessScope.ADMIN)
        eng.register_grant("bob", "db", scope=AccessScope.READ_ONLY)
        campaign = eng.create_campaign("Admin Review", scope_filter="admin")
        assert campaign.total_grants == 1


# ---------------------------------------------------------------------------
# certify / revoke
# ---------------------------------------------------------------------------


class TestCertifyGrant:
    def test_certify(self):
        eng = _engine()
        grant = eng.register_grant("alice", "db")
        decision = eng.certify_grant(grant.id, reviewer="admin-1")
        assert decision is not None
        assert decision.decision == CertificationStatus.CERTIFIED
        assert eng.get_grant(grant.id).status == CertificationStatus.CERTIFIED

    def test_certify_not_found(self):
        eng = _engine()
        assert eng.certify_grant("nonexistent") is None

    def test_certify_with_campaign(self):
        eng = _engine()
        grant = eng.register_grant("alice", "db")
        campaign = eng.create_campaign("Q1")
        eng.certify_grant(grant.id, campaign_id=campaign.id)
        assert eng.get_campaign(campaign.id).certified_count == 1


class TestRevokeGrant:
    def test_revoke(self):
        eng = _engine()
        grant = eng.register_grant("alice", "db")
        decision = eng.revoke_grant(grant.id, reviewer="admin-1")
        assert decision is not None
        assert decision.decision == CertificationStatus.REVOKED
        assert eng.get_grant(grant.id).status == CertificationStatus.REVOKED

    def test_revoke_not_found(self):
        eng = _engine()
        assert eng.revoke_grant("nonexistent") is None

    def test_revoke_with_campaign(self):
        eng = _engine()
        grant = eng.register_grant("alice", "db")
        campaign = eng.create_campaign("Q1")
        eng.revoke_grant(grant.id, campaign_id=campaign.id)
        assert eng.get_campaign(campaign.id).revoked_count == 1


# ---------------------------------------------------------------------------
# campaigns / expired / stats
# ---------------------------------------------------------------------------


class TestCampaigns:
    def test_get_campaign(self):
        eng = _engine()
        campaign = eng.create_campaign("Q1")
        assert eng.get_campaign(campaign.id) is not None

    def test_get_campaign_not_found(self):
        eng = _engine()
        assert eng.get_campaign("nonexistent") is None

    def test_list_campaigns(self):
        eng = _engine()
        eng.create_campaign("Q1", cycle=ReviewCycle.QUARTERLY)
        eng.create_campaign("Annual", cycle=ReviewCycle.ANNUAL)
        assert len(eng.list_campaigns()) == 2

    def test_filter_campaigns_by_cycle(self):
        eng = _engine()
        eng.create_campaign("Q1", cycle=ReviewCycle.QUARTERLY)
        eng.create_campaign("Annual", cycle=ReviewCycle.ANNUAL)
        results = eng.list_campaigns(cycle=ReviewCycle.QUARTERLY)
        assert len(results) == 1


class TestExpiredGrants:
    def test_expired(self):
        eng = _engine()
        grant = eng.register_grant("alice", "db")
        grant.expires_at = time.time() - 3600
        expired = eng.get_expired_grants()
        assert len(expired) == 1
        assert expired[0].status == CertificationStatus.EXPIRED

    def test_none_expired(self):
        eng = _engine()
        eng.register_grant("alice", "db")
        expired = eng.get_expired_grants()
        assert len(expired) == 0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_grants"] == 0

    def test_populated_stats(self):
        eng = _engine()
        g = eng.register_grant("alice", "db", scope=AccessScope.ADMIN)
        eng.certify_grant(g.id, reviewer="admin")
        stats = eng.get_stats()
        assert stats["total_grants"] == 1
        assert stats["total_decisions"] == 1
        assert stats["scope_distribution"][AccessScope.ADMIN] == 1
