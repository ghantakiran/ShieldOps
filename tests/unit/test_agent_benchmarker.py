"""Tests for agent performance benchmarker."""

from __future__ import annotations

import pytest

from shieldops.agents.benchmarker import (
    AgentPerformanceBenchmarker,
    BenchmarkBaseline,
    BenchmarkMetric,
    BenchmarkResult,
    PerformanceRegression,
    RegressionSeverity,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _benchmarker(**kwargs) -> AgentPerformanceBenchmarker:
    return AgentPerformanceBenchmarker(**kwargs)


def _record_n(
    b: AgentPerformanceBenchmarker,
    agent_type: str = "investigation",
    n: int = 10,
    duration: float = 1.0,
    success: bool = True,
    confidence: float = 0.9,
    tokens: int = 500,
) -> None:
    for _ in range(n):
        b.record_execution(
            agent_type,
            duration_seconds=duration,
            success=success,
            confidence=confidence,
            token_usage=tokens,
        )


# ── Enum tests ───────────────────────────────────────────────────────


class TestBenchmarkMetricEnum:
    def test_duration(self) -> None:
        assert BenchmarkMetric.DURATION == "duration"

    def test_success_rate(self) -> None:
        assert BenchmarkMetric.SUCCESS_RATE == "success_rate"

    def test_confidence(self) -> None:
        assert BenchmarkMetric.CONFIDENCE == "confidence"

    def test_token_usage(self) -> None:
        assert BenchmarkMetric.TOKEN_USAGE == "token_usage"  # noqa: S105

    def test_member_count(self) -> None:
        assert len(BenchmarkMetric) == 4


class TestRegressionSeverityEnum:
    def test_minor(self) -> None:
        assert RegressionSeverity.MINOR == "minor"

    def test_moderate(self) -> None:
        assert RegressionSeverity.MODERATE == "moderate"

    def test_major(self) -> None:
        assert RegressionSeverity.MAJOR == "major"

    def test_member_count(self) -> None:
        assert len(RegressionSeverity) == 3


# ── Model tests ──────────────────────────────────────────────────────


class TestBenchmarkResultModel:
    def test_defaults(self) -> None:
        r = BenchmarkResult(agent_type="investigation")
        assert len(r.id) == 12
        assert r.agent_type == "investigation"
        assert r.duration_seconds == 0.0
        assert r.success is True
        assert r.confidence == 0.0
        assert r.token_usage == 0
        assert r.timestamp > 0
        assert r.metadata == {}


class TestBenchmarkBaselineModel:
    def test_defaults(self) -> None:
        bl = BenchmarkBaseline(agent_type="remediation")
        assert bl.agent_type == "remediation"
        assert bl.avg_duration == 0.0
        assert bl.avg_confidence == 0.0
        assert bl.avg_token_usage == 0.0
        assert bl.success_rate == 0.0
        assert bl.sample_count == 0
        assert bl.computed_at > 0


class TestPerformanceRegressionModel:
    def test_defaults(self) -> None:
        pr = PerformanceRegression(
            agent_type="security",
            metric=BenchmarkMetric.DURATION,
            baseline_value=1.0,
            current_value=2.0,
        )
        assert len(pr.id) == 12
        assert pr.severity == RegressionSeverity.MINOR
        assert pr.detected_at > 0
        assert pr.description == ""
        assert pr.deviation == 0.0


# ── Benchmarker creation ─────────────────────────────────────────────


class TestBenchmarkerCreation:
    def test_default_params(self) -> None:
        b = _benchmarker()
        assert b._baseline_seconds == 30 * 86400
        assert b._threshold == 0.2

    def test_custom_baseline_days(self) -> None:
        b = _benchmarker(baseline_days=7)
        assert b._baseline_seconds == 7 * 86400

    def test_custom_regression_threshold(self) -> None:
        b = _benchmarker(regression_threshold=0.5)
        assert b._threshold == 0.5


# ── record_execution ─────────────────────────────────────────────────


class TestRecordExecution:
    def test_basic_record(self) -> None:
        b = _benchmarker()
        r = b.record_execution("investigation", duration_seconds=2.5, success=True)
        assert isinstance(r, BenchmarkResult)
        assert r.agent_type == "investigation"
        assert r.duration_seconds == 2.5

    def test_record_with_metadata(self) -> None:
        b = _benchmarker()
        r = b.record_execution("investigation", metadata={"env": "prod"})
        assert r.metadata["env"] == "prod"

    def test_multiple_types_stored_separately(self) -> None:
        b = _benchmarker()
        b.record_execution("investigation")
        b.record_execution("remediation")
        b.record_execution("investigation")
        assert len(b._results["investigation"]) == 2
        assert len(b._results["remediation"]) == 1

    def test_records_accumulate(self) -> None:
        b = _benchmarker()
        _record_n(b, n=5)
        assert len(b._results["investigation"]) == 5

    def test_default_values(self) -> None:
        b = _benchmarker()
        r = b.record_execution("security")
        assert r.duration_seconds == 0.0
        assert r.success is True
        assert r.confidence == 0.0
        assert r.token_usage == 0


# ── compute_baseline ─────────────────────────────────────────────────


class TestComputeBaseline:
    def test_with_data(self) -> None:
        b = _benchmarker()
        _record_n(b, duration=2.0, confidence=0.85, tokens=600, n=5)
        bl = b.compute_baseline("investigation")
        assert bl.agent_type == "investigation"
        assert bl.avg_duration == pytest.approx(2.0, abs=0.01)
        assert bl.avg_confidence == pytest.approx(0.85, abs=0.01)
        assert bl.avg_token_usage == pytest.approx(600.0, abs=1.0)
        assert bl.success_rate == pytest.approx(1.0)
        assert bl.sample_count == 5

    def test_empty_no_results(self) -> None:
        b = _benchmarker()
        bl = b.compute_baseline("investigation")
        assert bl.agent_type == "investigation"
        assert bl.sample_count == 0
        assert bl.avg_duration == 0.0
        assert bl.success_rate == 0.0

    def test_correct_averages_mixed(self) -> None:
        b = _benchmarker()
        b.record_execution(
            "inv",
            duration_seconds=1.0,
            success=True,
            confidence=0.8,
            token_usage=100,
        )
        b.record_execution(
            "inv",
            duration_seconds=3.0,
            success=False,
            confidence=0.6,
            token_usage=300,
        )
        bl = b.compute_baseline("inv")
        assert bl.avg_duration == pytest.approx(2.0, abs=0.01)
        assert bl.avg_confidence == pytest.approx(0.7, abs=0.01)
        assert bl.avg_token_usage == pytest.approx(200.0, abs=1.0)
        assert bl.success_rate == pytest.approx(0.5, abs=0.01)
        assert bl.sample_count == 2

    def test_baseline_stored_internally(self) -> None:
        b = _benchmarker()
        _record_n(b, n=3)
        b.compute_baseline("investigation")
        assert "investigation" in b._baselines


# ── detect_regressions ───────────────────────────────────────────────


class TestDetectRegressions:
    def _setup_baseline(
        self,
        b: AgentPerformanceBenchmarker,
        agent: str = "inv",
        duration: float = 1.0,
        confidence: float = 0.9,
        tokens: int = 500,
    ) -> None:
        _record_n(
            b,
            agent_type=agent,
            n=10,
            duration=duration,
            confidence=confidence,
            tokens=tokens,
        )
        b.compute_baseline(agent)

    def test_duration_increase_regression(self) -> None:
        b = _benchmarker(regression_threshold=0.2)
        self._setup_baseline(b, duration=1.0)
        # Record slower recent executions
        _record_n(b, agent_type="inv", n=5, duration=2.0)
        regs = b.detect_regressions("inv", window_size=5)
        metrics = {r.metric for r in regs}
        assert BenchmarkMetric.DURATION in metrics

    def test_success_rate_decrease_regression(self) -> None:
        b = _benchmarker(regression_threshold=0.2)
        self._setup_baseline(b, duration=1.0, confidence=0.9, tokens=500)
        # Record recent failures
        _record_n(b, agent_type="inv", n=5, duration=1.0, success=False, confidence=0.9, tokens=500)
        regs = b.detect_regressions("inv", window_size=5)
        metrics = {r.metric for r in regs}
        assert BenchmarkMetric.SUCCESS_RATE in metrics

    def test_confidence_decrease_regression(self) -> None:
        b = _benchmarker(regression_threshold=0.2)
        self._setup_baseline(b, duration=1.0, confidence=0.9, tokens=500)
        # Record recent low-confidence
        _record_n(b, agent_type="inv", n=5, duration=1.0, confidence=0.3, tokens=500)
        regs = b.detect_regressions("inv", window_size=5)
        metrics = {r.metric for r in regs}
        assert BenchmarkMetric.CONFIDENCE in metrics

    def test_token_usage_increase_regression(self) -> None:
        b = _benchmarker(regression_threshold=0.2)
        self._setup_baseline(b, duration=1.0, confidence=0.9, tokens=500)
        # Record recent high-token executions
        _record_n(b, agent_type="inv", n=5, duration=1.0, confidence=0.9, tokens=2000)
        regs = b.detect_regressions("inv", window_size=5)
        metrics = {r.metric for r in regs}
        assert BenchmarkMetric.TOKEN_USAGE in metrics

    def test_no_regression_stable(self) -> None:
        b = _benchmarker(regression_threshold=0.2)
        self._setup_baseline(b)
        regs = b.detect_regressions("inv", window_size=10)
        assert regs == []

    def test_no_baseline_returns_empty(self) -> None:
        b = _benchmarker()
        _record_n(b, n=5)
        regs = b.detect_regressions("investigation")
        assert regs == []

    def test_window_size_parameter(self) -> None:
        b = _benchmarker(regression_threshold=0.2)
        self._setup_baseline(b, duration=1.0)
        # 5 slow then 3 fast; window_size=3 should see only fast ones => no regression
        _record_n(b, agent_type="inv", n=5, duration=5.0)
        _record_n(b, agent_type="inv", n=3, duration=1.0)
        regs = b.detect_regressions("inv", window_size=3)
        duration_regs = [r for r in regs if r.metric == BenchmarkMetric.DURATION]
        assert duration_regs == []

    def test_regression_description_populated(self) -> None:
        b = _benchmarker(regression_threshold=0.2)
        self._setup_baseline(b, duration=1.0)
        _record_n(b, agent_type="inv", n=5, duration=5.0)
        regs = b.detect_regressions("inv", window_size=5)
        dur_reg = [r for r in regs if r.metric == BenchmarkMetric.DURATION]
        assert len(dur_reg) >= 1
        assert "Duration" in dur_reg[0].description


# ── _classify_regression ─────────────────────────────────────────────


class TestClassifyRegression:
    def test_major_at_0_5(self) -> None:
        b = _benchmarker()
        assert b._classify_regression(0.5) == RegressionSeverity.MAJOR

    def test_major_above_0_5(self) -> None:
        b = _benchmarker()
        assert b._classify_regression(0.9) == RegressionSeverity.MAJOR

    def test_moderate_at_0_3(self) -> None:
        b = _benchmarker()
        assert b._classify_regression(0.3) == RegressionSeverity.MODERATE

    def test_moderate_at_0_49(self) -> None:
        b = _benchmarker()
        assert b._classify_regression(0.49) == RegressionSeverity.MODERATE

    def test_minor_below_0_3(self) -> None:
        b = _benchmarker()
        assert b._classify_regression(0.29) == RegressionSeverity.MINOR

    def test_minor_at_zero(self) -> None:
        b = _benchmarker()
        assert b._classify_regression(0.0) == RegressionSeverity.MINOR


# ── get_benchmark ────────────────────────────────────────────────────


class TestGetBenchmark:
    def test_with_data(self) -> None:
        b = _benchmarker()
        _record_n(b, n=3)
        b.compute_baseline("investigation")
        bm = b.get_benchmark("investigation")
        assert bm["agent_type"] == "investigation"
        assert bm["total_executions"] == 3
        assert bm["baseline"] is not None

    def test_empty_no_results(self) -> None:
        b = _benchmarker()
        bm = b.get_benchmark("investigation")
        assert bm["agent_type"] == "investigation"
        assert bm["total_executions"] == 0
        assert bm["baseline"] is None


# ── list_benchmarks ──────────────────────────────────────────────────


class TestListBenchmarks:
    def test_multiple_types(self) -> None:
        b = _benchmarker()
        b.record_execution("investigation")
        b.record_execution("remediation")
        bms = b.list_benchmarks()
        assert len(bms) == 2
        types = {bm["agent_type"] for bm in bms}
        assert types == {"investigation", "remediation"}

    def test_empty(self) -> None:
        b = _benchmarker()
        assert b.list_benchmarks() == []


# ── get_stats ────────────────────────────────────────────────────────


class TestGetStats:
    def test_empty(self) -> None:
        b = _benchmarker()
        stats = b.get_stats()
        assert stats["tracked_agent_types"] == 0
        assert stats["total_executions"] == 0
        assert stats["baselines_computed"] == 0

    def test_with_data(self) -> None:
        b = _benchmarker()
        _record_n(b, agent_type="investigation", n=3)
        _record_n(b, agent_type="remediation", n=2)
        b.compute_baseline("investigation")
        stats = b.get_stats()
        assert stats["tracked_agent_types"] == 2
        assert stats["total_executions"] == 5
        assert stats["baselines_computed"] == 1
