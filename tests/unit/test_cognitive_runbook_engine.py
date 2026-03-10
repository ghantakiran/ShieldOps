"""Tests for CognitiveRunbookEngine."""

from __future__ import annotations

from shieldops.operations.cognitive_runbook_engine import (
    CognitiveRunbookEngine,
    EvolutionAction,
    LearningSignal,
    RunbookOutcome,
)


def _engine(**kw) -> CognitiveRunbookEngine:
    return CognitiveRunbookEngine(**kw)


class TestEnums:
    def test_runbook_outcome(self):
        assert RunbookOutcome.SUCCESS == "success"

    def test_learning_signal(self):
        assert LearningSignal.POSITIVE == "positive"

    def test_evolution_action(self):
        assert EvolutionAction.ADD_STEP == "add_step"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(runbook_id="rb-1", step_name="step-a")
        assert rec.runbook_id == "rb-1"
        assert rec.step_name == "step-a"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                runbook_id=f"rb-{i}",
                step_name="step",
            )
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(runbook_id="rb-1", step_name="step-a")
        result = eng.process("rb-1")
        assert isinstance(result, dict)
        assert result["runbook_id"] == "rb-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestSuggestModifications:
    def test_basic(self):
        eng = _engine()
        eng.add_record(runbook_id="rb-1", step_name="step-a")
        result = eng.suggest_modifications("rb-1")
        assert isinstance(result, list)


class TestComputeEffectiveness:
    def test_basic(self):
        eng = _engine()
        eng.add_record(runbook_id="rb-1", step_name="step-a")
        result = eng.compute_effectiveness("rb-1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(runbook_id="rb-1", step_name="step-a")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(runbook_id="rb-1", step_name="step-a")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(runbook_id="rb-1", step_name="step-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
