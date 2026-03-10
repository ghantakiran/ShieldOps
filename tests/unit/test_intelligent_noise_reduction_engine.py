"""Tests for IntelligentNoiseReductionEngine."""

from __future__ import annotations

from shieldops.incidents.intelligent_noise_reduction_engine import (
    ClusterMethod,
    IntelligentNoiseReductionEngine,
    NoiseCategory,
    ReductionOutcome,
)


def _engine(**kw) -> IntelligentNoiseReductionEngine:
    return IntelligentNoiseReductionEngine(**kw)


class TestEnums:
    def test_cluster_method(self):
        assert ClusterMethod.SEMANTIC == "semantic"

    def test_noise_category(self):
        assert NoiseCategory.DUPLICATE == "duplicate"

    def test_reduction_outcome(self):
        assert ReductionOutcome.MERGED == "merged"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(alert_id="a-1", service="api")
        assert rec.alert_id == "a-1"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(alert_id=f"a-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(
            alert_id="a-1",
            service="api",
            cluster_id="c-1",
        )
        result = eng.process("c-1")
        assert isinstance(result, dict)
        assert result["cluster_id"] == "c-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestClusterRelatedAlerts:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            alert_id="a-1",
            service="api",
            cluster_id="c-1",
        )
        result = eng.cluster_related_alerts("c-1")
        assert isinstance(result, list)


class TestComputeNoiseRatio:
    def test_basic(self):
        eng = _engine()
        eng.add_record(alert_id="a-1", service="api")
        result = eng.compute_noise_ratio("api")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_id="a-1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(alert_id="a-1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(alert_id="a-1", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
