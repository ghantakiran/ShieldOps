"""Tests for TraceSamplingIntelligenceEngine."""

from __future__ import annotations

from shieldops.observability.trace_sampling_intelligence_engine import (
    SampleDecision,
    SamplingQuality,
    SamplingStrategy,
    TraceSamplingAnalysis,
    TraceSamplingIntelligenceEngine,
    TraceSamplingRecord,
    TraceSamplingReport,
)


def test_add_record() -> None:
    engine = TraceSamplingIntelligenceEngine()
    rec = engine.add_record(
        service_name="svc-a",
        trace_id="t1",
        sampling_strategy=SamplingStrategy.TAIL_BASED,
        sample_decision=SampleDecision.KEEP,
        sampling_quality=SamplingQuality.REPRESENTATIVE,
        sampling_rate=0.1,
        trace_volume=1000,
        kept_traces=100,
        bias_score=0.1,
    )
    assert isinstance(rec, TraceSamplingRecord)
    assert rec.service_name == "svc-a"
    assert rec.sampling_rate == 0.1


def test_process() -> None:
    engine = TraceSamplingIntelligenceEngine()
    rec = engine.add_record(
        service_name="svc-b",
        sampling_strategy=SamplingStrategy.ADAPTIVE,
        trace_volume=500,
        kept_traces=400,
        bias_score=0.8,
    )
    result = engine.process(rec.id)
    assert isinstance(result, TraceSamplingAnalysis)
    assert result.service_name == "svc-b"
    assert result.effective_rate == 80.0
    assert result.bias_detected is True


def test_process_not_found() -> None:
    engine = TraceSamplingIntelligenceEngine()
    result = engine.process("unknown-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = TraceSamplingIntelligenceEngine()
    for svc, strat, dec, qual, rate in [
        (
            "svc-a",
            SamplingStrategy.HEAD_BASED,
            SampleDecision.KEEP,
            SamplingQuality.REPRESENTATIVE,
            0.05,
        ),
        ("svc-b", SamplingStrategy.TAIL_BASED, SampleDecision.DROP, SamplingQuality.BIASED, 0.1),
        ("svc-c", SamplingStrategy.PRIORITY, SampleDecision.DEFER, SamplingQuality.SPARSE, 0.2),
        (
            "svc-d",
            SamplingStrategy.ADAPTIVE,
            SampleDecision.ESCALATE,
            SamplingQuality.COMPREHENSIVE,
            0.5,
        ),
    ]:
        engine.add_record(
            service_name=svc,
            sampling_strategy=strat,
            sample_decision=dec,
            sampling_quality=qual,
            sampling_rate=rate,
        )
    report = engine.generate_report()
    assert isinstance(report, TraceSamplingReport)
    assert report.total_records == 4
    assert "head_based" in report.by_sampling_strategy


def test_get_stats() -> None:
    engine = TraceSamplingIntelligenceEngine()
    engine.add_record(sampling_strategy=SamplingStrategy.HEAD_BASED, sampling_rate=0.05)
    engine.add_record(sampling_strategy=SamplingStrategy.TAIL_BASED, sampling_rate=0.1)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "strategy_distribution" in stats


def test_clear_data() -> None:
    engine = TraceSamplingIntelligenceEngine()
    engine.add_record(service_name="svc-x", sampling_rate=0.01)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_evaluate_sampling_strategies() -> None:
    engine = TraceSamplingIntelligenceEngine()
    engine.add_record(
        sampling_strategy=SamplingStrategy.HEAD_BASED,
        sampling_rate=0.05,
        bias_score=0.2,
        trace_volume=1000,
        kept_traces=50,
    )
    engine.add_record(
        sampling_strategy=SamplingStrategy.TAIL_BASED,
        sampling_rate=0.1,
        bias_score=0.6,
        trace_volume=1000,
        kept_traces=900,
    )
    engine.add_record(
        sampling_strategy=SamplingStrategy.HEAD_BASED,
        sampling_rate=0.05,
        bias_score=0.1,
        trace_volume=500,
        kept_traces=25,
    )
    results = engine.evaluate_sampling_strategies()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "sampling_strategy" in results[0]
    assert "effective_rate_pct" in results[0]


def test_detect_sampling_bias() -> None:
    engine = TraceSamplingIntelligenceEngine()
    engine.add_record(service_name="svc-bias", bias_score=0.9, sampling_rate=0.1)
    engine.add_record(service_name="svc-ok", bias_score=0.1, sampling_rate=0.1)
    engine.add_record(service_name="svc-bias", bias_score=0.7, sampling_rate=0.15)
    results = engine.detect_sampling_bias()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "bias_detected" in results[0]
    assert results[0]["avg_bias_score"] >= results[-1]["avg_bias_score"]


def test_optimize_sampling_rates() -> None:
    engine = TraceSamplingIntelligenceEngine()
    engine.add_record(service_name="svc-a", sampling_rate=0.05, bias_score=0.8)
    engine.add_record(service_name="svc-b", sampling_rate=0.1, bias_score=0.1)
    engine.add_record(service_name="svc-a", sampling_rate=0.07, bias_score=0.6)
    results = engine.optimize_sampling_rates()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "recommended_rate" in results[0]
    assert "adjustment_pct" in results[0]
