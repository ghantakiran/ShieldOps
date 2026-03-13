"""Tests for AdaptiveRetrievalStrategyEngine."""

from __future__ import annotations

from shieldops.observability.adaptive_retrieval_strategy_engine import (
    AdaptiveRetrievalAnalysis,
    AdaptiveRetrievalRecord,
    AdaptiveRetrievalReport,
    AdaptiveRetrievalStrategyEngine,
    DataSource,
    QueryOutcome,
    RetrievalStrategy,
)


def test_add_record() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    rec = engine.add_record(
        session_id="sess-001",
        data_source=DataSource.METRICS,
        retrieval_strategy=RetrievalStrategy.PRIORITY_GUIDED,
        query_outcome=QueryOutcome.HIGH_SIGNAL,
        query_cost_ms=50.0,
        signal_score=0.9,
        query_text="avg cpu > 80%",
    )
    assert isinstance(rec, AdaptiveRetrievalRecord)
    assert rec.session_id == "sess-001"
    assert rec.signal_score == 0.9


def test_process() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    rec = engine.add_record(
        session_id="sess-002",
        data_source=DataSource.LOGS,
        query_outcome=QueryOutcome.HIGH_SIGNAL,
        signal_score=0.8,
        query_cost_ms=100.0,
    )
    result = engine.process(rec.id)
    assert isinstance(result, AdaptiveRetrievalAnalysis)
    assert result.session_id == "sess-002"
    assert result.efficiency_score > 0


def test_process_not_found() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    for sid, ds, rs, qo, cost, sig in [
        (
            "s1",
            DataSource.METRICS,
            RetrievalStrategy.BREADTH_FIRST,
            QueryOutcome.HIGH_SIGNAL,
            30.0,
            0.9,
        ),
        ("s2", DataSource.LOGS, RetrievalStrategy.DEPTH_FIRST, QueryOutcome.LOW_SIGNAL, 80.0, 0.4),
        ("s3", DataSource.TRACES, RetrievalStrategy.COST_AWARE, QueryOutcome.NO_SIGNAL, 200.0, 0.0),
        (
            "s4",
            DataSource.EVENTS,
            RetrievalStrategy.PRIORITY_GUIDED,
            QueryOutcome.AMBIGUOUS,
            60.0,
            0.5,
        ),
    ]:
        engine.add_record(
            session_id=sid,
            data_source=ds,
            retrieval_strategy=rs,
            query_outcome=qo,
            query_cost_ms=cost,
            signal_score=sig,
        )
    report = engine.generate_report()
    assert isinstance(report, AdaptiveRetrievalReport)
    assert report.total_records == 4
    assert "metrics" in report.by_data_source
    assert "metrics" in report.priority_map


def test_get_stats() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    engine.add_record(data_source=DataSource.METRICS, signal_score=0.9)
    engine.add_record(data_source=DataSource.LOGS, signal_score=0.5)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "data_source_distribution" in stats


def test_clear_data() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    engine.add_record(session_id="s-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_select_next_data_source() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    engine.add_record(data_source=DataSource.METRICS, signal_score=0.9, query_cost_ms=10.0)
    engine.add_record(data_source=DataSource.METRICS, signal_score=0.85, query_cost_ms=15.0)
    engine.add_record(data_source=DataSource.LOGS, signal_score=0.3, query_cost_ms=200.0)
    results = engine.select_next_data_source()
    assert isinstance(results, list)
    assert results[0]["priority_score"] >= results[-1]["priority_score"]
    assert "avg_signal_score" in results[0]


def test_evaluate_retrieval_efficiency() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    engine.add_record(
        retrieval_strategy=RetrievalStrategy.COST_AWARE,
        signal_score=0.8,
        query_cost_ms=20.0,
    )
    engine.add_record(
        retrieval_strategy=RetrievalStrategy.BREADTH_FIRST,
        signal_score=0.4,
        query_cost_ms=300.0,
    )
    results = engine.evaluate_retrieval_efficiency()
    assert isinstance(results, list)
    assert results[0]["efficiency_score"] >= results[-1]["efficiency_score"]
    assert "avg_signal" in results[0]


def test_build_retrieval_priority_map() -> None:
    engine = AdaptiveRetrievalStrategyEngine()
    engine.add_record(
        data_source=DataSource.METRICS, signal_score=0.9, query_outcome=QueryOutcome.HIGH_SIGNAL
    )
    engine.add_record(
        data_source=DataSource.METRICS, signal_score=0.85, query_outcome=QueryOutcome.HIGH_SIGNAL
    )
    engine.add_record(
        data_source=DataSource.LOGS, signal_score=0.4, query_outcome=QueryOutcome.LOW_SIGNAL
    )
    priority_map = engine.build_retrieval_priority_map()
    assert isinstance(priority_map, dict)
    assert "metrics" in priority_map
    assert priority_map["metrics"]["priority_rank"] == 1
    assert "outcome_distribution" in priority_map["metrics"]
