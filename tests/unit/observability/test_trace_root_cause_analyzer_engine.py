"""Tests for TraceRootCauseAnalyzerEngine."""

from __future__ import annotations

from shieldops.observability.trace_root_cause_analyzer_engine import (
    AnalysisDepth,
    CauseConfidence,
    RootCauseType,
    TraceRootCauseAnalysis,
    TraceRootCauseAnalyzerEngine,
    TraceRootCauseRecord,
    TraceRootCauseReport,
)


def test_add_record() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    rec = engine.add_record(
        trace_id="t1",
        service_name="svc-a",
        root_cause_type=RootCauseType.SERVICE_ERROR,
        analysis_depth=AnalysisDepth.DEEP,
        cause_confidence=CauseConfidence.CONFIRMED,
        likelihood_score=95.0,
        affected_spans=5,
        error_message="connection refused",
    )
    assert isinstance(rec, TraceRootCauseRecord)
    assert rec.trace_id == "t1"
    assert rec.likelihood_score == 95.0


def test_process() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    rec = engine.add_record(
        trace_id="t2",
        service_name="svc-b",
        root_cause_type=RootCauseType.NETWORK_ISSUE,
        cause_confidence=CauseConfidence.CONFIRMED,
        likelihood_score=80.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, TraceRootCauseAnalysis)
    assert result.trace_id == "t2"
    assert result.is_confirmed is True
    assert result.weighted_score > 0


def test_process_not_found() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    result = engine.process("missing-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    for trace, cause, depth, conf, score in [
        ("t1", RootCauseType.SERVICE_ERROR, AnalysisDepth.DEEP, CauseConfidence.CONFIRMED, 90.0),
        ("t2", RootCauseType.NETWORK_ISSUE, AnalysisDepth.MODERATE, CauseConfidence.PROBABLE, 70.0),
        ("t3", RootCauseType.RESOURCE_LIMIT, AnalysisDepth.SHALLOW, CauseConfidence.POSSIBLE, 50.0),
        (
            "t4",
            RootCauseType.CONFIGURATION,
            AnalysisDepth.EXHAUSTIVE,
            CauseConfidence.SPECULATIVE,
            20.0,
        ),
    ]:
        engine.add_record(
            trace_id=trace,
            root_cause_type=cause,
            analysis_depth=depth,
            cause_confidence=conf,
            likelihood_score=score,
        )
    report = engine.generate_report()
    assert isinstance(report, TraceRootCauseReport)
    assert report.total_records == 4
    assert "service_error" in report.by_root_cause_type


def test_get_stats() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    engine.add_record(root_cause_type=RootCauseType.SERVICE_ERROR, likelihood_score=80.0)
    engine.add_record(root_cause_type=RootCauseType.NETWORK_ISSUE, likelihood_score=60.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "cause_type_distribution" in stats


def test_clear_data() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    engine.add_record(trace_id="t-x", likelihood_score=30.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_analyze_root_causes() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    engine.add_record(
        service_name="svc-a", likelihood_score=80.0, root_cause_type=RootCauseType.SERVICE_ERROR
    )
    engine.add_record(
        service_name="svc-b", likelihood_score=40.0, root_cause_type=RootCauseType.NETWORK_ISSUE
    )
    engine.add_record(
        service_name="svc-a", likelihood_score=60.0, root_cause_type=RootCauseType.RESOURCE_LIMIT
    )
    results = engine.analyze_root_causes()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "service_name" in results[0]
    assert "avg_likelihood" in results[0]


def test_correlate_cause_patterns() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    engine.add_record(
        root_cause_type=RootCauseType.SERVICE_ERROR,
        analysis_depth=AnalysisDepth.DEEP,
        likelihood_score=70.0,
    )
    engine.add_record(
        root_cause_type=RootCauseType.NETWORK_ISSUE,
        analysis_depth=AnalysisDepth.MODERATE,
        likelihood_score=50.0,
    )
    engine.add_record(
        root_cause_type=RootCauseType.SERVICE_ERROR,
        analysis_depth=AnalysisDepth.DEEP,
        likelihood_score=90.0,
    )
    results = engine.correlate_cause_patterns()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "pattern" in results[0]
    assert "count" in results[0]


def test_rank_causes_by_likelihood() -> None:
    engine = TraceRootCauseAnalyzerEngine()
    engine.add_record(
        trace_id="t1",
        cause_confidence=CauseConfidence.CONFIRMED,
        likelihood_score=80.0,
    )
    engine.add_record(
        trace_id="t2",
        cause_confidence=CauseConfidence.SPECULATIVE,
        likelihood_score=80.0,
    )
    engine.add_record(
        trace_id="t3",
        cause_confidence=CauseConfidence.PROBABLE,
        likelihood_score=60.0,
    )
    results = engine.rank_causes_by_likelihood()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["weighted_likelihood"] >= results[-1]["weighted_likelihood"]
