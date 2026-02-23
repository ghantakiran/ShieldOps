"""Tests for shieldops.policy.approval.approval_delegation — ApprovalDelegationEngine."""

from __future__ import annotations

import time

from shieldops.policy.approval.approval_delegation import (
    ApprovalDelegationEngine,
    DelegationAudit,
    DelegationReason,
    DelegationRule,
    DelegationStatus,
)


def _engine(**kw) -> ApprovalDelegationEngine:
    return ApprovalDelegationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # DelegationReason (5 values)

    def test_delegation_reason_vacation(self):
        assert DelegationReason.VACATION == "vacation"

    def test_delegation_reason_expertise(self):
        assert DelegationReason.EXPERTISE == "expertise"

    def test_delegation_reason_workload(self):
        assert DelegationReason.WORKLOAD == "workload"

    def test_delegation_reason_escalation(self):
        assert DelegationReason.ESCALATION == "escalation"

    def test_delegation_reason_scheduled(self):
        assert DelegationReason.SCHEDULED == "scheduled"

    # DelegationStatus (3 values)

    def test_delegation_status_active(self):
        assert DelegationStatus.ACTIVE == "active"

    def test_delegation_status_expired(self):
        assert DelegationStatus.EXPIRED == "expired"

    def test_delegation_status_revoked(self):
        assert DelegationStatus.REVOKED == "revoked"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_delegation_rule_defaults(self):
        rule = DelegationRule(
            delegator="alice",
            delegate="bob",
            reason=DelegationReason.VACATION,
        )
        assert rule.id
        assert rule.delegator == "alice"
        assert rule.delegate == "bob"
        assert rule.scope == []
        assert rule.status == DelegationStatus.ACTIVE
        assert rule.starts_at > 0
        assert rule.created_at > 0

    def test_delegation_audit_defaults(self):
        audit = DelegationAudit(
            rule_id="r1",
            action="delegation_used",
            original_approver="alice",
            delegated_to="bob",
        )
        assert audit.id
        assert audit.resource_id == ""
        assert audit.timestamp > 0


# ---------------------------------------------------------------------------
# create_delegation
# ---------------------------------------------------------------------------


class TestCreateDelegation:
    def test_basic_create(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        assert rule.delegator == "alice"
        assert rule.delegate == "bob"
        assert rule.reason == DelegationReason.VACATION
        assert rule.status == DelegationStatus.ACTIVE

    def test_create_with_scope(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.EXPERTISE,
            scope=["infra", "security"],
        )
        assert rule.scope == ["infra", "security"]

    def test_evicts_at_max_rules(self):
        eng = _engine(max_rules=2)
        r1 = eng.create_delegation(
            "a",
            "b",
            DelegationReason.VACATION,
        )
        eng.create_delegation(
            "c",
            "d",
            DelegationReason.WORKLOAD,
        )
        eng.create_delegation(
            "e",
            "f",
            DelegationReason.ESCALATION,
        )
        rules = eng.list_rules()
        assert len(rules) == 2
        ids = {r.id for r in rules}
        assert r1.id not in ids

    def test_accepts_string_reason(self):
        eng = _engine()
        rule = eng.create_delegation("alice", "bob", "workload")
        assert rule.reason == DelegationReason.WORKLOAD

    def test_custom_expires_at(self):
        eng = _engine()
        future = time.time() + 86400
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.SCHEDULED,
            expires_at=future,
        )
        assert rule.expires_at == future


# ---------------------------------------------------------------------------
# find_delegate
# ---------------------------------------------------------------------------


class TestFindDelegate:
    def test_finds_matching_delegate(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        delegate = eng.find_delegate("alice")
        assert delegate == "bob"

    def test_returns_none_if_no_match(self):
        eng = _engine()
        assert eng.find_delegate("alice") is None

    def test_respects_scope_matching(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.EXPERTISE,
            scope=["infra"],
        )
        assert eng.find_delegate("alice", scope_item="infra") == "bob"
        assert eng.find_delegate("alice", scope_item="security") is None

    def test_ignores_revoked_rules(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        eng.revoke_delegation(rule.id)
        assert eng.find_delegate("alice") is None

    def test_ignores_expired_rules(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
            expires_at=time.time() - 100,
        )
        assert eng.find_delegate("alice") is None

    def test_matches_when_scope_present_but_no_scope_item(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.EXPERTISE,
            scope=["infra"],
        )
        # Rule has scope but caller doesn't specify scope_item -> match
        assert eng.find_delegate("alice") == "bob"


# ---------------------------------------------------------------------------
# record_delegation_use
# ---------------------------------------------------------------------------


class TestRecordDelegationUse:
    def test_creates_audit_entry(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        audit = eng.record_delegation_use(
            rule.id,
            resource_id="PR-123",
        )
        assert audit.rule_id == rule.id
        assert audit.original_approver == "alice"
        assert audit.delegated_to == "bob"
        assert audit.resource_id == "PR-123"
        assert audit.action == "delegation_used"

    def test_trims_to_max_audit(self):
        eng = _engine(max_audit=3)
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        for i in range(5):
            eng.record_delegation_use(rule.id, resource_id=f"r{i}")
        log = eng.get_audit_log(limit=100)
        assert len(log) == 3

    def test_audit_for_unknown_rule(self):
        eng = _engine()
        audit = eng.record_delegation_use("unknown-id")
        assert audit.original_approver == "unknown"
        assert audit.delegated_to == "unknown"


# ---------------------------------------------------------------------------
# revoke_delegation
# ---------------------------------------------------------------------------


class TestRevokeDelegation:
    def test_revokes_rule(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        revoked = eng.revoke_delegation(rule.id)
        assert revoked is not None
        assert revoked.status == DelegationStatus.REVOKED

    def test_returns_none_for_unknown(self):
        eng = _engine()
        assert eng.revoke_delegation("nope") is None


# ---------------------------------------------------------------------------
# get_active_delegations
# ---------------------------------------------------------------------------


class TestGetActiveDelegations:
    def test_returns_active_only(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        r2 = eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
        )
        eng.revoke_delegation(r2.id)
        active = eng.get_active_delegations()
        assert len(active) == 1
        assert active[0].delegator == "alice"

    def test_filter_by_user_delegator(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
        )
        active = eng.get_active_delegations(user="alice")
        assert len(active) == 1
        assert active[0].delegator == "alice"

    def test_filter_by_user_delegate(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        active = eng.get_active_delegations(user="bob")
        assert len(active) == 1
        assert active[0].delegate == "bob"


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_filter_by_delegator(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
        )
        results = eng.list_rules(delegator="alice")
        assert len(results) == 1
        assert results[0].delegator == "alice"

    def test_filter_by_delegate(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
        )
        results = eng.list_rules(delegate="dave")
        assert len(results) == 1
        assert results[0].delegate == "dave"

    def test_list_all(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
        )
        assert len(eng.list_rules()) == 2


# ---------------------------------------------------------------------------
# get_audit_log
# ---------------------------------------------------------------------------


class TestGetAuditLog:
    def test_filter_by_rule_id(self):
        eng = _engine()
        r1 = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        r2 = eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
        )
        eng.record_delegation_use(r1.id, resource_id="a1")
        eng.record_delegation_use(r2.id, resource_id="a2")
        log = eng.get_audit_log(rule_id=r1.id)
        assert len(log) == 1
        assert log[0].rule_id == r1.id

    def test_respects_limit(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        for i in range(10):
            eng.record_delegation_use(rule.id, resource_id=f"r{i}")
        log = eng.get_audit_log(limit=3)
        assert len(log) == 3


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------


class TestCleanupExpired:
    def test_marks_expired_rules(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
            expires_at=time.time() - 100,
        )
        eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
            expires_at=time.time() + 86400,
        )
        count = eng.cleanup_expired()
        assert count == 1

    def test_skips_already_expired(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
            expires_at=time.time() - 100,
        )
        # Manually set status to expired before cleanup
        rule.status = DelegationStatus.EXPIRED
        count = eng.cleanup_expired()
        assert count == 0

    def test_skips_revoked(self):
        eng = _engine()
        rule = eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
            expires_at=time.time() - 100,
        )
        eng.revoke_delegation(rule.id)
        count = eng.cleanup_expired()
        assert count == 0

    def test_no_rules_returns_zero(self):
        eng = _engine()
        assert eng.cleanup_expired() == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_rules"] == 0
        assert stats["active_rules"] == 0
        assert stats["total_audit_entries"] == 0
        assert stats["status_distribution"] == {}
        assert stats["reason_distribution"] == {}

    def test_populated_stats(self):
        eng = _engine()
        eng.create_delegation(
            "alice",
            "bob",
            DelegationReason.VACATION,
        )
        r2 = eng.create_delegation(
            "carol",
            "dave",
            DelegationReason.WORKLOAD,
        )
        eng.revoke_delegation(r2.id)
        eng.record_delegation_use(r2.id)
        stats = eng.get_stats()
        assert stats["total_rules"] == 2
        assert stats["active_rules"] == 1
        assert stats["total_audit_entries"] == 1
        status_dist = stats["status_distribution"]
        assert status_dist[DelegationStatus.ACTIVE] == 1
        assert status_dist[DelegationStatus.REVOKED] == 1
        reason_dist = stats["reason_distribution"]
        assert reason_dist[DelegationReason.VACATION] == 1
        assert reason_dist[DelegationReason.WORKLOAD] == 1
