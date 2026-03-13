"""Tests for ToolUseInterleavingEngine."""

from __future__ import annotations

from shieldops.observability.tool_use_interleaving_engine import (
    InterleavingPattern,
    ToolCallOutcome,
    ToolUseInterleavingAnalysis,
    ToolUseInterleavingEngine,
    ToolUseInterleavingRecord,
    ToolUseInterleavingReport,
    TurnType,
)


def test_add_record() -> None:
    engine = ToolUseInterleavingEngine()
    rec = engine.add_record(
        session_id="sess-001",
        turn_type=TurnType.TOOL_CALL,
        interleaving_pattern=InterleavingPattern.ALTERNATING,
        tool_call_outcome=ToolCallOutcome.DECISIVE,
        information_gain=0.85,
        turn_duration_ms=120.0,
        tool_name="get_metrics",
    )
    assert isinstance(rec, ToolUseInterleavingRecord)
    assert rec.session_id == "sess-001"
    assert rec.information_gain == 0.85


def test_process() -> None:
    engine = ToolUseInterleavingEngine()
    rec = engine.add_record(
        session_id="sess-002",
        turn_type=TurnType.TOOL_CALL,
        tool_call_outcome=ToolCallOutcome.DECISIVE,
        information_gain=0.9,
        turn_duration_ms=100.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, ToolUseInterleavingAnalysis)
    assert result.session_id == "sess-002"
    assert result.roi_score > 0


def test_process_not_found() -> None:
    engine = ToolUseInterleavingEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = ToolUseInterleavingEngine()
    for sid, tt, ip, tco, gain in [
        (
            "s1",
            TurnType.REASONING,
            InterleavingPattern.REASON_FIRST,
            ToolCallOutcome.INFORMATIVE,
            0.6,
        ),
        ("s2", TurnType.TOOL_CALL, InterleavingPattern.TOOL_FIRST, ToolCallOutcome.DECISIVE, 0.9),
        ("s3", TurnType.SYNTHESIS, InterleavingPattern.ALTERNATING, ToolCallOutcome.REDUNDANT, 0.2),
        ("s4", TurnType.VERIFICATION, InterleavingPattern.ADAPTIVE, ToolCallOutcome.FAILED, 0.0),
    ]:
        engine.add_record(
            session_id=sid,
            turn_type=tt,
            interleaving_pattern=ip,
            tool_call_outcome=tco,
            information_gain=gain,
        )
    report = engine.generate_report()
    assert isinstance(report, ToolUseInterleavingReport)
    assert report.total_records == 4
    assert "reasoning" in report.by_turn_type


def test_get_stats() -> None:
    engine = ToolUseInterleavingEngine()
    engine.add_record(turn_type=TurnType.REASONING, information_gain=0.5)
    engine.add_record(turn_type=TurnType.TOOL_CALL, information_gain=0.8)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "turn_type_distribution" in stats


def test_clear_data() -> None:
    engine = ToolUseInterleavingEngine()
    engine.add_record(session_id="s-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_analyze_interleaving_pattern() -> None:
    engine = ToolUseInterleavingEngine()
    engine.add_record(
        session_id="sess-A",
        interleaving_pattern=InterleavingPattern.ALTERNATING,
        information_gain=0.7,
    )
    engine.add_record(
        session_id="sess-A",
        interleaving_pattern=InterleavingPattern.ALTERNATING,
        information_gain=0.8,
    )
    engine.add_record(
        session_id="sess-B",
        interleaving_pattern=InterleavingPattern.TOOL_FIRST,
        information_gain=0.5,
    )
    results = engine.analyze_interleaving_pattern()
    assert isinstance(results, list)
    assert len(results) == 2
    assert "dominant_pattern" in results[0]


def test_recommend_next_action() -> None:
    engine = ToolUseInterleavingEngine()
    engine.add_record(
        session_id="sess-A",
        turn_type=TurnType.REASONING,
        tool_call_outcome=ToolCallOutcome.INFORMATIVE,
    )
    engine.add_record(
        session_id="sess-B",
        turn_type=TurnType.TOOL_CALL,
        tool_call_outcome=ToolCallOutcome.DECISIVE,
    )
    results = engine.recommend_next_action()
    assert isinstance(results, list)
    sess_a = next(r for r in results if r["session_id"] == "sess-A")
    assert sess_a["recommended_next"] == "tool_call"
    sess_b = next(r for r in results if r["session_id"] == "sess-B")
    assert sess_b["recommended_next"] == "synthesis"


def test_compute_tool_call_roi() -> None:
    engine = ToolUseInterleavingEngine()
    engine.add_record(
        session_id="s1",
        turn_type=TurnType.TOOL_CALL,
        tool_name="get_logs",
        tool_call_outcome=ToolCallOutcome.DECISIVE,
        information_gain=0.9,
        turn_duration_ms=50.0,
    )
    engine.add_record(
        session_id="s2",
        turn_type=TurnType.TOOL_CALL,
        tool_name="get_metrics",
        tool_call_outcome=ToolCallOutcome.REDUNDANT,
        information_gain=0.1,
        turn_duration_ms=200.0,
    )
    results = engine.compute_tool_call_roi()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["roi_score"] >= results[-1]["roi_score"]
