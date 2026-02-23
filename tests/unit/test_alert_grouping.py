"""Tests for shieldops.observability.alert_grouping -- AlertGroupingEngine."""

from __future__ import annotations

import time

import pytest

from shieldops.observability.alert_grouping import (
    AlertFingerprint,
    AlertGroup,
    AlertGroupingEngine,
    GroupingRule,
    GroupingStrategy,
    GroupStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kwargs) -> AlertGroupingEngine:
    return AlertGroupingEngine(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_group_status_open(self):
        assert GroupStatus.OPEN == "open"

    def test_group_status_merged(self):
        assert GroupStatus.MERGED == "merged"

    def test_group_status_resolved(self):
        assert GroupStatus.RESOLVED == "resolved"

    def test_grouping_strategy_fingerprint(self):
        assert GroupingStrategy.FINGERPRINT == "fingerprint"

    def test_grouping_strategy_time_window(self):
        assert GroupingStrategy.TIME_WINDOW == "time_window"

    def test_grouping_strategy_service_affinity(self):
        assert GroupingStrategy.SERVICE_AFFINITY == "service_affinity"

    def test_grouping_strategy_label_match(self):
        assert GroupingStrategy.LABEL_MATCH == "label_match"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_alert_fingerprint_defaults(self):
        fp = AlertFingerprint(alert_name="cpu_high", fingerprint="abc123")
        assert fp.id
        assert fp.service == ""
        assert fp.labels == {}
        assert fp.received_at > 0

    def test_alert_group_defaults(self):
        g = AlertGroup(strategy=GroupingStrategy.FINGERPRINT)
        assert g.id
        assert g.name == ""
        assert g.fingerprint == ""
        assert g.alerts == []
        assert g.status == GroupStatus.OPEN
        assert g.service == ""
        assert g.resolved_at is None
        assert g.metadata == {}
        assert g.created_at > 0

    def test_grouping_rule_defaults(self):
        r = GroupingRule(name="by-service", strategy=GroupingStrategy.SERVICE_AFFINITY)
        assert r.id
        assert r.match_labels == {}
        assert r.service_pattern == ""
        assert r.window_seconds == 300
        assert r.priority == 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# Ingest alert
# ---------------------------------------------------------------------------


class TestIngestAlert:
    def test_creates_new_group(self):
        e = _engine()
        result = e.ingest_alert(alert_name="cpu_high", service="api")
        assert result["alert_id"]
        assert result["group_id"]
        assert result["new_group"] is True

    def test_same_fingerprint_joins_existing(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high", service="api")
        r2 = e.ingest_alert(alert_name="cpu_high", service="api")
        assert r2["new_group"] is False
        assert r2["group_id"] == r1["group_id"]

    def test_different_fingerprint_creates_new_group(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high", service="api")
        r2 = e.ingest_alert(alert_name="mem_high", service="web")
        assert r2["new_group"] is True
        assert r2["group_id"] != r1["group_id"]

    def test_different_labels_different_fingerprint(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high", labels={"env": "prod"})
        r2 = e.ingest_alert(alert_name="cpu_high", labels={"env": "staging"})
        assert r2["new_group"] is True
        assert r2["group_id"] != r1["group_id"]

    def test_group_contains_alert_ids(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high", service="api")
        r2 = e.ingest_alert(alert_name="cpu_high", service="api")
        group = e.get_group(r1["group_id"])
        assert group is not None
        assert r1["alert_id"] in group.alerts
        assert r2["alert_id"] in group.alerts

    def test_ingest_with_labels(self):
        e = _engine()
        result = e.ingest_alert(
            alert_name="disk_full", service="storage", labels={"region": "us-east"}
        )
        assert result["alert_id"]
        assert result["new_group"] is True

    def test_ingest_sets_group_name(self):
        e = _engine()
        result = e.ingest_alert(alert_name="cpu_high")
        group = e.get_group(result["group_id"])
        assert group is not None
        assert "cpu_high" in group.name

    def test_ingest_sets_group_service(self):
        e = _engine()
        result = e.ingest_alert(alert_name="cpu_high", service="api")
        group = e.get_group(result["group_id"])
        assert group is not None
        assert group.service == "api"

    def test_ingest_max_groups_limit(self):
        e = _engine(max_groups=2)
        e.ingest_alert(alert_name="alert1", service="svc1")
        e.ingest_alert(alert_name="alert2", service="svc2")
        with pytest.raises(ValueError, match="Maximum groups limit"):
            e.ingest_alert(alert_name="alert3", service="svc3")

    def test_same_alert_outside_window_creates_new_group(self):
        e = _engine(window_seconds=1)
        r1 = e.ingest_alert(alert_name="cpu_high", service="api")
        # Manually age the group
        group = e.get_group(r1["group_id"])
        assert group is not None
        group.created_at = time.time() - 10
        r2 = e.ingest_alert(alert_name="cpu_high", service="api")
        assert r2["new_group"] is True
        assert r2["group_id"] != r1["group_id"]


# ---------------------------------------------------------------------------
# Create rule
# ---------------------------------------------------------------------------


class TestCreateRule:
    def test_create_basic(self):
        e = _engine()
        rule = e.create_rule(name="by-fingerprint", strategy=GroupingStrategy.FINGERPRINT)
        assert rule.name == "by-fingerprint"
        assert rule.strategy == GroupingStrategy.FINGERPRINT
        assert rule.id

    def test_create_with_all_fields(self):
        e = _engine()
        rule = e.create_rule(
            name="service-rule",
            strategy=GroupingStrategy.SERVICE_AFFINITY,
            match_labels={"team": "platform"},
            service_pattern="api-*",
            window_seconds=600,
            priority=10,
        )
        assert rule.match_labels["team"] == "platform"
        assert rule.service_pattern == "api-*"
        assert rule.window_seconds == 600
        assert rule.priority == 10

    def test_create_multiple_rules(self):
        e = _engine()
        e.create_rule(name="r1", strategy=GroupingStrategy.FINGERPRINT)
        e.create_rule(name="r2", strategy=GroupingStrategy.LABEL_MATCH)
        assert len(e.list_rules()) == 2


# ---------------------------------------------------------------------------
# Get group
# ---------------------------------------------------------------------------


class TestGetGroup:
    def test_found(self):
        e = _engine()
        result = e.ingest_alert(alert_name="cpu_high")
        group = e.get_group(result["group_id"])
        assert group is not None
        assert group.id == result["group_id"]

    def test_not_found(self):
        e = _engine()
        assert e.get_group("nonexistent") is None


# ---------------------------------------------------------------------------
# List groups
# ---------------------------------------------------------------------------


class TestListGroups:
    def test_list_all(self):
        e = _engine()
        e.ingest_alert(alert_name="cpu_high", service="api")
        e.ingest_alert(alert_name="mem_high", service="web")
        groups = e.list_groups()
        assert len(groups) == 2

    def test_filter_by_status_open(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high")
        e.ingest_alert(alert_name="mem_high")
        e.resolve_group(r1["group_id"])
        open_groups = e.list_groups(status=GroupStatus.OPEN)
        assert len(open_groups) == 1

    def test_filter_by_status_resolved(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high")
        e.ingest_alert(alert_name="mem_high")
        e.resolve_group(r1["group_id"])
        resolved = e.list_groups(status=GroupStatus.RESOLVED)
        assert len(resolved) == 1

    def test_list_empty(self):
        e = _engine()
        assert len(e.list_groups()) == 0


# ---------------------------------------------------------------------------
# Merge groups
# ---------------------------------------------------------------------------


class TestMergeGroups:
    def test_merge_success(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high", service="api")
        r2 = e.ingest_alert(alert_name="mem_high", service="api")
        primary = e.merge_groups([r1["group_id"], r2["group_id"]])
        assert primary is not None
        assert r1["alert_id"] in primary.alerts
        assert r2["alert_id"] in primary.alerts

    def test_merge_secondary_marked_merged(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high", service="api")
        r2 = e.ingest_alert(alert_name="mem_high", service="api")
        e.merge_groups([r1["group_id"], r2["group_id"]])
        secondary = e.get_group(r2["group_id"])
        assert secondary is not None
        assert secondary.status == GroupStatus.MERGED
        assert secondary.metadata["merged_into"] == r1["group_id"]

    def test_merge_less_than_2_raises(self):
        e = _engine()
        with pytest.raises(ValueError, match="At least 2 group IDs"):
            e.merge_groups(["single-id"])

    def test_merge_empty_list_raises(self):
        e = _engine()
        with pytest.raises(ValueError, match="At least 2 group IDs"):
            e.merge_groups([])

    def test_merge_with_nonexistent_ids(self):
        e = _engine()
        result = e.merge_groups(["nonexistent1", "nonexistent2"])
        assert result is None

    def test_merge_three_groups(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="a1", service="svc1")
        r2 = e.ingest_alert(alert_name="a2", service="svc2")
        r3 = e.ingest_alert(alert_name="a3", service="svc3")
        primary = e.merge_groups([r1["group_id"], r2["group_id"], r3["group_id"]])
        assert primary is not None
        assert len(primary.alerts) == 3


# ---------------------------------------------------------------------------
# Resolve group
# ---------------------------------------------------------------------------


class TestResolveGroup:
    def test_resolve_success(self):
        e = _engine()
        result = e.ingest_alert(alert_name="cpu_high")
        group = e.resolve_group(result["group_id"])
        assert group is not None
        assert group.status == GroupStatus.RESOLVED
        assert group.resolved_at is not None

    def test_resolve_not_found(self):
        e = _engine()
        assert e.resolve_group("nonexistent") is None

    def test_resolve_sets_resolved_at(self):
        e = _engine()
        before = time.time()
        result = e.ingest_alert(alert_name="cpu_high")
        group = e.resolve_group(result["group_id"])
        assert group is not None
        assert group.resolved_at is not None
        assert group.resolved_at >= before


# ---------------------------------------------------------------------------
# List rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_list_empty(self):
        e = _engine()
        assert len(e.list_rules()) == 0

    def test_list_with_rules(self):
        e = _engine()
        e.create_rule(name="r1", strategy=GroupingStrategy.FINGERPRINT)
        e.create_rule(name="r2", strategy=GroupingStrategy.LABEL_MATCH)
        rules = e.list_rules()
        assert len(rules) == 2
        names = {r.name for r in rules}
        assert names == {"r1", "r2"}


# ---------------------------------------------------------------------------
# Delete rule
# ---------------------------------------------------------------------------


class TestDeleteRule:
    def test_delete_success(self):
        e = _engine()
        rule = e.create_rule(name="temp", strategy=GroupingStrategy.FINGERPRINT)
        assert e.delete_rule(rule.id) is True
        assert len(e.list_rules()) == 0

    def test_delete_not_found(self):
        e = _engine()
        assert e.delete_rule("nonexistent") is False

    def test_delete_reduces_count(self):
        e = _engine()
        r1 = e.create_rule(name="r1", strategy=GroupingStrategy.FINGERPRINT)
        e.create_rule(name="r2", strategy=GroupingStrategy.LABEL_MATCH)
        e.delete_rule(r1.id)
        assert len(e.list_rules()) == 1


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        e = _engine()
        s = e.get_stats()
        assert s["total_alerts"] == 0
        assert s["total_groups"] == 0
        assert s["open_groups"] == 0
        assert s["merged_groups"] == 0
        assert s["resolved_groups"] == 0
        assert s["total_rules"] == 0

    def test_stats_with_data(self):
        e = _engine()
        e.ingest_alert(alert_name="cpu_high", service="api")
        e.ingest_alert(alert_name="mem_high", service="web")
        e.create_rule(name="r1", strategy=GroupingStrategy.FINGERPRINT)
        s = e.get_stats()
        assert s["total_alerts"] == 2
        assert s["total_groups"] == 2
        assert s["open_groups"] == 2
        assert s["total_rules"] == 1

    def test_stats_after_resolve(self):
        e = _engine()
        r = e.ingest_alert(alert_name="cpu_high")
        e.resolve_group(r["group_id"])
        s = e.get_stats()
        assert s["resolved_groups"] == 1
        assert s["open_groups"] == 0

    def test_stats_after_merge(self):
        e = _engine()
        r1 = e.ingest_alert(alert_name="cpu_high", service="api")
        r2 = e.ingest_alert(alert_name="mem_high", service="web")
        e.merge_groups([r1["group_id"], r2["group_id"]])
        s = e.get_stats()
        assert s["merged_groups"] == 1
        assert s["open_groups"] == 1
