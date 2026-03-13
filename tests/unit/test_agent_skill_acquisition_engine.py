"""Tests for AgentSkillAcquisitionEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.agent_skill_acquisition_engine import (
    AcquisitionStatus,
    AgentSkillAcquisitionEngine,
    SkillDependency,
    SkillDomain,
)


@pytest.fixture()
def engine() -> AgentSkillAcquisitionEngine:
    return AgentSkillAcquisitionEngine(max_records=100)


def test_add_record(engine: AgentSkillAcquisitionEngine) -> None:
    rec = engine.add_record(
        agent_id="agent-A",
        skill_name="log_analysis",
        domain=SkillDomain.DIAGNOSIS,
        status=AcquisitionStatus.ACQUIRED,
        dependency=SkillDependency.INDEPENDENT,
        proficiency_score=0.75,
        iteration_acquired=5,
    )
    assert rec.agent_id == "agent-A"
    assert rec.skill_name == "log_analysis"
    assert len(engine._records) == 1


def test_process(engine: AgentSkillAcquisitionEngine) -> None:
    rec = engine.add_record(agent_id="agent-B", skill_name="restart_pod", proficiency_score=0.8)
    result = engine.process(rec.id)
    assert hasattr(result, "agent_id")
    assert result.agent_id == "agent-B"  # type: ignore[union-attr]


def test_process_not_found(engine: AgentSkillAcquisitionEngine) -> None:
    result = engine.process("ghost-id")
    assert result["status"] == "not_found"


def test_generate_report(engine: AgentSkillAcquisitionEngine) -> None:
    engine.add_record(agent_id="a1", skill_name="sk1", domain=SkillDomain.REMEDIATION)
    engine.add_record(agent_id="a2", skill_name="sk2", domain=SkillDomain.TRIAGE)
    report = engine.generate_report()
    assert report.total_records == 2
    assert "remediation" in report.by_domain or "triage" in report.by_domain


def test_get_stats(engine: AgentSkillAcquisitionEngine) -> None:
    engine.add_record(agent_id="a3", skill_name="sk3", domain=SkillDomain.PREVENTION)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "domain_distribution" in stats


def test_clear_data(engine: AgentSkillAcquisitionEngine) -> None:
    engine.add_record(agent_id="a4", skill_name="sk4")
    engine.clear_data()
    assert engine._records == []


def test_map_skill_acquisition_graph(engine: AgentSkillAcquisitionEngine) -> None:
    engine.add_record(
        agent_id="graph-agent",
        skill_name="diagnose_cpu",
        domain=SkillDomain.DIAGNOSIS,
        status=AcquisitionStatus.MASTERED,
        proficiency_score=0.95,
    )
    engine.add_record(
        agent_id="graph-agent",
        skill_name="scale_deployment",
        domain=SkillDomain.REMEDIATION,
        status=AcquisitionStatus.LEARNING,
        proficiency_score=0.45,
    )
    graph = engine.map_skill_acquisition_graph("graph-agent")
    assert len(graph) == 2
    assert graph[0]["proficiency"] >= graph[1]["proficiency"]


def test_identify_skill_gaps(engine: AgentSkillAcquisitionEngine) -> None:
    engine.add_record(agent_id="gap-agent", skill_name="skill_x", status=AcquisitionStatus.ACQUIRED)
    engine.add_record(
        agent_id="other-agent", skill_name="skill_y", status=AcquisitionStatus.MASTERED
    )
    result = engine.identify_skill_gaps("gap-agent")
    assert result["agent_id"] == "gap-agent"
    assert "skill_y" in result["missing_skills"]


def test_predict_next_skill_unlock(engine: AgentSkillAcquisitionEngine) -> None:
    engine.add_record(
        agent_id="unlock-agent",
        skill_name="base_skill",
        status=AcquisitionStatus.ACQUIRED,
        proficiency_score=1.0,
    )
    engine.add_record(
        agent_id="unlock-agent",
        skill_name="advanced_skill",
        status=AcquisitionStatus.LEARNING,
        dependency=SkillDependency.PREREQUISITE,
        prerequisite_skill="base_skill",
        proficiency_score=0.7,
    )
    predictions = engine.predict_next_skill_unlock("unlock-agent")
    assert len(predictions) >= 1
    assert predictions[0]["skill_name"] == "advanced_skill"
    assert predictions[0]["prerequisite_met"] is True
