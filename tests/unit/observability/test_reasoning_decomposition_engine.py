"""Tests for ReasoningDecompositionEngine."""

from __future__ import annotations

from shieldops.observability.reasoning_decomposition_engine import (
    CompositionStrategy,
    DecompositionMethod,
    ReasoningDecompositionAnalysis,
    ReasoningDecompositionEngine,
    ReasoningDecompositionRecord,
    ReasoningDecompositionReport,
    SubQueryComplexity,
)


def test_add_record() -> None:
    engine = ReasoningDecompositionEngine()
    rec = engine.add_record(
        investigation_id="inv-001",
        decomposition_method=DecompositionMethod.HIERARCHICAL,
        sub_query_complexity=SubQueryComplexity.SIMPLE,
        composition_strategy=CompositionStrategy.MERGE,
        sub_query_count=3,
        resolution_score=0.85,
        sub_query_text="check cpu anomalies",
    )
    assert isinstance(rec, ReasoningDecompositionRecord)
    assert rec.investigation_id == "inv-001"
    assert rec.sub_query_count == 3


def test_process() -> None:
    engine = ReasoningDecompositionEngine()
    rec = engine.add_record(
        investigation_id="inv-002",
        decomposition_method=DecompositionMethod.HYBRID,
        resolution_score=0.9,
        sub_query_count=4,
    )
    result = engine.process(rec.id)
    assert isinstance(result, ReasoningDecompositionAnalysis)
    assert result.investigation_id == "inv-002"
    assert result.is_optimal is True


def test_process_not_found() -> None:
    engine = ReasoningDecompositionEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = ReasoningDecompositionEngine()
    for inv_id, dm, sqc, cs, count, score in [
        (
            "i1",
            DecompositionMethod.HIERARCHICAL,
            SubQueryComplexity.ATOMIC,
            CompositionStrategy.MERGE,
            2,
            0.9,
        ),
        (
            "i2",
            DecompositionMethod.PARALLEL,
            SubQueryComplexity.SIMPLE,
            CompositionStrategy.CHAIN,
            4,
            0.7,
        ),
        (
            "i3",
            DecompositionMethod.SEQUENTIAL,
            SubQueryComplexity.COMPOUND,
            CompositionStrategy.VOTE,
            3,
            0.5,
        ),
        (
            "i4",
            DecompositionMethod.HYBRID,
            SubQueryComplexity.RECURSIVE,
            CompositionStrategy.WEIGHTED,
            6,
            0.85,
        ),
    ]:
        engine.add_record(
            investigation_id=inv_id,
            decomposition_method=dm,
            sub_query_complexity=sqc,
            composition_strategy=cs,
            sub_query_count=count,
            resolution_score=score,
        )
    report = engine.generate_report()
    assert isinstance(report, ReasoningDecompositionReport)
    assert report.total_records == 4
    assert "hierarchical" in report.by_decomposition_method


def test_get_stats() -> None:
    engine = ReasoningDecompositionEngine()
    engine.add_record(decomposition_method=DecompositionMethod.PARALLEL, resolution_score=0.8)
    engine.add_record(decomposition_method=DecompositionMethod.SEQUENTIAL, resolution_score=0.5)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "decomposition_method_distribution" in stats


def test_clear_data() -> None:
    engine = ReasoningDecompositionEngine()
    engine.add_record(investigation_id="inv-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_decompose_investigation() -> None:
    engine = ReasoningDecompositionEngine()
    engine.add_record(
        investigation_id="inv-A",
        decomposition_method=DecompositionMethod.HIERARCHICAL,
        sub_query_count=3,
        resolution_score=0.9,
    )
    engine.add_record(
        investigation_id="inv-A",
        decomposition_method=DecompositionMethod.PARALLEL,
        sub_query_count=2,
        resolution_score=0.85,
    )
    engine.add_record(
        investigation_id="inv-B",
        decomposition_method=DecompositionMethod.SEQUENTIAL,
        sub_query_count=1,
        resolution_score=0.4,
    )
    results = engine.decompose_investigation()
    assert isinstance(results, list)
    inv_a = next(r for r in results if r["investigation_id"] == "inv-A")
    assert inv_a["total_sub_queries"] == 5
    assert results[0]["avg_resolution_score"] >= results[-1]["avg_resolution_score"]


def test_compose_sub_results() -> None:
    engine = ReasoningDecompositionEngine()
    engine.add_record(
        investigation_id="inv-A",
        composition_strategy=CompositionStrategy.WEIGHTED,
        sub_query_count=3,
        resolution_score=0.9,
    )
    engine.add_record(
        investigation_id="inv-A",
        composition_strategy=CompositionStrategy.WEIGHTED,
        sub_query_count=1,
        resolution_score=0.5,
    )
    results = engine.compose_sub_results()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "composed_score" in results[0]
    assert "dominant_strategy" in results[0]


def test_optimize_decomposition_strategy() -> None:
    engine = ReasoningDecompositionEngine()
    engine.add_record(decomposition_method=DecompositionMethod.HYBRID, resolution_score=0.9)
    engine.add_record(decomposition_method=DecompositionMethod.HYBRID, resolution_score=0.85)
    engine.add_record(decomposition_method=DecompositionMethod.SEQUENTIAL, resolution_score=0.4)
    results = engine.optimize_decomposition_strategy()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["avg_resolution_score"] >= results[-1]["avg_resolution_score"]
