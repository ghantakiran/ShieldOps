"""Tests for SecurityPostureTrendEngine."""

from __future__ import annotations

from shieldops.security.security_posture_trend_engine import (
    BenchmarkSource,
    PostureDimension,
    SecurityPostureTrendEngine,
    TrendDirection,
)


def _engine(**kw) -> SecurityPostureTrendEngine:
    return SecurityPostureTrendEngine(**kw)


class TestEnums:
    def test_dim_network(self):
        assert PostureDimension.NETWORK == "network"

    def test_dim_identity(self):
        assert PostureDimension.IDENTITY == "identity"

    def test_dim_data(self):
        assert PostureDimension.DATA == "data"

    def test_dim_application(self):
        assert PostureDimension.APPLICATION == "application"

    def test_dir_improving(self):
        assert TrendDirection.IMPROVING == "improving"

    def test_dir_stable(self):
        assert TrendDirection.STABLE == "stable"

    def test_dir_declining(self):
        assert TrendDirection.DECLINING == "declining"

    def test_dir_volatile(self):
        assert TrendDirection.VOLATILE == "volatile"

    def test_bench_industry(self):
        assert BenchmarkSource.INDUSTRY == "industry"

    def test_bench_internal(self):
        assert BenchmarkSource.INTERNAL == "internal"

    def test_bench_regulatory(self):
        assert BenchmarkSource.REGULATORY == "regulatory"

    def test_bench_peer(self):
        assert BenchmarkSource.PEER == "peer"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(posture_id="p1", posture_score=85.0)
        assert r.posture_id == "p1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(posture_id=f"p-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            posture_id="p1",
            posture_score=80.0,
            benchmark_score=90.0,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.posture_id == "p1"

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(posture_id="p1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(posture_id="p1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(posture_id="p1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputePostureTrajectory:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            posture_id="p1",
            dimension=PostureDimension.NETWORK,
            posture_score=80.0,
        )
        result = eng.compute_posture_trajectory()
        assert len(result) == 1
        assert result[0]["dimension"] == "network"

    def test_empty(self):
        assert _engine().compute_posture_trajectory() == []


class TestDetectRegressionSignals:
    def test_basic(self):
        eng = _engine(regression_threshold=70.0)
        eng.add_record(posture_id="p1", posture_score=50.0)
        result = eng.detect_regression_signals()
        assert len(result) == 1
        assert result[0]["regression_gap"] > 0

    def test_empty(self):
        assert _engine().detect_regression_signals() == []


class TestBenchmarkAgainstPeers:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            posture_id="p1",
            posture_score=70.0,
            benchmark_score=80.0,
        )
        result = eng.benchmark_against_peers()
        assert result["overall_gap"] == 10.0

    def test_empty(self):
        result = _engine().benchmark_against_peers()
        assert result["overall_gap"] == 0.0
