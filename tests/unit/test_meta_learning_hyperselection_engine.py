"""Tests for MetaLearningHyperselectionEngine."""

from __future__ import annotations

from shieldops.analytics.meta_learning_hyperselection_engine import (
    HyperparamType,
    MetaLearningHyperselectionEngine,
    SearchStrategy,
    SelectionOutcome,
)


def _engine(**kw) -> MetaLearningHyperselectionEngine:
    return MetaLearningHyperselectionEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", performance_score=0.88)
    assert r.agent_id == "a1"
    assert r.performance_score == 0.88


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        agent_id="a1",
        search_strategy=SearchStrategy.BAYESIAN,
        performance_score=0.9,
        iterations_used=50,
    )
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"
    assert analysis.best_strategy == SearchStrategy.BAYESIAN


def test_process_not_found():
    result = _engine().process("nope")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        search_strategy=SearchStrategy.GRID,
        outcome=SelectionOutcome.IMPROVED,
        performance_score=0.7,
    )
    eng.add_record(
        agent_id="a2",
        search_strategy=SearchStrategy.EVOLUTIONARY,
        outcome=SelectionOutcome.FAILED,
        performance_score=0.2,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "failed" in rpt.by_outcome
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", search_strategy=SearchStrategy.RANDOM)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "random" in stats["search_strategy_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_evaluate_search_strategies():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        search_strategy=SearchStrategy.BAYESIAN,
        performance_score=0.9,
        iterations_used=30,
        search_budget=10.0,
    )
    eng.add_record(
        agent_id="a2",
        search_strategy=SearchStrategy.GRID,
        performance_score=0.6,
        iterations_used=100,
        search_budget=50.0,
    )
    result = eng.evaluate_search_strategies()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "efficiency" in result[0]
    assert result[0]["efficiency"] >= result[1]["efficiency"]


def test_rank_hyperparameter_configs():
    eng = _engine()
    eng.add_record(
        agent_id="a1", hyperparam_type=HyperparamType.LEARNING_RATE, performance_score=0.9
    )
    eng.add_record(agent_id="a2", hyperparam_type=HyperparamType.BATCH_SIZE, performance_score=0.6)
    eng.add_record(
        agent_id="a3", hyperparam_type=HyperparamType.ARCHITECTURE, performance_score=0.75
    )
    result = eng.rank_hyperparameter_configs()
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["rank"] == 1
    assert result[0]["avg_performance"] >= result[-1]["avg_performance"]


def test_optimize_meta_learning_schedule():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        performance_score=0.85,
        iterations_used=20,
        outcome=SelectionOutcome.IMPROVED,
    )
    eng.add_record(
        agent_id="a1",
        performance_score=0.9,
        iterations_used=15,
        outcome=SelectionOutcome.IMPROVED,
    )
    eng.add_record(
        agent_id="a2",
        performance_score=0.3,
        iterations_used=80,
        outcome=SelectionOutcome.DEGRADED,
    )
    result = eng.optimize_meta_learning_schedule()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "schedule_quality" in result[0]
    assert "needs_rerun" in result[0]
