"""Tests for AgentEvolutionTracker."""

from __future__ import annotations

from shieldops.analytics.agent_evolution_tracker import (
    AgentEvolutionTracker,
    EvolutionStage,
    MutationType,
    SelectionPressure,
)


def _engine(**kw) -> AgentEvolutionTracker:
    return AgentEvolutionTracker(**kw)


class TestEnums:
    def test_evolution_stage_values(self):
        assert isinstance(EvolutionStage.INITIAL, str)
        assert isinstance(EvolutionStage.LEARNING, str)
        assert isinstance(EvolutionStage.OPTIMIZING, str)
        assert isinstance(EvolutionStage.MATURE, str)

    def test_mutation_type_values(self):
        assert isinstance(MutationType.PARAMETER, str)
        assert isinstance(MutationType.ARCHITECTURE, str)
        assert isinstance(MutationType.STRATEGY, str)
        assert isinstance(MutationType.PROMPT, str)

    def test_selection_pressure_values(self):
        assert isinstance(SelectionPressure.PERFORMANCE, str)
        assert isinstance(SelectionPressure.COST, str)
        assert isinstance(SelectionPressure.RELIABILITY, str)
        assert isinstance(SelectionPressure.SPEED, str)


class TestAddRecord:
    def test_basic_add(self):
        eng = _engine()
        r = eng.add_record(
            agent_id="a1",
            stage=EvolutionStage.LEARNING,
            fitness_score=0.75,
            generation=3,
        )
        assert r.agent_id == "a1"
        assert r.fitness_score == 0.75

    def test_eviction_at_max(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(agent_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(agent_id="a1")
        result = eng.process(r.id)
        assert "analysis_id" in result

    def test_missing_key(self):
        eng = _engine()
        result = eng.process("nonexistent")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
        report = eng.generate_report()
        assert report.total_records > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        assert "total_records" in eng.get_stats()

    def test_populated_count(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
        eng.add_record(agent_id="a2")
        assert eng.get_stats()["total_records"] == 2


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(agent_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestTrackGenerationalProgress:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(agent_id="a1", generation=1, fitness_score=0.5)
        eng.add_record(agent_id="a1", generation=2, fitness_score=0.7)
        result = eng.track_generational_progress("a1")
        assert len(result) == 2
        assert result[0]["generation"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.track_generational_progress("a1") == []


class TestComputeEvolutionVelocity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(agent_id="a1", generation=1, fitness_score=0.5)
        eng.add_record(agent_id="a1", generation=2, fitness_score=0.7)
        result = eng.compute_evolution_velocity("a1")
        assert result["velocity"] == 0.2

    def test_empty(self):
        eng = _engine()
        result = eng.compute_evolution_velocity("a1")
        assert result["status"] == "no_data"


class TestIdentifyEvolutionaryDeadEnds:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            agent_id="a1",
            mutation=MutationType.PARAMETER,
            fitness_score=0.5,
        )
        eng.add_record(
            agent_id="a1",
            mutation=MutationType.PARAMETER,
            fitness_score=0.3,
        )
        result = eng.identify_evolutionary_dead_ends("a1")
        assert len(result) == 1
        assert result[0]["mutation_type"] == "parameter"

    def test_empty(self):
        eng = _engine()
        result = eng.identify_evolutionary_dead_ends("a1")
        assert result == []
