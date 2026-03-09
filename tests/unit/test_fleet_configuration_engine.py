"""Tests for shieldops.operations.fleet_configuration_engine — FleetConfigurationEngine."""

from __future__ import annotations

from shieldops.operations.fleet_configuration_engine import (
    ConfigScope,
    FleetConfigurationEngine,
    PolicyEnforcement,
    PropagationStatus,
)


def _engine(**kw) -> FleetConfigurationEngine:
    return FleetConfigurationEngine(**kw)


class TestEnums:
    def test_config_scope(self):
        assert ConfigScope.CLUSTER == "cluster"

    def test_propagation(self):
        assert PropagationStatus.APPLIED == "applied"

    def test_policy(self):
        assert PolicyEnforcement.ENFORCED == "enforced"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="network-policy", config_scope=ConfigScope.CLUSTER)
        assert rec.name == "network-policy"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"cfg-{i}")
        assert len(eng._records) == 3


class TestConsistency:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="cfg-1", target_clusters=2, applied_clusters=1)
        eng.record_item(name="cfg-1", target_clusters=2, applied_clusters=2)
        result = eng.measure_consistency()
        assert isinstance(result, list)


class TestPropagation:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="cfg-1", propagation_status=PropagationStatus.APPLIED)
        result = eng.track_propagation()
        assert isinstance(result, dict)


class TestPolicyAudit:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="cfg-1", policy_enforcement=PolicyEnforcement.ENFORCED)
        result = eng.audit_policy_enforcement()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="cfg-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="cfg-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="cfg-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
