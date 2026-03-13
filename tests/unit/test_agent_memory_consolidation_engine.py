"""Tests for AgentMemoryConsolidationEngine."""

from __future__ import annotations

from shieldops.analytics.agent_memory_consolidation_engine import (
    AgentMemoryConsolidationEngine,
    ConsolidationPhase,
    MemoryType,
    RetentionQuality,
)


def _engine(**kw) -> AgentMemoryConsolidationEngine:
    return AgentMemoryConsolidationEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", retention_score=0.85)
    assert r.agent_id == "a1"
    assert r.retention_score == 0.85


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(agent_id="a1", retention_score=0.8, decay_rate=0.05)
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"
    assert analysis.consolidation_score >= 0


def test_process_not_found():
    result = _engine().process("no-such-id")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        memory_type=MemoryType.EPISODIC,
        retention_quality=RetentionQuality.EXCELLENT,
        retention_score=0.95,
    )
    eng.add_record(
        agent_id="a2",
        memory_type=MemoryType.WORKING,
        retention_quality=RetentionQuality.LOST,
        retention_score=0.1,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "lost" in rpt.by_retention_quality
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", memory_type=MemoryType.SEMANTIC)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "semantic" in stats["memory_type_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_evaluate_memory_retention():
    eng = _engine()
    eng.add_record(agent_id="a1", memory_type=MemoryType.EPISODIC, retention_score=0.9)
    eng.add_record(agent_id="a1", memory_type=MemoryType.SEMANTIC, retention_score=0.7)
    eng.add_record(agent_id="a2", memory_type=MemoryType.PROCEDURAL, retention_score=0.5)
    result = eng.evaluate_memory_retention()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "overall_retention" in result[0]
    assert "per_type_retention" in result[0]


def test_detect_knowledge_decay():
    eng = _engine()
    eng.add_record(agent_id="a1", retention_score=0.9, decay_rate=0.02)
    eng.add_record(agent_id="a1", retention_score=0.5, decay_rate=0.4)
    eng.add_record(agent_id="a2", retention_score=0.85, decay_rate=0.01)
    eng.add_record(agent_id="a2", retention_score=0.87, decay_rate=0.01)
    result = eng.detect_knowledge_decay()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "is_decaying" in result[0]
    assert "severity" in result[0]


def test_optimize_consolidation_schedule():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        decay_rate=0.4,
        memory_size_mb=100.0,
        retention_quality=RetentionQuality.LOST,
        phase=ConsolidationPhase.PRUNING,
    )
    eng.add_record(
        agent_id="a2",
        decay_rate=0.01,
        memory_size_mb=20.0,
        retention_quality=RetentionQuality.EXCELLENT,
    )
    result = eng.optimize_consolidation_schedule()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "recommended_frequency" in result[0]
    assert result[0]["consolidation_urgency"] >= result[1]["consolidation_urgency"]
