"""Tests for shieldops.audit.config_audit — ConfigurationAuditTrail.

Covers:
- ConfigScope, ChangeAction, ApprovalStatus enums
- ConfigEntry, ConfigDiff model defaults
- record_change (basic create, update, versioning, trims at max)
- get_current (found, not found)
- get_history (basic, empty)
- get_diff (basic, not found)
- restore_version (basic, not found)
- blame (basic, empty)
- search (basic, no results)
- list_recent_changes (basic)
- delete_key (basic, not found)
- get_stats (empty, populated)
- Multiple versions (three versions, diff across)
"""

from __future__ import annotations

from shieldops.audit.config_audit import (
    ApprovalStatus,
    ChangeAction,
    ConfigDiff,
    ConfigEntry,
    ConfigScope,
    ConfigurationAuditTrail,
)


def _trail(**kw) -> ConfigurationAuditTrail:
    return ConfigurationAuditTrail(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ConfigScope (4 values)

    def test_scope_service(self):
        assert ConfigScope.SERVICE == "service"

    def test_scope_environment(self):
        assert ConfigScope.ENVIRONMENT == "environment"

    def test_scope_global(self):
        assert ConfigScope.GLOBAL == "global"

    def test_scope_namespace(self):
        assert ConfigScope.NAMESPACE == "namespace"

    # ChangeAction (4 values)

    def test_action_create(self):
        assert ChangeAction.CREATE == "create"

    def test_action_update(self):
        assert ChangeAction.UPDATE == "update"

    def test_action_delete(self):
        assert ChangeAction.DELETE == "delete"

    def test_action_restore(self):
        assert ChangeAction.RESTORE == "restore"

    # ApprovalStatus (4 values)

    def test_approval_pending(self):
        assert ApprovalStatus.PENDING == "pending"

    def test_approval_approved(self):
        assert ApprovalStatus.APPROVED == "approved"

    def test_approval_rejected(self):
        assert ApprovalStatus.REJECTED == "rejected"

    def test_approval_auto_approved(self):
        assert ApprovalStatus.AUTO_APPROVED == "auto_approved"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_config_entry_defaults(self):
        entry = ConfigEntry(config_key="db.host")
        assert entry.id
        assert entry.config_key == "db.host"
        assert entry.value == ""
        assert entry.previous_value == ""
        assert entry.scope == ConfigScope.SERVICE
        assert entry.action == ChangeAction.CREATE
        assert entry.approval_status == ApprovalStatus.AUTO_APPROVED
        assert entry.changed_by == ""
        assert entry.reason == ""
        assert entry.version == 1
        assert entry.created_at > 0

    def test_config_diff_defaults(self):
        diff = ConfigDiff(config_key="db.host", from_version=1, to_version=2)
        assert diff.config_key == "db.host"
        assert diff.from_version == 1
        assert diff.to_version == 2
        assert diff.from_value == ""
        assert diff.to_value == ""
        assert diff.changed_by == ""


# ---------------------------------------------------------------------------
# record_change
# ---------------------------------------------------------------------------


class TestRecordChange:
    def test_basic_create(self):
        t = _trail()
        entry = t.record_change("db.host", "localhost", changed_by="admin")
        assert entry.config_key == "db.host"
        assert entry.value == "localhost"
        assert entry.action == ChangeAction.CREATE
        assert entry.version == 1
        assert entry.changed_by == "admin"

    def test_update_action(self):
        t = _trail()
        t.record_change("db.host", "localhost")
        entry = t.record_change("db.host", "prod-db.internal")
        assert entry.action == ChangeAction.UPDATE
        assert entry.previous_value == "localhost"

    def test_versioning(self):
        t = _trail()
        e1 = t.record_change("db.host", "v1")
        e2 = t.record_change("db.host", "v2")
        e3 = t.record_change("db.host", "v3")
        assert e1.version == 1
        assert e2.version == 2
        assert e3.version == 3

    def test_trims_at_max(self):
        t = _trail(max_entries=3)
        t.record_change("k1", "v1")
        t.record_change("k2", "v2")
        t.record_change("k3", "v3")
        t.record_change("k4", "v4")
        recent = t.list_recent_changes(limit=100)
        assert len(recent) == 3


# ---------------------------------------------------------------------------
# get_current
# ---------------------------------------------------------------------------


class TestGetCurrent:
    def test_found(self):
        t = _trail()
        t.record_change("db.host", "v1")
        t.record_change("db.host", "v2")
        current = t.get_current("db.host")
        assert current is not None
        assert current.value == "v2"
        assert current.version == 2

    def test_not_found(self):
        t = _trail()
        assert t.get_current("nonexistent") is None


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    def test_basic(self):
        t = _trail()
        t.record_change("db.host", "v1")
        t.record_change("db.host", "v2")
        t.record_change("db.host", "v3")
        history = t.get_history("db.host")
        assert len(history) == 3
        assert history[0].version == 1
        assert history[2].version == 3

    def test_empty(self):
        t = _trail()
        assert t.get_history("nonexistent") == []


# ---------------------------------------------------------------------------
# get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    def test_basic(self):
        t = _trail()
        t.record_change("db.host", "localhost")
        t.record_change("db.host", "prod-db.internal")
        diff = t.get_diff("db.host", 1, 2)
        assert diff is not None
        assert diff.from_value == "localhost"
        assert diff.to_value == "prod-db.internal"
        assert diff.from_version == 1
        assert diff.to_version == 2

    def test_not_found(self):
        t = _trail()
        assert t.get_diff("db.host", 1, 2) is None


# ---------------------------------------------------------------------------
# restore_version
# ---------------------------------------------------------------------------


class TestRestoreVersion:
    def test_basic(self):
        t = _trail()
        t.record_change("db.host", "original", changed_by="dev")
        t.record_change("db.host", "changed", changed_by="dev")
        restored = t.restore_version("db.host", 1, restored_by="admin")
        assert restored is not None
        assert restored.value == "original"
        assert restored.version == 3
        assert "Restored from version 1" in restored.reason

    def test_not_found(self):
        t = _trail()
        assert t.restore_version("nonexistent", 1) is None


# ---------------------------------------------------------------------------
# blame
# ---------------------------------------------------------------------------


class TestBlame:
    def test_basic(self):
        t = _trail()
        t.record_change("db.host", "v1", changed_by="alice")
        t.record_change("db.host", "v2", changed_by="bob")
        blame = t.blame("db.host")
        assert len(blame) == 2
        assert blame[0]["changed_by"] == "alice"
        assert blame[0]["version"] == 1
        assert blame[1]["changed_by"] == "bob"
        assert blame[1]["version"] == 2

    def test_empty(self):
        t = _trail()
        assert t.blame("nonexistent") == []


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_basic(self):
        t = _trail()
        t.record_change("db.host", "localhost")
        t.record_change("db.port", "5432")
        t.record_change("cache.host", "redis")
        results = t.search("db")
        assert len(results) == 2
        keys = {r.config_key for r in results}
        assert keys == {"db.host", "db.port"}

    def test_no_results(self):
        t = _trail()
        t.record_change("db.host", "localhost")
        assert t.search("nonexistent") == []


# ---------------------------------------------------------------------------
# list_recent_changes
# ---------------------------------------------------------------------------


class TestListRecentChanges:
    def test_basic(self):
        t = _trail()
        t.record_change("k1", "v1")
        t.record_change("k2", "v2")
        t.record_change("k3", "v3")
        recent = t.list_recent_changes(limit=2)
        assert len(recent) == 2
        # Most recent first
        assert recent[0].config_key == "k3"


# ---------------------------------------------------------------------------
# delete_key
# ---------------------------------------------------------------------------


class TestDeleteKey:
    def test_basic(self):
        t = _trail()
        t.record_change("db.host", "localhost")
        assert t.delete_key("db.host", deleted_by="admin") is True
        current = t.get_current("db.host")
        assert current is not None
        assert current.action == ChangeAction.DELETE
        assert current.value == ""

    def test_not_found(self):
        t = _trail()
        assert t.delete_key("nonexistent") is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        t = _trail()
        stats = t.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_keys"] == 0
        assert stats["scope_distribution"] == {}
        assert stats["action_distribution"] == {}

    def test_populated(self):
        t = _trail()
        t.record_change("db.host", "v1", scope=ConfigScope.SERVICE)
        t.record_change("db.host", "v2", scope=ConfigScope.SERVICE)
        t.record_change("cache.host", "redis", scope=ConfigScope.GLOBAL)
        stats = t.get_stats()
        assert stats["total_entries"] == 3
        assert stats["total_keys"] == 2
        assert ConfigScope.SERVICE in stats["scope_distribution"]
        assert ConfigScope.GLOBAL in stats["scope_distribution"]
        assert ChangeAction.CREATE in stats["action_distribution"]


# ---------------------------------------------------------------------------
# Multiple versions
# ---------------------------------------------------------------------------


class TestMultipleVersions:
    def test_three_versions(self):
        t = _trail()
        t.record_change("db.host", "alpha")
        t.record_change("db.host", "beta")
        t.record_change("db.host", "gamma")
        history = t.get_history("db.host")
        assert len(history) == 3
        assert history[0].value == "alpha"
        assert history[1].value == "beta"
        assert history[2].value == "gamma"
        assert history[1].previous_value == "alpha"
        assert history[2].previous_value == "beta"

    def test_diff_across_versions(self):
        t = _trail()
        t.record_change("db.host", "alpha")
        t.record_change("db.host", "beta")
        t.record_change("db.host", "gamma")
        diff = t.get_diff("db.host", 1, 3)
        assert diff is not None
        assert diff.from_value == "alpha"
        assert diff.to_value == "gamma"

    def test_version_trim_per_key(self):
        t = _trail(max_versions_per_key=2)
        t.record_change("db.host", "v1")
        t.record_change("db.host", "v2")
        t.record_change("db.host", "v3")
        history = t.get_history("db.host")
        assert len(history) == 2
        # Oldest trimmed, keep last 2
        assert history[0].value == "v2"
        assert history[1].value == "v3"
