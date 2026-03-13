"""Tests for MultiObjectiveOptimizerEngine."""

from __future__ import annotations

from shieldops.analytics.multi_objective_optimizer_engine import (
    MultiObjectiveOptimizerEngine,
    ObjectiveType,
    OptimizationStatus,
    TradeoffStrategy,
)


def _engine(**kw) -> MultiObjectiveOptimizerEngine:
    return MultiObjectiveOptimizerEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(solution_id="s1", objective_value=0.85)
    assert r.solution_id == "s1"
    assert r.objective_value == 0.85


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(solution_id=f"s{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(solution_id="s1", objective_value=0.7)
    analysis = eng.process(r.id)
    assert hasattr(analysis, "solution_id")
    assert analysis.solution_id == "s1"


def test_process_not_found():
    result = _engine().process("missing")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        solution_id="s1",
        objective_type=ObjectiveType.LATENCY,
        status=OptimizationStatus.OPTIMAL,
        objective_value=0.9,
    )
    eng.add_record(
        solution_id="s2",
        objective_type=ObjectiveType.COST,
        status=OptimizationStatus.SUBOPTIMAL,
        objective_value=0.4,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert rpt.avg_objective_value > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(solution_id="s1", objective_type=ObjectiveType.THROUGHPUT)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "throughput" in stats["objective_type_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(solution_id="s1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_find_pareto_frontiers():
    eng = _engine()
    eng.add_record(solution_id="s1", objective_type=ObjectiveType.LATENCY, objective_value=0.9)
    eng.add_record(solution_id="s1", objective_type=ObjectiveType.COST, objective_value=0.8)
    eng.add_record(solution_id="s2", objective_type=ObjectiveType.LATENCY, objective_value=0.5)
    eng.add_record(solution_id="s2", objective_type=ObjectiveType.COST, objective_value=0.3)
    result = eng.find_pareto_frontiers()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "solution_id" in result[0]
    assert result[0]["pareto_optimal"] is True


def test_evaluate_tradeoff_strategies():
    eng = _engine()
    eng.add_record(
        solution_id="s1",
        tradeoff_strategy=TradeoffStrategy.PARETO,
        objective_value=0.9,
    )
    eng.add_record(
        solution_id="s2",
        tradeoff_strategy=TradeoffStrategy.WEIGHTED,
        objective_value=0.6,
    )
    eng.add_record(
        solution_id="s3",
        tradeoff_strategy=TradeoffStrategy.LEXICOGRAPHIC,
        objective_value=0.75,
    )
    result = eng.evaluate_tradeoff_strategies()
    assert isinstance(result, list)
    assert len(result) == 3
    assert "avg_objective" in result[0]


def test_rank_solutions_by_objective():
    eng = _engine()
    eng.add_record(solution_id="s1", objective_type=ObjectiveType.RELIABILITY, objective_value=0.9)
    eng.add_record(solution_id="s2", objective_type=ObjectiveType.RELIABILITY, objective_value=0.5)
    eng.add_record(solution_id="s3", objective_type=ObjectiveType.RELIABILITY, objective_value=0.7)
    result = eng.rank_solutions_by_objective("reliability")
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["rank"] == 1
    assert result[0]["avg_value"] >= result[1]["avg_value"]
