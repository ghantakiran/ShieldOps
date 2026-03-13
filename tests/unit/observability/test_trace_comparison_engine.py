"""Tests for TraceComparisonEngine."""

from __future__ import annotations

from shieldops.observability.trace_comparison_engine import (
    ComparisonResult,
    ComparisonType,
    DifferenceType,
    TraceComparisonAnalysis,
    TraceComparisonEngine,
    TraceComparisonRecord,
    TraceComparisonReport,
)


def test_add_record() -> None:
    engine = TraceComparisonEngine()
    rec = engine.add_record(
        service_name="svc-a",
        baseline_trace_id="base-1",
        candidate_trace_id="cand-1",
        comparison_type=ComparisonType.TEMPORAL,
        difference_type=DifferenceType.PERFORMANCE,
        comparison_result=ComparisonResult.DEGRADED,
        baseline_latency_ms=200.0,
        candidate_latency_ms=500.0,
        baseline_error_rate=0.01,
        candidate_error_rate=0.05,
        difference_score=75.0,
    )
    assert isinstance(rec, TraceComparisonRecord)
    assert rec.service_name == "svc-a"
    assert rec.difference_score == 75.0


def test_process() -> None:
    engine = TraceComparisonEngine()
    rec = engine.add_record(
        service_name="svc-b",
        baseline_latency_ms=100.0,
        candidate_latency_ms=300.0,
        baseline_error_rate=0.01,
        candidate_error_rate=0.02,
        comparison_result=ComparisonResult.DEGRADED,
    )
    result = engine.process(rec.id)
    assert isinstance(result, TraceComparisonAnalysis)
    assert result.service_name == "svc-b"
    assert result.latency_delta_ms == 200.0
    assert result.comparison_result == ComparisonResult.DEGRADED


def test_process_not_found() -> None:
    engine = TraceComparisonEngine()
    result = engine.process("none-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = TraceComparisonEngine()
    for svc, ctype, dtype, result, bscore, cscore in [
        (
            "svc-a",
            ComparisonType.TEMPORAL,
            DifferenceType.PERFORMANCE,
            ComparisonResult.DEGRADED,
            100.0,
            300.0,
        ),
        (
            "svc-b",
            ComparisonType.VERSION,
            DifferenceType.STRUCTURAL,
            ComparisonResult.IMPROVED,
            300.0,
            100.0,
        ),
        (
            "svc-c",
            ComparisonType.CANARY,
            DifferenceType.ERROR_RATE,
            ComparisonResult.UNCHANGED,
            200.0,
            200.0,
        ),
        (
            "svc-d",
            ComparisonType.BASELINE,
            DifferenceType.VOLUME,
            ComparisonResult.INCOMPARABLE,
            0.0,
            0.0,
        ),
    ]:
        engine.add_record(
            service_name=svc,
            comparison_type=ctype,
            difference_type=dtype,
            comparison_result=result,
            baseline_latency_ms=bscore,
            candidate_latency_ms=cscore,
            difference_score=abs(cscore - bscore) * 0.1,
        )
    report = engine.generate_report()
    assert isinstance(report, TraceComparisonReport)
    assert report.total_records == 4
    assert "temporal" in report.by_comparison_type


def test_get_stats() -> None:
    engine = TraceComparisonEngine()
    engine.add_record(comparison_result=ComparisonResult.DEGRADED, difference_score=50.0)
    engine.add_record(comparison_result=ComparisonResult.IMPROVED, difference_score=30.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "result_distribution" in stats


def test_clear_data() -> None:
    engine = TraceComparisonEngine()
    engine.add_record(service_name="svc-x", difference_score=10.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_compare_trace_profiles() -> None:
    engine = TraceComparisonEngine()
    engine.add_record(
        service_name="svc-a",
        baseline_latency_ms=100.0,
        candidate_latency_ms=200.0,
        baseline_error_rate=0.01,
        candidate_error_rate=0.02,
        comparison_result=ComparisonResult.DEGRADED,
    )
    engine.add_record(
        service_name="svc-a",
        baseline_latency_ms=150.0,
        candidate_latency_ms=180.0,
        baseline_error_rate=0.02,
        candidate_error_rate=0.01,
        comparison_result=ComparisonResult.IMPROVED,
    )
    engine.add_record(
        service_name="svc-b",
        baseline_latency_ms=200.0,
        candidate_latency_ms=600.0,
        baseline_error_rate=0.01,
        candidate_error_rate=0.08,
        comparison_result=ComparisonResult.DEGRADED,
    )
    results = engine.compare_trace_profiles()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "avg_latency_delta_ms" in results[0]
    assert "degraded_pct" in results[0]


def test_detect_behavioral_changes() -> None:
    engine = TraceComparisonEngine()
    engine.add_record(
        service_name="svc-a",
        comparison_result=ComparisonResult.DEGRADED,
        baseline_latency_ms=100.0,
        candidate_latency_ms=500.0,
        difference_score=80.0,
        difference_type=DifferenceType.PERFORMANCE,
        comparison_type=ComparisonType.TEMPORAL,
    )
    engine.add_record(
        service_name="svc-b",
        comparison_result=ComparisonResult.UNCHANGED,
        baseline_latency_ms=200.0,
        candidate_latency_ms=200.0,
        difference_score=0.0,
        difference_type=DifferenceType.STRUCTURAL,
        comparison_type=ComparisonType.VERSION,
    )
    results = engine.detect_behavioral_changes()
    assert isinstance(results, list)
    assert all(r["comparison_result"] in ("degraded", "improved") for r in results)


def test_rank_differences_by_significance() -> None:
    engine = TraceComparisonEngine()
    engine.add_record(
        service_name="svc-a",
        baseline_latency_ms=100.0,
        candidate_latency_ms=900.0,
        baseline_error_rate=0.01,
        candidate_error_rate=0.1,
        difference_score=50.0,
        comparison_result=ComparisonResult.DEGRADED,
    )
    engine.add_record(
        service_name="svc-b",
        baseline_latency_ms=200.0,
        candidate_latency_ms=210.0,
        baseline_error_rate=0.02,
        candidate_error_rate=0.02,
        difference_score=5.0,
        comparison_result=ComparisonResult.UNCHANGED,
    )
    results = engine.rank_differences_by_significance()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["significance_score"] >= results[-1]["significance_score"]
