"""Tests for TraceCompletenessVerificationEngine."""

from __future__ import annotations

from shieldops.observability.trace_completeness_verification_engine import (
    CompletenessType,
    IntegrityStatus,
    TraceCompletenessAnalysis,
    TraceCompletenessRecord,
    TraceCompletenessReport,
    TraceCompletenessVerificationEngine,
    VerificationMethod,
)


def test_add_record() -> None:
    engine = TraceCompletenessVerificationEngine()
    rec = engine.add_record(
        trace_id="t1",
        service_name="svc-a",
        completeness_type=CompletenessType.FULL,
        verification_method=VerificationMethod.SPAN_COUNT,
        integrity_status=IntegrityStatus.VALID,
        completeness_score=98.0,
        expected_spans=20,
        actual_spans=20,
        missing_spans=0,
        orphaned_spans=0,
    )
    assert isinstance(rec, TraceCompletenessRecord)
    assert rec.trace_id == "t1"
    assert rec.completeness_score == 98.0


def test_process() -> None:
    engine = TraceCompletenessVerificationEngine()
    rec = engine.add_record(
        trace_id="t2",
        service_name="svc-b",
        completeness_type=CompletenessType.FULL,
        integrity_status=IntegrityStatus.VALID,
        completeness_score=95.0,
        missing_spans=0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, TraceCompletenessAnalysis)
    assert result.trace_id == "t2"
    assert result.is_complete is True
    assert result.effective_score == 95.0


def test_process_not_found() -> None:
    engine = TraceCompletenessVerificationEngine()
    result = engine.process("unknown-trace")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = TraceCompletenessVerificationEngine()
    for trace, ctype, vmethod, integrity, score in [
        ("t1", CompletenessType.FULL, VerificationMethod.SPAN_COUNT, IntegrityStatus.VALID, 100.0),
        (
            "t2",
            CompletenessType.PARTIAL,
            VerificationMethod.PARENT_CHECK,
            IntegrityStatus.INCOMPLETE,
            60.0,
        ),
        (
            "t3",
            CompletenessType.FRAGMENTED,
            VerificationMethod.DURATION_CHECK,
            IntegrityStatus.CORRUPTED,
            30.0,
        ),
        (
            "t4",
            CompletenessType.ORPHANED,
            VerificationMethod.SEMANTIC,
            IntegrityStatus.SUSPICIOUS,
            40.0,
        ),
    ]:
        engine.add_record(
            trace_id=trace,
            completeness_type=ctype,
            verification_method=vmethod,
            integrity_status=integrity,
            completeness_score=score,
        )
    report = engine.generate_report()
    assert isinstance(report, TraceCompletenessReport)
    assert report.total_records == 4
    assert "full" in report.by_completeness_type


def test_get_stats() -> None:
    engine = TraceCompletenessVerificationEngine()
    engine.add_record(completeness_type=CompletenessType.FULL, completeness_score=100.0)
    engine.add_record(completeness_type=CompletenessType.PARTIAL, completeness_score=60.0)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "completeness_type_distribution" in stats


def test_clear_data() -> None:
    engine = TraceCompletenessVerificationEngine()
    engine.add_record(trace_id="t-x", completeness_score=50.0)
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_verify_trace_completeness() -> None:
    engine = TraceCompletenessVerificationEngine()
    engine.add_record(
        trace_id="trace-1",
        completeness_score=95.0,
        expected_spans=10,
        actual_spans=10,
        missing_spans=0,
    )
    engine.add_record(
        trace_id="trace-2",
        completeness_score=60.0,
        expected_spans=10,
        actual_spans=6,
        missing_spans=4,
    )
    engine.add_record(
        trace_id="trace-1",
        completeness_score=98.0,
        expected_spans=10,
        actual_spans=10,
        missing_spans=0,
    )
    results = engine.verify_trace_completeness()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "avg_completeness_score" in results[0]
    assert "is_complete" in results[0]


def test_detect_missing_spans() -> None:
    engine = TraceCompletenessVerificationEngine()
    engine.add_record(trace_id="t1", missing_spans=5, orphaned_spans=2, completeness_score=60.0)
    engine.add_record(trace_id="t2", missing_spans=0, orphaned_spans=0, completeness_score=100.0)
    engine.add_record(trace_id="t3", missing_spans=10, orphaned_spans=0, completeness_score=30.0)
    results = engine.detect_missing_spans()
    assert isinstance(results, list)
    assert all(r["missing_spans"] > 0 or r["orphaned_spans"] > 0 for r in results)
    assert results[0]["missing_spans"] >= results[-1]["missing_spans"]


def test_rank_traces_by_completeness() -> None:
    engine = TraceCompletenessVerificationEngine()
    engine.add_record(
        trace_id="t1", completeness_score=100.0, integrity_status=IntegrityStatus.VALID
    )
    engine.add_record(
        trace_id="t2", completeness_score=80.0, integrity_status=IntegrityStatus.CORRUPTED
    )
    engine.add_record(
        trace_id="t3", completeness_score=70.0, integrity_status=IntegrityStatus.INCOMPLETE
    )
    results = engine.rank_traces_by_completeness()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["effective_score"] >= results[-1]["effective_score"]
