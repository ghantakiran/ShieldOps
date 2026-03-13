"""Tests for EnvironmentParityAnalyzer."""

from __future__ import annotations

from shieldops.changes.environment_parity_analyzer import (
    DivergenceLevel,
    EnvironmentParityAnalyzer,
    EnvironmentType,
    ParityDimension,
)


def _engine(**kw) -> EnvironmentParityAnalyzer:
    return EnvironmentParityAnalyzer(**kw)


class TestEnums:
    def test_environment_type_values(self):
        for v in EnvironmentType:
            assert isinstance(v.value, str)

    def test_parity_dimension_values(self):
        for v in ParityDimension:
            assert isinstance(v.value, str)

    def test_divergence_level_values(self):
        for v in DivergenceLevel:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(env_id="e1")
        assert r.env_id == "e1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(env_id=f"e-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            env_id="e1",
            parity_score=85.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "env_id")
        assert a.env_id == "e1"

    def test_needs_attention(self):
        eng = _engine()
        r = eng.record_item(
            env_id="e1",
            divergence_level=(DivergenceLevel.CRITICAL),
        )
        a = eng.process(r.id)
        assert a.needs_attention is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(env_id="e1")
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
        eng.record_item(env_id="e1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(env_id="e1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeParityScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(env_id="e1", parity_score=80.0)
        result = eng.compute_parity_score()
        assert len(result) == 1
        assert result[0]["avg_parity"] == 80.0

    def test_empty(self):
        r = _engine().compute_parity_score()
        assert r == []


class TestDetectEnvironmentDrift:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            env_id="e1",
            divergence_level=(DivergenceLevel.SIGNIFICANT),
        )
        result = eng.detect_environment_drift()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().detect_environment_drift()
        assert r == []


class TestRankEnvironmentsByDivergence:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(env_id="e1", parity_score=90.0)
        eng.record_item(env_id="e2", parity_score=50.0)
        result = eng.rank_environments_by_divergence()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_environments_by_divergence()
        assert r == []
