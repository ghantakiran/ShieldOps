"""Tests for DeploymentReliabilityImpactEngine."""

from __future__ import annotations

from shieldops.changes.deployment_reliability_impact_engine import (
    DeploymentReliabilityImpactEngine,
    DeploymentType,
    ImpactWindow,
    ReliabilityImpact,
)


def _engine(**kw) -> DeploymentReliabilityImpactEngine:
    return DeploymentReliabilityImpactEngine(**kw)


class TestEnums:
    def test_reliability_impact_values(self):
        for v in ReliabilityImpact:
            assert isinstance(v.value, str)

    def test_deployment_type_values(self):
        for v in DeploymentType:
            assert isinstance(v.value, str)

    def test_impact_window_values(self):
        for v in ImpactWindow:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(deployment_id="d1")
        assert r.deployment_id == "d1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(deployment_id=f"d-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.record_item(
            deployment_id="d1",
            reliability_impact=ReliabilityImpact.SEVERE,
            deployment_type=DeploymentType.CANARY,
            delta=-5.0,
        )
        assert r.delta == -5.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(deployment_id="d1", delta=-2.0)
        a = eng.process(r.id)
        assert hasattr(a, "deployment_id")
        assert a.deployment_id == "d1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_degrading_detected(self):
        eng = _engine()
        r = eng.record_item(
            deployment_id="d1",
            reliability_impact=ReliabilityImpact.NEGATIVE,
        )
        a = eng.process(r.id)
        assert a.degrading is True


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(deployment_id="d1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(deployment_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(deployment_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeDeploymentReliabilityDelta:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(deployment_id="d1", delta=-3.0)
        result = eng.compute_deployment_reliability_delta()
        assert len(result) == 1
        assert result[0]["deployment_id"] == "d1"

    def test_empty(self):
        assert _engine().compute_deployment_reliability_delta() == []


class TestDetectReliabilityDegradingDeploys:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            deployment_id="d1",
            reliability_impact=ReliabilityImpact.SEVERE,
            delta=-5.0,
        )
        result = eng.detect_reliability_degrading_deploys()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_reliability_degrading_deploys() == []


class TestRankDeploymentsByReliabilityImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(deployment_id="d1", delta=-5.0)
        eng.record_item(deployment_id="d2", delta=2.0)
        result = eng.rank_deployments_by_reliability_impact()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_deployments_by_reliability_impact() == []
