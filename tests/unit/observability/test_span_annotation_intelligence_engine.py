"""Tests for SpanAnnotationIntelligenceEngine."""

from __future__ import annotations

from shieldops.observability.span_annotation_intelligence_engine import (
    AnnotationQuality,
    AnnotationSource,
    AnnotationType,
    SpanAnnotationAnalysis,
    SpanAnnotationIntelligenceEngine,
    SpanAnnotationRecord,
    SpanAnnotationReport,
)


def test_add_record() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    rec = engine.add_record(
        span_id="sp1",
        trace_id="t1",
        service_name="svc-a",
        annotation_type=AnnotationType.ERROR,
        annotation_source=AnnotationSource.AUTOMATIC,
        annotation_quality=AnnotationQuality.ACCURATE,
        coverage_score=90.0,
        missing_annotations=0,
        total_spans=100,
        annotated_spans=90,
    )
    assert isinstance(rec, SpanAnnotationRecord)
    assert rec.span_id == "sp1"
    assert rec.coverage_score == 90.0


def test_process() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    rec = engine.add_record(
        span_id="sp2",
        service_name="svc-b",
        annotation_quality=AnnotationQuality.ACCURATE,
        coverage_score=80.0,
        missing_annotations=3,
    )
    result = engine.process(rec.id)
    assert isinstance(result, SpanAnnotationAnalysis)
    assert result.span_id == "sp2"
    assert result.effective_coverage == 80.0
    assert result.has_missing is True


def test_process_not_found() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    result = engine.process("no-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    for span, atype, src, qual, score in [
        ("sp1", AnnotationType.ERROR, AnnotationSource.AUTOMATIC, AnnotationQuality.ACCURATE, 90.0),
        (
            "sp2",
            AnnotationType.WARNING,
            AnnotationSource.MANUAL,
            AnnotationQuality.APPROXIMATE,
            70.0,
        ),
        ("sp3", AnnotationType.INFO, AnnotationSource.ML_INFERRED, AnnotationQuality.STALE, 50.0),
        ("sp4", AnnotationType.CUSTOM, AnnotationSource.POLICY, AnnotationQuality.INCORRECT, 30.0),
    ]:
        engine.add_record(
            span_id=span,
            annotation_type=atype,
            annotation_source=src,
            annotation_quality=qual,
            coverage_score=score,
        )
    report = engine.generate_report()
    assert isinstance(report, SpanAnnotationReport)
    assert report.total_records == 4
    assert "error" in report.by_annotation_type


def test_get_stats() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    engine.add_record(annotation_type=AnnotationType.ERROR, coverage_score=80.0)
    engine.add_record(annotation_type=AnnotationType.INFO, coverage_score=60.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "annotation_type_distribution" in stats


def test_clear_data() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    engine.add_record(span_id="sp-x", coverage_score=50.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_evaluate_annotation_coverage() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    engine.add_record(
        service_name="svc-a", coverage_score=90.0, total_spans=100, annotated_spans=90
    )
    engine.add_record(
        service_name="svc-b", coverage_score=40.0, total_spans=100, annotated_spans=40
    )
    engine.add_record(service_name="svc-a", coverage_score=85.0, total_spans=50, annotated_spans=43)
    results = engine.evaluate_annotation_coverage()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "annotation_rate_pct" in results[0]
    assert results[0]["avg_coverage_score"] >= results[-1]["avg_coverage_score"]


def test_detect_missing_annotations() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    engine.add_record(span_id="sp1", missing_annotations=5, coverage_score=60.0)
    engine.add_record(span_id="sp2", missing_annotations=0, coverage_score=100.0)
    engine.add_record(span_id="sp3", missing_annotations=10, coverage_score=40.0)
    results = engine.detect_missing_annotations()
    assert isinstance(results, list)
    assert all(r["missing_annotations"] > 0 for r in results)
    assert results[0]["missing_annotations"] >= results[-1]["missing_annotations"]


def test_optimize_annotation_rules() -> None:
    engine = SpanAnnotationIntelligenceEngine()
    engine.add_record(
        annotation_source=AnnotationSource.AUTOMATIC, coverage_score=90.0, missing_annotations=1
    )
    engine.add_record(
        annotation_source=AnnotationSource.ML_INFERRED, coverage_score=50.0, missing_annotations=8
    )
    engine.add_record(
        annotation_source=AnnotationSource.AUTOMATIC, coverage_score=85.0, missing_annotations=2
    )
    results = engine.optimize_annotation_rules()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "needs_optimization" in results[0]
    assert "avg_coverage" in results[0]
