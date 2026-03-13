"""Tests for AlertDedupIntelligence."""

from __future__ import annotations

from shieldops.observability.alert_dedup_intelligence import (
    AlertDedupIntelligence,
    ClusterStatus,
    DedupStrategy,
    SimilarityLevel,
)


def _engine(**kw) -> AlertDedupIntelligence:
    return AlertDedupIntelligence(**kw)


class TestEnums:
    def test_dedup_strategy_values(self):
        for v in DedupStrategy:
            assert isinstance(v.value, str)

    def test_cluster_status_values(self):
        for v in ClusterStatus:
            assert isinstance(v.value, str)

    def test_similarity_level_values(self):
        for v in SimilarityLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(alert_id="a1")
        assert r.alert_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(alert_id=f"a-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            alert_id="a1",
            fingerprint="fp1",
            cluster_id="c1",
        )
        assert r.fingerprint == "fp1"


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(alert_id="a1", fingerprint="fp1")
        a = eng.process(r.id)
        assert hasattr(a, "alert_id")
        assert a.alert_id == "a1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
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
        eng.add_record(alert_id="a1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeDedupFingerprints:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(alert_id="a1", fingerprint="fp1")
        eng.add_record(alert_id="a2", fingerprint="fp1")
        result = eng.compute_dedup_fingerprints()
        assert len(result) >= 1
        assert result[0]["alert_count"] == 2

    def test_empty(self):
        assert _engine().compute_dedup_fingerprints() == []


class TestIdentifyDuplicateClusters:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(alert_id="a1", cluster_id="c1")
        eng.add_record(alert_id="a2", cluster_id="c1")
        result = eng.identify_duplicate_clusters()
        assert len(result) == 1
        assert result[0]["member_count"] == 2

    def test_empty(self):
        r = _engine().identify_duplicate_clusters()
        assert r == []


class TestMeasureDedupEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            similarity_level=SimilarityLevel.EXACT,
        )
        result = eng.measure_dedup_effectiveness()
        assert len(result) >= 1

    def test_empty(self):
        r = _engine().measure_dedup_effectiveness()
        assert r == []
