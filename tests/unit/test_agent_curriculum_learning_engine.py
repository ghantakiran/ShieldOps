"""Tests for AgentCurriculumLearningEngine."""

from __future__ import annotations

from shieldops.analytics.agent_curriculum_learning_engine import (
    AgentCurriculumLearningEngine,
    CurriculumPhase,
    DifficultyLevel,
    LearningProgress,
)


def _engine(**kw) -> AgentCurriculumLearningEngine:
    return AgentCurriculumLearningEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", task_score=0.75)
    assert r.agent_id == "a1"
    assert r.task_score == 0.75


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(agent_id="a1", task_score=0.8, completion_rate=0.9)
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"
    assert analysis.readiness_score > 0


def test_process_not_found():
    result = _engine().process("missing")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        difficulty=DifficultyLevel.BEGINNER,
        phase=CurriculumPhase.TRAINING,
        task_score=0.65,
    )
    eng.add_record(
        agent_id="a2",
        difficulty=DifficultyLevel.ADVANCED,
        progress=LearningProgress.BEHIND,
        task_score=0.4,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "behind" in rpt.by_progress
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", difficulty=DifficultyLevel.EXPERT)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "expert" in stats["difficulty_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_design_learning_curriculum():
    eng = _engine()
    eng.add_record(agent_id="a1", difficulty=DifficultyLevel.BEGINNER, task_score=0.9)
    eng.add_record(agent_id="a1", difficulty=DifficultyLevel.BEGINNER, task_score=0.85)
    eng.add_record(agent_id="a2", difficulty=DifficultyLevel.INTERMEDIATE, task_score=0.6)
    result = eng.design_learning_curriculum()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "should_advance" in result[0]
    assert result[0]["should_advance"] is True


def test_evaluate_progression_readiness():
    eng = _engine()
    eng.add_record(agent_id="a1", task_score=0.85, completion_rate=0.9)
    eng.add_record(agent_id="a1", task_score=0.8, completion_rate=0.88)
    eng.add_record(agent_id="a2", task_score=0.4, completion_rate=0.5)
    result = eng.evaluate_progression_readiness()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "ready_to_advance" in result[0]
    assert result[0]["readiness_score"] >= result[1]["readiness_score"]


def test_optimize_difficulty_scheduling():
    eng = _engine()
    eng.add_record(agent_id="a1", difficulty=DifficultyLevel.BEGINNER, task_score=0.8)
    eng.add_record(agent_id="a2", difficulty=DifficultyLevel.ADVANCED, task_score=0.5)
    eng.add_record(agent_id="a3", difficulty=DifficultyLevel.EXPERT, task_score=0.95)
    result = eng.optimize_difficulty_scheduling()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "schedule_optimal" in result[0]
    assert "advance_threshold" in result[0]
