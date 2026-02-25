"""Tests for shieldops.changes.velocity_throttle — ChangeVelocityThrottle."""

from __future__ import annotations

from shieldops.changes.velocity_throttle import (
    ChangeScope,
    ChangeVelocityRecord,
    ChangeVelocityThrottle,
    ThrottleAction,
    ThrottlePolicy,
    VelocityThrottleReport,
    VelocityZone,
)


def _engine(**kw) -> ChangeVelocityThrottle:
    return ChangeVelocityThrottle(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ThrottleAction (5)
    def test_action_allow(self):
        assert ThrottleAction.ALLOW == "allow"

    def test_action_warn(self):
        assert ThrottleAction.WARN == "warn"

    def test_action_delay(self):
        assert ThrottleAction.DELAY == "delay"

    def test_action_require_approval(self):
        assert ThrottleAction.REQUIRE_APPROVAL == "require_approval"

    def test_action_block(self):
        assert ThrottleAction.BLOCK == "block"

    # VelocityZone (5)
    def test_zone_green(self):
        assert VelocityZone.GREEN == "green"

    def test_zone_yellow(self):
        assert VelocityZone.YELLOW == "yellow"

    def test_zone_orange(self):
        assert VelocityZone.ORANGE == "orange"

    def test_zone_red(self):
        assert VelocityZone.RED == "red"

    def test_zone_lockdown(self):
        assert VelocityZone.LOCKDOWN == "lockdown"

    # ChangeScope (5)
    def test_scope_service(self):
        assert ChangeScope.SERVICE == "service"

    def test_scope_team(self):
        assert ChangeScope.TEAM == "team"

    def test_scope_environment(self):
        assert ChangeScope.ENVIRONMENT == "environment"

    def test_scope_region(self):
        assert ChangeScope.REGION == "region"

    def test_scope_global(self):
        assert ChangeScope.GLOBAL == "global"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_change_velocity_record_defaults(self):
        r = ChangeVelocityRecord()
        assert r.id
        assert r.service == ""
        assert r.team == ""
        assert r.environment == "production"
        assert r.change_type == ""
        assert r.action_taken == ThrottleAction.ALLOW
        assert r.zone == VelocityZone.GREEN
        assert r.velocity_per_hour == 0.0
        assert r.created_at > 0

    def test_throttle_policy_defaults(self):
        p = ThrottlePolicy()
        assert p.id
        assert p.name == ""
        assert p.scope == ChangeScope.SERVICE
        assert p.max_changes_per_hour == 10
        assert p.warn_at == 6
        assert p.delay_at == 8
        assert p.block_at == 12
        assert p.created_at > 0

    def test_velocity_throttle_report_defaults(self):
        r = VelocityThrottleReport()
        assert r.total_records == 0
        assert r.total_policies == 0
        assert r.by_action == {}
        assert r.by_zone == {}
        assert r.spike_count == 0
        assert r.avg_velocity_per_hour == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_policy
# ---------------------------------------------------------------------------


class TestRegisterPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.register_policy(name="deploy-limit", scope=ChangeScope.SERVICE)
        assert p.name == "deploy-limit"
        assert p.scope == ChangeScope.SERVICE
        assert p.max_changes_per_hour == 10

    def test_with_params(self):
        eng = _engine()
        p = eng.register_policy(
            name="strict-policy",
            scope=ChangeScope.GLOBAL,
            max_changes_per_hour=5,
            warn_at=3,
            delay_at=4,
            block_at=6,
        )
        assert p.scope == ChangeScope.GLOBAL
        assert p.max_changes_per_hour == 5
        assert p.warn_at == 3
        assert p.delay_at == 4
        assert p.block_at == 6

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.register_policy(name=f"policy-{i}")
        assert len(eng._policies) == 3


# ---------------------------------------------------------------------------
# get_policy
# ---------------------------------------------------------------------------


class TestGetPolicy:
    def test_found(self):
        eng = _engine()
        p = eng.register_policy(name="my-policy")
        result = eng.get_policy(p.id)
        assert result is not None
        assert result.name == "my-policy"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_policy("nonexistent") is None


# ---------------------------------------------------------------------------
# list_policies
# ---------------------------------------------------------------------------


class TestListPolicies:
    def test_list_all(self):
        eng = _engine()
        eng.register_policy(name="p1", scope=ChangeScope.SERVICE)
        eng.register_policy(name="p2", scope=ChangeScope.GLOBAL)
        assert len(eng.list_policies()) == 2

    def test_filter_by_scope(self):
        eng = _engine()
        eng.register_policy(name="p1", scope=ChangeScope.SERVICE)
        eng.register_policy(name="p2", scope=ChangeScope.GLOBAL)
        results = eng.list_policies(scope=ChangeScope.SERVICE)
        assert len(results) == 1
        assert results[0].name == "p1"


# ---------------------------------------------------------------------------
# evaluate_change
# ---------------------------------------------------------------------------


class TestEvaluateChange:
    def test_first_change_green(self):
        eng = _engine(max_changes_per_hour=10)
        r = eng.evaluate_change(service="svc-a")
        assert r.service == "svc-a"
        assert r.velocity_per_hour == 1.0
        assert r.zone == VelocityZone.GREEN
        assert r.action_taken == ThrottleAction.ALLOW

    def test_many_changes_escalate_zone(self):
        eng = _engine(max_changes_per_hour=10)
        for _ in range(15):
            r = eng.evaluate_change(service="svc-a")
        # velocity is 16 => ratio 1.6 >= 1.5 => LOCKDOWN
        assert r.zone == VelocityZone.LOCKDOWN
        assert r.action_taken == ThrottleAction.BLOCK

    def test_with_optional_params(self):
        eng = _engine()
        r = eng.evaluate_change(
            service="svc-b",
            team="team-x",
            environment="staging",
            change_type="deploy",
        )
        assert r.team == "team-x"
        assert r.environment == "staging"
        assert r.change_type == "deploy"


# ---------------------------------------------------------------------------
# get_current_velocity
# ---------------------------------------------------------------------------


class TestGetCurrentVelocity:
    def test_velocity_after_changes(self):
        eng = _engine(max_changes_per_hour=10)
        eng.evaluate_change(service="svc-a")
        eng.evaluate_change(service="svc-a")
        result = eng.get_current_velocity("svc-a")
        assert result["service"] == "svc-a"
        assert result["velocity_per_hour"] == 2
        assert result["max_per_hour"] == 10
        assert result["zone"] == VelocityZone.GREEN.value

    def test_no_changes(self):
        eng = _engine(max_changes_per_hour=10)
        result = eng.get_current_velocity("svc-x")
        assert result["velocity_per_hour"] == 0
        assert result["zone"] == VelocityZone.GREEN.value


# ---------------------------------------------------------------------------
# get_current_zone
# ---------------------------------------------------------------------------


class TestGetCurrentZone:
    def test_zone_with_changes(self):
        eng = _engine(max_changes_per_hour=10)
        eng.evaluate_change(service="svc-a")
        result = eng.get_current_zone("svc-a")
        assert result["service"] == "svc-a"
        assert result["zone"] == VelocityZone.GREEN.value
        assert result["action"] == ThrottleAction.ALLOW.value
        assert result["velocity_per_hour"] == 1

    def test_zone_no_changes(self):
        eng = _engine()
        result = eng.get_current_zone("unknown")
        assert result["zone"] == VelocityZone.GREEN.value
        assert result["action"] == ThrottleAction.ALLOW.value


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.evaluate_change(service="svc-a")
        eng.evaluate_change(service="svc-b")
        assert len(eng.list_records()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.evaluate_change(service="svc-a")
        eng.evaluate_change(service="svc-b")
        results = eng.list_records(service="svc-a")
        assert len(results) == 1
        assert results[0].service == "svc-a"

    def test_filter_by_zone(self):
        eng = _engine(max_changes_per_hour=10)
        eng.evaluate_change(service="svc-a")  # velocity 1 => GREEN
        results = eng.list_records(zone=VelocityZone.GREEN)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# identify_velocity_spikes
# ---------------------------------------------------------------------------


class TestIdentifyVelocitySpikes:
    def test_has_spikes(self):
        eng = _engine(max_changes_per_hour=3)
        for _ in range(5):
            eng.evaluate_change(service="svc-hot")
        eng.evaluate_change(service="svc-cold")
        spikes = eng.identify_velocity_spikes()
        assert len(spikes) == 1
        assert spikes[0]["service"] == "svc-hot"
        assert spikes[0]["velocity_per_hour"] == 5
        assert spikes[0]["excess"] == 2

    def test_no_spikes(self):
        eng = _engine(max_changes_per_hour=100)
        eng.evaluate_change(service="svc-a")
        assert eng.identify_velocity_spikes() == []


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_changes_per_hour=10)
        eng.register_policy(name="p1")
        eng.evaluate_change(service="svc-a")
        eng.evaluate_change(service="svc-b")
        report = eng.generate_report()
        assert isinstance(report, VelocityThrottleReport)
        assert report.total_records == 2
        assert report.total_policies == 1
        assert len(report.by_action) > 0
        assert len(report.by_zone) > 0
        assert report.avg_velocity_per_hour > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.total_policies == 0
        assert "Change velocity within normal parameters" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.evaluate_change(service="svc-a")
        eng.register_policy(name="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_policies"] == 0
        assert stats["zone_distribution"] == {}
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine(max_changes_per_hour=10)
        eng.evaluate_change(service="svc-a")
        eng.register_policy(name="p1")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["total_policies"] == 1
        assert stats["max_changes_per_hour"] == 10
        assert "green" in stats["zone_distribution"]
        assert stats["unique_services"] == 1
