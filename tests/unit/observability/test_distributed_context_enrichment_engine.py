"""Tests for DistributedContextEnrichmentEngine."""

from __future__ import annotations

from shieldops.observability.distributed_context_enrichment_engine import (
    ContextSource,
    DistributedContextAnalysis,
    DistributedContextEnrichmentEngine,
    DistributedContextRecord,
    DistributedContextReport,
    EnrichmentQuality,
    EnrichmentType,
)


def test_add_record() -> None:
    engine = DistributedContextEnrichmentEngine()
    rec = engine.add_record(
        trace_id="t1",
        service_name="svc-a",
        context_source=ContextSource.HEADERS,
        enrichment_type=EnrichmentType.TECHNICAL,
        enrichment_quality=EnrichmentQuality.COMPLETE,
        completeness_score=95.0,
        propagation_hops=3,
        missing_keys=0,
        stale_fields=1,
    )
    assert isinstance(rec, DistributedContextRecord)
    assert rec.trace_id == "t1"
    assert rec.completeness_score == 95.0


def test_process() -> None:
    engine = DistributedContextEnrichmentEngine()
    rec = engine.add_record(
        trace_id="t2",
        service_name="svc-b",
        enrichment_quality=EnrichmentQuality.MISSING,
        completeness_score=60.0,
        missing_keys=5,
        stale_fields=2,
    )
    result = engine.process(rec.id)
    assert isinstance(result, DistributedContextAnalysis)
    assert result.trace_id == "t2"
    assert result.gap_detected is True
    assert result.effective_completeness < 60.0


def test_process_not_found() -> None:
    engine = DistributedContextEnrichmentEngine()
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = DistributedContextEnrichmentEngine()
    for trace, src, etype, qual, score in [
        ("t1", ContextSource.HEADERS, EnrichmentType.TECHNICAL, EnrichmentQuality.COMPLETE, 95.0),
        ("t2", ContextSource.BAGGAGE, EnrichmentType.BUSINESS, EnrichmentQuality.PARTIAL, 70.0),
        ("t3", ContextSource.METADATA, EnrichmentType.SECURITY, EnrichmentQuality.STALE, 50.0),
        (
            "t4",
            ContextSource.ENVIRONMENT,
            EnrichmentType.COMPLIANCE,
            EnrichmentQuality.MISSING,
            10.0,
        ),
    ]:
        engine.add_record(
            trace_id=trace,
            context_source=src,
            enrichment_type=etype,
            enrichment_quality=qual,
            completeness_score=score,
        )
    report = engine.generate_report()
    assert isinstance(report, DistributedContextReport)
    assert report.total_records == 4
    assert "headers" in report.by_context_source


def test_get_stats() -> None:
    engine = DistributedContextEnrichmentEngine()
    engine.add_record(enrichment_quality=EnrichmentQuality.COMPLETE, completeness_score=90.0)
    engine.add_record(enrichment_quality=EnrichmentQuality.MISSING, completeness_score=10.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "quality_distribution" in stats


def test_clear_data() -> None:
    engine = DistributedContextEnrichmentEngine()
    engine.add_record(trace_id="t-x", completeness_score=50.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_evaluate_context_completeness() -> None:
    engine = DistributedContextEnrichmentEngine()
    engine.add_record(service_name="svc-a", completeness_score=90.0, missing_keys=0)
    engine.add_record(service_name="svc-b", completeness_score=40.0, missing_keys=5)
    engine.add_record(service_name="svc-a", completeness_score=85.0, missing_keys=1)
    results = engine.evaluate_context_completeness()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "avg_completeness_score" in results[0]
    assert "completeness_ok" in results[0]


def test_detect_context_propagation_gaps() -> None:
    engine = DistributedContextEnrichmentEngine()
    engine.add_record(propagation_hops=1, completeness_score=95.0, missing_keys=0)
    engine.add_record(propagation_hops=3, completeness_score=60.0, missing_keys=3)
    engine.add_record(propagation_hops=5, completeness_score=30.0, missing_keys=8)
    results = engine.detect_context_propagation_gaps()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "propagation_hops" in results[0]
    assert "gap_detected" in results[0]


def test_optimize_enrichment_pipeline() -> None:
    engine = DistributedContextEnrichmentEngine()
    engine.add_record(
        context_source=ContextSource.HEADERS,
        completeness_score=90.0,
        missing_keys=1,
        stale_fields=0,
    )
    engine.add_record(
        context_source=ContextSource.BAGGAGE,
        completeness_score=40.0,
        missing_keys=5,
        stale_fields=3,
    )
    engine.add_record(
        context_source=ContextSource.HEADERS,
        completeness_score=85.0,
        missing_keys=2,
        stale_fields=1,
    )
    results = engine.optimize_enrichment_pipeline()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "needs_optimization" in results[0]
    assert "avg_completeness" in results[0]
