"""Tests for shieldops.audit.config_change_tracker — ConfigChangeTracker."""

from __future__ import annotations

import time

from shieldops.audit.config_change_tracker import (
    ChangeApproval,
    ChangeAuditTrail,
    ChangeImpact,
    ChangeScope,
    ChangeTrackerReport,
    ConfigChange,
    ConfigChangeTracker,
)


def _engine(**kw) -> ConfigChangeTracker:
    return ConfigChangeTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ChangeScope (5)
    def test_scope_application(self):
        assert ChangeScope.APPLICATION == "application"

    def test_scope_infrastructure(self):
        assert ChangeScope.INFRASTRUCTURE == "infrastructure"

    def test_scope_database(self):
        assert ChangeScope.DATABASE == "database"

    def test_scope_network(self):
        assert ChangeScope.NETWORK == "network"

    def test_scope_security(self):
        assert ChangeScope.SECURITY == "security"

    # ChangeApproval (5)
    def test_approval_auto_approved(self):
        assert ChangeApproval.AUTO_APPROVED == "auto_approved"

    def test_approval_peer_reviewed(self):
        assert ChangeApproval.PEER_REVIEWED == "peer_reviewed"

    def test_approval_manager_approved(self):
        assert ChangeApproval.MANAGER_APPROVED == "manager_approved"

    def test_approval_emergency_bypass(self):
        assert ChangeApproval.EMERGENCY_BYPASS == "emergency_bypass"

    def test_approval_pending(self):
        assert ChangeApproval.PENDING == "pending"

    # ChangeImpact (5)
    def test_impact_none(self):
        assert ChangeImpact.NONE == "none"

    def test_impact_low(self):
        assert ChangeImpact.LOW == "low"

    def test_impact_medium(self):
        assert ChangeImpact.MEDIUM == "medium"

    def test_impact_high(self):
        assert ChangeImpact.HIGH == "high"

    def test_impact_critical(self):
        assert ChangeImpact.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_config_change_defaults(self):
        c = ConfigChange()
        assert c.id
        assert c.service_name == ""
        assert c.scope == ChangeScope.APPLICATION
        assert c.key == ""
        assert c.old_value == ""
        assert c.new_value == ""
        assert c.author == ""
        assert c.approval == ChangeApproval.PENDING
        assert c.impact == ChangeImpact.NONE
        assert c.is_rolled_back is False
        assert c.changed_at > 0
        assert c.created_at > 0

    def test_change_audit_trail_defaults(self):
        t = ChangeAuditTrail()
        assert t.id
        assert t.change_id == ""
        assert t.action == ""
        assert t.actor == ""
        assert t.reason == ""
        assert t.performed_at > 0
        assert t.created_at > 0

    def test_change_tracker_report_defaults(self):
        r = ChangeTrackerReport()
        assert r.total_changes == 0
        assert r.total_rollbacks == 0
        assert r.rollback_rate_pct == 0.0
        assert r.by_scope == {}
        assert r.by_approval == {}
        assert r.by_impact == {}
        assert r.high_impact_changes == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_change
# ---------------------------------------------------------------------------


class TestRecordChange:
    def test_basic_record(self):
        eng = _engine()
        change = eng.record_change(
            service_name="api-gateway",
            scope=ChangeScope.APPLICATION,
            key="max_connections",
            old_value="100",
            new_value="200",
            author="alice",
        )
        assert change.service_name == "api-gateway"
        assert change.key == "max_connections"
        assert change.old_value == "100"
        assert change.new_value == "200"
        assert change.author == "alice"

    def test_record_with_impact(self):
        eng = _engine()
        change = eng.record_change(
            service_name="db-primary",
            scope=ChangeScope.DATABASE,
            key="max_pool_size",
            old_value="50",
            new_value="100",
            impact=ChangeImpact.HIGH,
        )
        assert change.impact == ChangeImpact.HIGH
        assert change.scope == ChangeScope.DATABASE

    def test_eviction_at_max(self):
        eng = _engine(max_changes=3)
        for i in range(5):
            eng.record_change(
                service_name=f"svc-{i}",
                scope=ChangeScope.APPLICATION,
                key=f"key-{i}",
                old_value="old",
                new_value="new",
            )
        assert len(eng._items) == 3


# ---------------------------------------------------------------------------
# get_change
# ---------------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        eng = _engine()
        change = eng.record_change(
            service_name="api",
            scope=ChangeScope.APPLICATION,
            key="timeout",
            old_value="30",
            new_value="60",
        )
        result = eng.get_change(change.id)
        assert result is not None
        assert result.key == "timeout"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_change("nonexistent") is None


# ---------------------------------------------------------------------------
# list_changes
# ---------------------------------------------------------------------------


class TestListChanges:
    def test_list_all(self):
        eng = _engine()
        eng.record_change(
            "svc-a",
            ChangeScope.APPLICATION,
            "k1",
            "old",
            "new",
        )
        eng.record_change(
            "svc-b",
            ChangeScope.DATABASE,
            "k2",
            "old",
            "new",
        )
        assert len(eng.list_changes()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_change(
            "svc-a",
            ChangeScope.APPLICATION,
            "k1",
            "old",
            "new",
        )
        eng.record_change(
            "svc-b",
            ChangeScope.APPLICATION,
            "k2",
            "old",
            "new",
        )
        results = eng.list_changes(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_change(
            "svc-a",
            ChangeScope.APPLICATION,
            "k1",
            "old",
            "new",
        )
        eng.record_change(
            "svc-b",
            ChangeScope.SECURITY,
            "k2",
            "old",
            "new",
        )
        results = eng.list_changes(scope=ChangeScope.SECURITY)
        assert len(results) == 1
        assert results[0].scope == ChangeScope.SECURITY

    def test_respects_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_change(
                f"svc-{i}",
                ChangeScope.APPLICATION,
                f"k-{i}",
                "old",
                "new",
            )
        results = eng.list_changes(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# rollback_change
# ---------------------------------------------------------------------------


class TestRollbackChange:
    def test_successful_rollback(self):
        eng = _engine()
        change = eng.record_change(
            "api",
            ChangeScope.APPLICATION,
            "timeout",
            "30",
            "60",
        )
        result = eng.rollback_change(
            change.id,
            "bob",
            "Caused latency",
        )
        assert result is not None
        assert result.is_rolled_back is True

    def test_rollback_creates_audit(self):
        eng = _engine()
        change = eng.record_change(
            "api",
            ChangeScope.APPLICATION,
            "timeout",
            "30",
            "60",
        )
        eng.rollback_change(
            change.id,
            "bob",
            "Reverted",
        )
        assert len(eng._audit_trails) == 1
        trail = eng._audit_trails[0]
        assert trail.action == "rollback"
        assert trail.actor == "bob"

    def test_rollback_not_found(self):
        eng = _engine()
        assert (
            eng.rollback_change(
                "bad-id",
                "bob",
                "reason",
            )
            is None
        )


# ---------------------------------------------------------------------------
# audit_change
# ---------------------------------------------------------------------------


class TestAuditChange:
    def test_create_audit_trail(self):
        eng = _engine()
        change = eng.record_change(
            "api",
            ChangeScope.APPLICATION,
            "key",
            "old",
            "new",
        )
        trail = eng.audit_change(
            change.id,
            "review",
            "carol",
            "Approved",
        )
        assert trail.change_id == change.id
        assert trail.action == "review"
        assert trail.actor == "carol"
        assert trail.reason == "Approved"

    def test_audit_eviction(self):
        eng = _engine(max_changes=2)
        for i in range(5):
            eng.audit_change(
                f"change-{i}",
                "action",
                "actor",
                "reason",
            )
        assert len(eng._audit_trails) == 2


# ---------------------------------------------------------------------------
# calculate_rollback_rate
# ---------------------------------------------------------------------------


class TestCalculateRollbackRate:
    def test_no_changes(self):
        eng = _engine()
        assert eng.calculate_rollback_rate() == 0.0

    def test_with_rollbacks(self):
        eng = _engine()
        c1 = eng.record_change(
            "a",
            ChangeScope.APPLICATION,
            "k1",
            "o",
            "n",
        )
        eng.record_change(
            "b",
            ChangeScope.APPLICATION,
            "k2",
            "o",
            "n",
        )
        eng.rollback_change(c1.id, "bob", "bad")
        rate = eng.calculate_rollback_rate()
        assert rate == 50.0


# ---------------------------------------------------------------------------
# detect_unauthorized_changes
# ---------------------------------------------------------------------------


class TestDetectUnauthorizedChanges:
    def test_finds_pending_and_bypass(self):
        eng = _engine()
        eng.record_change(
            "a",
            ChangeScope.APPLICATION,
            "k1",
            "o",
            "n",
            approval=ChangeApproval.PENDING,
        )
        eng.record_change(
            "b",
            ChangeScope.APPLICATION,
            "k2",
            "o",
            "n",
            approval=ChangeApproval.EMERGENCY_BYPASS,
        )
        eng.record_change(
            "c",
            ChangeScope.APPLICATION,
            "k3",
            "o",
            "n",
            approval=ChangeApproval.PEER_REVIEWED,
        )
        unauthorized = eng.detect_unauthorized_changes()
        assert len(unauthorized) == 2

    def test_none_unauthorized(self):
        eng = _engine()
        eng.record_change(
            "a",
            ChangeScope.APPLICATION,
            "k1",
            "o",
            "n",
            approval=ChangeApproval.PEER_REVIEWED,
        )
        assert len(eng.detect_unauthorized_changes()) == 0


# ---------------------------------------------------------------------------
# find_correlated_changes
# ---------------------------------------------------------------------------


class TestFindCorrelatedChanges:
    def test_finds_clusters(self):
        eng = _engine()
        now = time.time()
        eng.record_change(
            "a",
            ChangeScope.APPLICATION,
            "k1",
            "o",
            "n",
            changed_at=now,
        )
        eng.record_change(
            "b",
            ChangeScope.APPLICATION,
            "k2",
            "o",
            "n",
            changed_at=now + 60,
        )
        eng.record_change(
            "c",
            ChangeScope.APPLICATION,
            "k3",
            "o",
            "n",
            changed_at=now + 7200,
        )
        clusters = eng.find_correlated_changes(
            time_window_minutes=30,
        )
        assert len(clusters) == 1
        assert len(clusters[0]) == 2

    def test_no_clusters(self):
        eng = _engine()
        now = time.time()
        eng.record_change(
            "a",
            ChangeScope.APPLICATION,
            "k1",
            "o",
            "n",
            changed_at=now,
        )
        eng.record_change(
            "b",
            ChangeScope.APPLICATION,
            "k2",
            "o",
            "n",
            changed_at=now + 7200,
        )
        clusters = eng.find_correlated_changes(
            time_window_minutes=30,
        )
        assert len(clusters) == 0


# ---------------------------------------------------------------------------
# generate_tracker_report
# ---------------------------------------------------------------------------


class TestGenerateTrackerReport:
    def test_basic_report(self):
        eng = _engine()
        c1 = eng.record_change(
            "api",
            ChangeScope.APPLICATION,
            "k1",
            "o",
            "n",
            impact=ChangeImpact.HIGH,
        )
        eng.record_change(
            "db",
            ChangeScope.DATABASE,
            "k2",
            "o",
            "n",
            impact=ChangeImpact.LOW,
        )
        eng.rollback_change(c1.id, "bob", "bad")
        report = eng.generate_tracker_report()
        assert report.total_changes == 2
        assert report.total_rollbacks == 1
        assert report.rollback_rate_pct == 50.0
        assert len(report.by_scope) > 0
        assert len(report.by_impact) > 0
        assert len(report.high_impact_changes) == 1
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_tracker_report()
        assert report.total_changes == 0
        assert report.total_rollbacks == 0
        assert report.rollback_rate_pct == 0.0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        c = eng.record_change(
            "api",
            ChangeScope.APPLICATION,
            "k",
            "o",
            "n",
        )
        eng.audit_change(c.id, "review", "alice", "ok")
        assert len(eng._items) == 1
        assert len(eng._audit_trails) == 1
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._audit_trails) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_changes"] == 0
        assert stats["total_audit_trails"] == 0
        assert stats["scope_distribution"] == {}
        assert stats["impact_distribution"] == {}
        assert stats["approval_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        c = eng.record_change(
            "api",
            ChangeScope.APPLICATION,
            "k",
            "o",
            "n",
            impact=ChangeImpact.HIGH,
        )
        eng.audit_change(c.id, "review", "alice", "ok")
        stats = eng.get_stats()
        assert stats["total_changes"] == 1
        assert stats["total_audit_trails"] == 1
        assert stats["max_changes"] == 500000
        assert stats["high_impact_alert_enabled"] is True
