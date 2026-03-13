"""Tests for AgentPerformanceAttributionEngine."""

from __future__ import annotations

from shieldops.analytics.agent_performance_attribution_engine import (
    AgentPerformanceAttributionEngine,
    ComponentType,
    PerformanceImpact,
)


def _engine(**kw) -> AgentPerformanceAttributionEngine:
    return AgentPerformanceAttributionEngine(**kw)


def test_add_record_basic():
    eng = _engine()
    r = eng.add_record(agent_id="a1", attribution_score=0.75)
    assert r.agent_id == "a1"
    assert r.attribution_score == 0.75


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(6):
        eng.add_record(agent_id=f"a{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        agent_id="a1",
        component_type=ComponentType.REASONING,
        attribution_score=0.8,
    )
    analysis = eng.process(r.id)
    assert hasattr(analysis, "agent_id")
    assert analysis.agent_id == "a1"
    assert analysis.top_component == ComponentType.REASONING


def test_process_not_found():
    result = _engine().process("none")
    assert result["status"] == "not_found"


def test_generate_report_populated():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        component_type=ComponentType.PERCEPTION,
        performance_impact=PerformanceImpact.CRITICAL,
        attribution_score=0.9,
    )
    eng.add_record(
        agent_id="a2",
        component_type=ComponentType.ACTION,
        performance_impact=PerformanceImpact.NEGLIGIBLE,
        attribution_score=0.2,
    )
    rpt = eng.generate_report()
    assert rpt.total_records == 2
    assert "critical" in rpt.by_performance_impact
    assert len(rpt.recommendations) > 0


def test_generate_report_empty():
    rpt = _engine().generate_report()
    assert rpt.total_records == 0


def test_get_stats():
    eng = _engine()
    eng.add_record(agent_id="a1", component_type=ComponentType.COMMUNICATION)
    stats = eng.get_stats()
    assert stats["total_records"] == 1
    assert "communication" in stats["component_type_distribution"]


def test_clear_data():
    eng = _engine()
    eng.add_record(agent_id="a1")
    eng.clear_data()
    assert len(eng._records) == 0


def test_compute_component_attribution():
    eng = _engine()
    eng.add_record(agent_id="a1", component_type=ComponentType.REASONING, attribution_score=0.9)
    eng.add_record(agent_id="a2", component_type=ComponentType.REASONING, attribution_score=0.8)
    eng.add_record(agent_id="a3", component_type=ComponentType.ACTION, attribution_score=0.5)
    result = eng.compute_component_attribution()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "avg_attribution" in result[0]
    assert result[0]["avg_attribution"] >= result[-1]["avg_attribution"]


def test_detect_performance_bottlenecks():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        component_type=ComponentType.PERCEPTION,
        performance_impact=PerformanceImpact.CRITICAL,
        attribution_score=0.9,
    )
    eng.add_record(
        agent_id="a2",
        component_type=ComponentType.PERCEPTION,
        performance_impact=PerformanceImpact.CRITICAL,
        attribution_score=0.8,
    )
    eng.add_record(
        agent_id="a3",
        component_type=ComponentType.COMMUNICATION,
        performance_impact=PerformanceImpact.NEGLIGIBLE,
        attribution_score=0.1,
    )
    result = eng.detect_performance_bottlenecks()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "is_bottleneck" in result[0]
    assert "critical_rate" in result[0]


def test_rank_components_by_impact():
    eng = _engine()
    eng.add_record(
        agent_id="a1",
        component_type=ComponentType.REASONING,
        performance_impact=PerformanceImpact.CRITICAL,
        attribution_score=0.9,
    )
    eng.add_record(
        agent_id="a2",
        component_type=ComponentType.ACTION,
        performance_impact=PerformanceImpact.MODERATE,
        attribution_score=0.5,
    )
    result = eng.rank_components_by_impact()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["rank"] == 1
    assert "weighted_impact" in result[0]
