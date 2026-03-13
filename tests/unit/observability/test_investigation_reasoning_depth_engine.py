"""Tests for InvestigationReasoningDepthEngine."""

from __future__ import annotations

from shieldops.observability.investigation_reasoning_depth_engine import (
    BreakdownPoint,
    InvestigationReasoningDepthAnalysis,
    InvestigationReasoningDepthEngine,
    InvestigationReasoningDepthRecord,
    InvestigationReasoningDepthReport,
    InvestigationStyle,
    ReasoningDepth,
)


def test_add_record() -> None:
    engine = InvestigationReasoningDepthEngine()
    rec = engine.add_record(
        investigation_id="inv-001",
        reasoning_depth=ReasoningDepth.DEEP,
        breakdown_point=BreakdownPoint.DATA_GAP,
        investigation_style=InvestigationStyle.ITERATIVE,
        depth_score=0.85,
        steps_taken=12,
        resolved=True,
    )
    assert isinstance(rec, InvestigationReasoningDepthRecord)
    assert rec.investigation_id == "inv-001"
    assert rec.steps_taken == 12


def test_process() -> None:
    engine = InvestigationReasoningDepthEngine()
    rec = engine.add_record(
        investigation_id="inv-002",
        reasoning_depth=ReasoningDepth.SHALLOW,
        breakdown_point=BreakdownPoint.TIMEOUT,
        depth_score=0.2,
        steps_taken=2,
        resolved=False,
    )
    result = engine.process(rec.id)
    assert isinstance(result, InvestigationReasoningDepthAnalysis)
    assert result.investigation_id == "inv-002"
    assert result.breakdown_detected is True


def test_process_not_found() -> None:
    engine = InvestigationReasoningDepthEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = InvestigationReasoningDepthEngine()
    for inv_id, depth, bp, style, score, resolved in [
        (
            "i1",
            ReasoningDepth.SHALLOW,
            BreakdownPoint.DATA_GAP,
            InvestigationStyle.LINEAR,
            0.2,
            False,
        ),
        (
            "i2",
            ReasoningDepth.MODERATE,
            BreakdownPoint.AMBIGUITY,
            InvestigationStyle.BRANCHING,
            0.5,
            True,
        ),
        (
            "i3",
            ReasoningDepth.DEEP,
            BreakdownPoint.TIMEOUT,
            InvestigationStyle.ITERATIVE,
            0.75,
            True,
        ),
        (
            "i4",
            ReasoningDepth.EXHAUSTIVE,
            BreakdownPoint.COMPLEXITY_LIMIT,
            InvestigationStyle.PARALLEL,
            0.9,
            True,
        ),
    ]:
        engine.add_record(
            investigation_id=inv_id,
            reasoning_depth=depth,
            breakdown_point=bp,
            investigation_style=style,
            depth_score=score,
            resolved=resolved,
        )
    report = engine.generate_report()
    assert isinstance(report, InvestigationReasoningDepthReport)
    assert report.total_records == 4
    assert "shallow" in report.by_reasoning_depth
    assert report.resolution_rate > 0


def test_get_stats() -> None:
    engine = InvestigationReasoningDepthEngine()
    engine.add_record(reasoning_depth=ReasoningDepth.DEEP, depth_score=0.8)
    engine.add_record(reasoning_depth=ReasoningDepth.SHALLOW, depth_score=0.2)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "reasoning_depth_distribution" in stats


def test_clear_data() -> None:
    engine = InvestigationReasoningDepthEngine()
    engine.add_record(investigation_id="inv-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_measure_reasoning_depth() -> None:
    engine = InvestigationReasoningDepthEngine()
    engine.add_record(
        investigation_id="inv-A",
        reasoning_depth=ReasoningDepth.DEEP,
        depth_score=0.9,
        steps_taken=10,
    )
    engine.add_record(
        investigation_id="inv-A",
        reasoning_depth=ReasoningDepth.EXHAUSTIVE,
        depth_score=0.95,
        steps_taken=15,
    )
    engine.add_record(
        investigation_id="inv-B",
        reasoning_depth=ReasoningDepth.SHALLOW,
        depth_score=0.2,
        steps_taken=2,
    )
    results = engine.measure_reasoning_depth()
    assert isinstance(results, list)
    assert results[0]["avg_depth_score"] >= results[-1]["avg_depth_score"]
    assert "total_steps" in results[0]


def test_identify_reasoning_breakdowns() -> None:
    engine = InvestigationReasoningDepthEngine()
    engine.add_record(
        investigation_id="inv-broken",
        reasoning_depth=ReasoningDepth.SHALLOW,
        breakdown_point=BreakdownPoint.TIMEOUT,
        depth_score=0.1,
        resolved=False,
    )
    engine.add_record(
        investigation_id="inv-ok",
        reasoning_depth=ReasoningDepth.DEEP,
        depth_score=0.9,
        resolved=True,
    )
    results = engine.identify_reasoning_breakdowns()
    assert isinstance(results, list)
    assert any(r["investigation_id"] == "inv-broken" for r in results)
    assert all(r["depth_score"] <= 0.5 for r in results)


def test_correlate_depth_with_resolution() -> None:
    engine = InvestigationReasoningDepthEngine()
    engine.add_record(reasoning_depth=ReasoningDepth.DEEP, depth_score=0.8, resolved=True)
    engine.add_record(reasoning_depth=ReasoningDepth.DEEP, depth_score=0.85, resolved=True)
    engine.add_record(reasoning_depth=ReasoningDepth.SHALLOW, depth_score=0.2, resolved=False)
    results = engine.correlate_depth_with_resolution()
    assert isinstance(results, list)
    deep_entry = next((r for r in results if r["reasoning_depth"] == "deep"), None)
    assert deep_entry is not None
    assert deep_entry["resolution_rate"] == 1.0
