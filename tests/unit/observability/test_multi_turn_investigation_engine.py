"""Tests for MultiTurnInvestigationEngine."""

from __future__ import annotations

from shieldops.observability.multi_turn_investigation_engine import (
    InvestigationState,
    MultiTurnInvestigationAnalysis,
    MultiTurnInvestigationEngine,
    MultiTurnInvestigationRecord,
    MultiTurnInvestigationReport,
    TurnOutcome,
    TurnPhase,
)


def test_add_record() -> None:
    engine = MultiTurnInvestigationEngine()
    rec = engine.add_record(
        investigation_id="inv-001",
        turn_phase=TurnPhase.DATA_GATHERING,
        investigation_state=InvestigationState.NARROWING,
        turn_outcome=TurnOutcome.PROGRESS,
        information_gain=0.6,
        turn_index=2,
        hypothesis="memory leak in service-A",
    )
    assert isinstance(rec, MultiTurnInvestigationRecord)
    assert rec.investigation_id == "inv-001"
    assert rec.turn_index == 2


def test_process() -> None:
    engine = MultiTurnInvestigationEngine()
    rec = engine.add_record(
        investigation_id="inv-002",
        turn_phase=TurnPhase.ANALYSIS,
        investigation_state=InvestigationState.OPEN,
        turn_outcome=TurnOutcome.PROGRESS,
        information_gain=0.4,
        turn_index=1,
    )
    result = engine.process(rec.id)
    assert isinstance(result, MultiTurnInvestigationAnalysis)
    assert result.investigation_id == "inv-002"
    assert result.should_continue is True


def test_process_resolved() -> None:
    engine = MultiTurnInvestigationEngine()
    rec = engine.add_record(
        investigation_id="inv-resolved",
        investigation_state=InvestigationState.RESOLVED,
        turn_outcome=TurnOutcome.PROGRESS,
    )
    result = engine.process(rec.id)
    assert isinstance(result, MultiTurnInvestigationAnalysis)
    assert result.should_continue is False


def test_process_not_found() -> None:
    engine = MultiTurnInvestigationEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = MultiTurnInvestigationEngine()
    for inv_id, tp, inv_state, to, gain in [
        ("i1", TurnPhase.HYPOTHESIS, InvestigationState.OPEN, TurnOutcome.PROGRESS, 0.3),
        (
            "i2",
            TurnPhase.DATA_GATHERING,
            InvestigationState.NARROWING,
            TurnOutcome.BREAKTHROUGH,
            0.8,
        ),
        ("i3", TurnPhase.ANALYSIS, InvestigationState.VALIDATING, TurnOutcome.DEAD_END, 0.1),
        ("i4", TurnPhase.SYNTHESIS, InvestigationState.RESOLVED, TurnOutcome.PROGRESS, 0.9),
    ]:
        engine.add_record(
            investigation_id=inv_id,
            turn_phase=tp,
            investigation_state=inv_state,
            turn_outcome=to,
            information_gain=gain,
        )
    report = engine.generate_report()
    assert isinstance(report, MultiTurnInvestigationReport)
    assert report.total_records == 4
    assert "hypothesis" in report.by_turn_phase
    assert len(report.resolved_investigations) >= 1


def test_get_stats() -> None:
    engine = MultiTurnInvestigationEngine()
    engine.add_record(turn_phase=TurnPhase.HYPOTHESIS, information_gain=0.3)
    engine.add_record(turn_phase=TurnPhase.ANALYSIS, information_gain=0.7)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "turn_phase_distribution" in stats


def test_clear_data() -> None:
    engine = MultiTurnInvestigationEngine()
    engine.add_record(investigation_id="inv-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_execute_investigation_turn() -> None:
    engine = MultiTurnInvestigationEngine()
    engine.add_record(investigation_id="inv-A", turn_index=1, information_gain=0.3)
    engine.add_record(investigation_id="inv-A", turn_index=2, information_gain=0.5)
    engine.add_record(investigation_id="inv-B", turn_index=1, information_gain=0.9)
    results = engine.execute_investigation_turn()
    assert isinstance(results, list)
    inv_b = next(r for r in results if r["investigation_id"] == "inv-B")
    assert inv_b["total_information_gain"] == 0.9
    assert results[0]["total_information_gain"] >= results[-1]["total_information_gain"]


def test_determine_turn_continuation() -> None:
    engine = MultiTurnInvestigationEngine()
    engine.add_record(
        investigation_id="open-inv",
        investigation_state=InvestigationState.OPEN,
        turn_outcome=TurnOutcome.PROGRESS,
        turn_index=1,
    )
    engine.add_record(
        investigation_id="resolved-inv",
        investigation_state=InvestigationState.RESOLVED,
        turn_outcome=TurnOutcome.PROGRESS,
        turn_index=1,
    )
    results = engine.determine_turn_continuation()
    assert isinstance(results, list)
    open_r = next(r for r in results if r["investigation_id"] == "open-inv")
    resolved_r = next(r for r in results if r["investigation_id"] == "resolved-inv")
    assert open_r["should_continue"] is True
    assert resolved_r["should_continue"] is False


def test_compute_turn_information_gain() -> None:
    engine = MultiTurnInvestigationEngine()
    engine.add_record(
        investigation_id="inv-X",
        turn_index=1,
        information_gain=0.3,
        turn_outcome=TurnOutcome.PROGRESS,
    )
    engine.add_record(
        investigation_id="inv-X",
        turn_index=2,
        information_gain=0.7,
        turn_outcome=TurnOutcome.BREAKTHROUGH,
    )
    results = engine.compute_turn_information_gain()
    assert isinstance(results, list)
    inv_x = next(r for r in results if r["investigation_id"] == "inv-X")
    assert inv_x["cumulative_gain"] == 1.0
    assert 2 in inv_x["breakthrough_turns"]
