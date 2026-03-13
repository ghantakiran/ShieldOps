"""Tests for AgentTransferLearningEngine."""

from __future__ import annotations

from shieldops.analytics.agent_transfer_learning_engine import (
    AgentTransferLearningEngine,
    DomainSimilarity,
    TransferOutcome,
    TransferType,
)


def _engine(**kw) -> AgentTransferLearningEngine:
    return AgentTransferLearningEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(source_agent="s1", target_agent="t1", performance_delta=0.2)
    assert r.source_agent == "s1"
    assert r.target_agent == "t1"
    assert r.performance_delta == 0.2


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(source_agent="s1", target_agent=f"t{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        source_agent="s1",
        target_agent="t1",
        performance_delta=0.15,
        knowledge_retained=0.8,
    )
    analysis = eng.process(r.id)
    assert hasattr(analysis, "source_agent")
    assert analysis.source_agent == "s1"


def test_process_not_found():
    result = _engine().process("ghost")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        source_agent="s1",
        target_agent="t1",
        transfer_type=TransferType.DIRECT,
        outcome=TransferOutcome.POSITIVE,
        performance_delta=0.3,
    )
    eng.add_record(
        source_agent="s2",
        target_agent="t2",
        outcome=TransferOutcome.CATASTROPHIC,
        performance_delta=-0.5,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "catastrophic" in rpt.by_outcome
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(source_agent="s1", target_agent="t1", transfer_type=TransferType.ZERO_SHOT)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "zero_shot" in stats["transfer_type_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(source_agent="s1", target_agent="t1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_evaluate_domain_similarity():
    eng = _engine()
    eng.add_record(
        source_agent="s1",
        target_agent="t1",
        domain_similarity=DomainSimilarity.IDENTICAL,
        performance_delta=0.4,
    )
    eng.add_record(
        source_agent="s2",
        target_agent="t2",
        domain_similarity=DomainSimilarity.DISTANT,
        performance_delta=0.05,
    )
    result = eng.evaluate_domain_similarity()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "similarity_score" in result[0]
    assert result[0]["similarity_score"] >= result[-1]["similarity_score"]


def test_measure_transfer_effectiveness():
    eng = _engine()
    eng.add_record(
        source_agent="s1",
        target_agent="t1",
        transfer_type=TransferType.FINE_TUNED,
        performance_delta=0.3,
        knowledge_retained=0.85,
        convergence_speed=0.9,
    )
    eng.add_record(
        source_agent="s2",
        target_agent="t2",
        transfer_type=TransferType.ADAPTED,
        performance_delta=0.1,
        knowledge_retained=0.6,
        convergence_speed=0.5,
    )
    result = eng.measure_transfer_effectiveness()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "effectiveness_score" in result[0]


def test_rank_transfer_candidates():
    eng = _engine()
    eng.add_record(
        source_agent="src_a",
        target_agent="t1",
        performance_delta=0.5,
        knowledge_retained=0.9,
        outcome=TransferOutcome.POSITIVE,
    )
    eng.add_record(
        source_agent="src_b",
        target_agent="t2",
        performance_delta=0.1,
        knowledge_retained=0.4,
        outcome=TransferOutcome.NEUTRAL,
    )
    result = eng.rank_transfer_candidates()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["candidate_score"] >= result[1]["candidate_score"]
