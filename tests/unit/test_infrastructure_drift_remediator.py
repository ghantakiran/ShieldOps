"""Tests for InfrastructureDriftRemediator."""

from __future__ import annotations

from shieldops.operations.infrastructure_drift_remediator import (
    DriftOrigin,
    DriftType,
    InfrastructureDriftRemediator,
    RemediationAction,
)


def _engine(**kw) -> InfrastructureDriftRemediator:
    return InfrastructureDriftRemediator(**kw)


class TestEnums:
    def test_drift_type_values(self):
        for v in DriftType:
            assert isinstance(v.value, str)

    def test_remediation_action_values(self):
        for v in RemediationAction:
            assert isinstance(v.value, str)

    def test_drift_origin_values(self):
        for v in DriftOrigin:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(resource_id="r1")
        assert r.resource_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(resource_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            resource_id="r1",
            severity_score=85.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "resource_id")
        assert a.remediation_priority == 1

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestClassifyDriftSeverity:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            severity_score=90.0,
        )
        result = eng.classify_drift_severity()
        assert len(result) == 1
        assert result[0]["severity_class"] == "critical"

    def test_empty(self):
        r = _engine().classify_drift_severity()
        assert r == []


class TestComputeRemediationPriority:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            severity_score=85.0,
        )
        result = eng.compute_remediation_priority()
        assert len(result) == 1
        assert result[0]["priority"] == 1

    def test_empty(self):
        r = _engine().compute_remediation_priority()
        assert r == []


class TestRankResourcesByDriftRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            severity_score=50.0,
        )
        eng.record_item(
            resource_id="r2",
            severity_score=80.0,
        )
        result = eng.rank_resources_by_drift_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_resources_by_drift_risk()
        assert r == []
