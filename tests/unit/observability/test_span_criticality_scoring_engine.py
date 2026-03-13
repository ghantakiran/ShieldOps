"""Tests for SpanCriticalityScoringEngine."""

from __future__ import annotations

from shieldops.observability.span_criticality_scoring_engine import (
    CriticalityFactor,
    ScoreConfidence,
    SpanCriticalityAnalysis,
    SpanCriticalityRecord,
    SpanCriticalityReport,
    SpanCriticalityScoringEngine,
    SpanRole,
)


def test_add_record() -> None:
    engine = SpanCriticalityScoringEngine()
    rec = engine.add_record(
        span_id="sp1",
        trace_id="t1",
        service_name="svc-a",
        span_role=SpanRole.ENTRY,
        criticality_factor=CriticalityFactor.LATENCY_CONTRIBUTION,
        score_confidence=ScoreConfidence.HIGH,
        criticality_score=85.0,
        latency_ms=200.0,
        dependency_count=3,
        call_count=100,
    )
    assert isinstance(rec, SpanCriticalityRecord)
    assert rec.span_id == "sp1"
    assert rec.criticality_score == 85.0


def test_process() -> None:
    engine = SpanCriticalityScoringEngine()
    rec = engine.add_record(
        span_id="sp2",
        service_name="svc-b",
        score_confidence=ScoreConfidence.HIGH,
        criticality_score=90.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, SpanCriticalityAnalysis)
    assert result.span_id == "sp2"
    assert result.final_score > 0
    assert result.is_critical_path is True


def test_process_not_found() -> None:
    engine = SpanCriticalityScoringEngine()
    result = engine.process("no-such-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = SpanCriticalityScoringEngine()
    for span, role, conf, score in [
        ("sp1", SpanRole.ENTRY, ScoreConfidence.HIGH, 90.0),
        ("sp2", SpanRole.INTERNAL, ScoreConfidence.MEDIUM, 50.0),
        ("sp3", SpanRole.LEAF, ScoreConfidence.LOW, 30.0),
        ("sp4", SpanRole.ERROR, ScoreConfidence.UNCERTAIN, 80.0),
    ]:
        engine.add_record(
            span_id=span,
            span_role=role,
            score_confidence=conf,
            criticality_score=score,
        )
    report = engine.generate_report()
    assert isinstance(report, SpanCriticalityReport)
    assert report.total_records == 4
    assert "entry" in report.by_span_role


def test_get_stats() -> None:
    engine = SpanCriticalityScoringEngine()
    engine.add_record(span_role=SpanRole.ENTRY, criticality_score=60.0)
    engine.add_record(span_role=SpanRole.LEAF, criticality_score=20.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "role_distribution" in stats


def test_clear_data() -> None:
    engine = SpanCriticalityScoringEngine()
    engine.add_record(span_id="sp-x", criticality_score=10.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_score_span_criticality() -> None:
    engine = SpanCriticalityScoringEngine()
    engine.add_record(span_id="sp1", score_confidence=ScoreConfidence.HIGH, criticality_score=80.0)
    engine.add_record(span_id="sp2", score_confidence=ScoreConfidence.LOW, criticality_score=80.0)
    engine.add_record(
        span_id="sp3", score_confidence=ScoreConfidence.MEDIUM, criticality_score=60.0
    )
    results = engine.score_span_criticality()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["final_score"] >= results[-1]["final_score"]


def test_identify_critical_paths() -> None:
    engine = SpanCriticalityScoringEngine()
    engine.add_record(trace_id="trace-1", span_id="sp1", latency_ms=300.0, criticality_score=90.0)
    engine.add_record(trace_id="trace-1", span_id="sp2", latency_ms=100.0, criticality_score=40.0)
    engine.add_record(trace_id="trace-2", span_id="sp3", latency_ms=50.0, criticality_score=20.0)
    results = engine.identify_critical_paths()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "trace_id" in results[0]
    assert "is_critical" in results[0]


def test_rank_spans_by_importance() -> None:
    engine = SpanCriticalityScoringEngine()
    engine.add_record(span_id="sp1", criticality_score=50.0, dependency_count=5, call_count=1000)
    engine.add_record(span_id="sp2", criticality_score=90.0, dependency_count=1, call_count=10)
    engine.add_record(span_id="sp3", criticality_score=30.0, dependency_count=3, call_count=500)
    results = engine.rank_spans_by_importance()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert "importance_score" in results[0]
