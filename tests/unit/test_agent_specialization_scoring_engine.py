"""Tests for AgentSpecializationScoringEngine."""

from __future__ import annotations

from shieldops.analytics.agent_specialization_scoring_engine import (
    AgentSpecializationScoringEngine,
    EffectivenessLevel,
    SpecializationDepth,
    SpecializationType,
)


def _engine(**kw) -> AgentSpecializationScoringEngine:
    return AgentSpecializationScoringEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", specialization_score=0.85)
    assert r.agent_id == "a1"
    assert r.specialization_score == 0.85


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        agent_id="a1",
        specialization_type=SpecializationType.DOMAIN,
        specialization_score=0.8,
        generalization_score=0.5,
    )
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"
    assert analysis.value_score > 0


def test_process_not_found():
    result = _engine().process("missing")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        specialization_type=SpecializationType.SKILL,
        effectiveness=EffectivenessLevel.EXCEPTIONAL,
        specialization_score=0.95,
    )
    eng.add_record(
        agent_id="a2",
        specialization_type=SpecializationType.ROLE,
        effectiveness=EffectivenessLevel.INEFFECTIVE,
        specialization_score=0.2,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "ineffective" in rpt.by_effectiveness
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", specialization_type=SpecializationType.TASK)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "task" in stats["specialization_type_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_evaluate_specialization_depth():
    eng = _engine()
    eng.add_record(agent_id="a1", depth=SpecializationDepth.EXPERT, specialization_score=0.95)
    eng.add_record(agent_id="a2", depth=SpecializationDepth.GENERALIST, specialization_score=0.4)
    eng.add_record(agent_id="a3", depth=SpecializationDepth.SPECIALIST, specialization_score=0.8)
    result = eng.evaluate_specialization_depth()
    assert isinstance(result, list)
    assert len(result) == 3
    assert "dominant_depth" in result[0]
    assert "depth_score" in result[0]
    assert result[0]["depth_score"] >= result[-1]["depth_score"]


def test_detect_overfitting_risk():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        specialization_score=0.95,
        generalization_score=0.3,
        depth=SpecializationDepth.EXPERT,
    )
    eng.add_record(
        agent_id="a2",
        specialization_score=0.7,
        generalization_score=0.65,
        depth=SpecializationDepth.MODERATE,
    )
    result = eng.detect_overfitting_risk()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "overfitting_risk" in result[0]
    assert "risk_level" in result[0]
    assert result[0]["spec_gen_gap"] >= result[1]["spec_gen_gap"]


def test_rank_specializations_by_value():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        specialization_type=SpecializationType.DOMAIN,
        task_success_rate=0.9,
        specialization_score=0.85,
        effectiveness=EffectivenessLevel.EXCEPTIONAL,
    )
    eng.add_record(
        agent_id="a2",
        specialization_type=SpecializationType.SKILL,
        task_success_rate=0.6,
        specialization_score=0.5,
        effectiveness=EffectivenessLevel.DEVELOPING,
    )
    result = eng.rank_specializations_by_value()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["rank"] == 1
    assert "value_score" in result[0]
