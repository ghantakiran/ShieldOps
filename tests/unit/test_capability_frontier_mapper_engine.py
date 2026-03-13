"""Tests for CapabilityFrontierMapperEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.capability_frontier_mapper_engine import (
    CapabilityFrontierMapperEngine,
    ExpansionDirection,
    FrontierStability,
    FrontierZone,
)


@pytest.fixture()
def engine() -> CapabilityFrontierMapperEngine:
    return CapabilityFrontierMapperEngine(max_records=100)


def test_add_record(engine: CapabilityFrontierMapperEngine) -> None:
    rec = engine.add_record(
        agent_id="agent-F",
        capability_name="root_cause_analysis",
        zone=FrontierZone.FRONTIER,
        direction=ExpansionDirection.DEPTH,
        stability=FrontierStability.EXPANDING,
        frontier_score=0.72,
        expansion_rate=0.03,
        iteration=10,
    )
    assert rec.agent_id == "agent-F"
    assert rec.zone == FrontierZone.FRONTIER
    assert len(engine._records) == 1


def test_process(engine: CapabilityFrontierMapperEngine) -> None:
    rec = engine.add_record(agent_id="agent-G", capability_name="cap-x", frontier_score=0.6)
    result = engine.process(rec.id)
    assert hasattr(result, "agent_id")
    assert result.agent_id == "agent-G"  # type: ignore[union-attr]


def test_process_not_found(engine: CapabilityFrontierMapperEngine) -> None:
    result = engine.process("no-such-key")
    assert result["status"] == "not_found"


def test_generate_report(engine: CapabilityFrontierMapperEngine) -> None:
    engine.add_record(
        agent_id="a1",
        capability_name="c1",
        zone=FrontierZone.MASTERED,
        frontier_score=0.95,
    )
    engine.add_record(
        agent_id="a2",
        capability_name="c2",
        zone=FrontierZone.BEYOND,
        frontier_score=0.1,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "mastered" in report.by_zone or "beyond" in report.by_zone


def test_get_stats(engine: CapabilityFrontierMapperEngine) -> None:
    engine.add_record(agent_id="a3", capability_name="c3", zone=FrontierZone.REACHABLE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "zone_distribution" in stats


def test_clear_data(engine: CapabilityFrontierMapperEngine) -> None:
    engine.add_record(agent_id="a4", capability_name="c4")
    engine.clear_data()
    assert engine._records == []


def test_compute_frontier_boundary(engine: CapabilityFrontierMapperEngine) -> None:
    engine.add_record(
        agent_id="bound-agent",
        capability_name="cap-a",
        zone=FrontierZone.FRONTIER,
        frontier_score=0.8,
    )
    engine.add_record(
        agent_id="bound-agent",
        capability_name="cap-b",
        zone=FrontierZone.MASTERED,
        frontier_score=0.95,
    )
    result = engine.compute_frontier_boundary("bound-agent")
    assert result["agent_id"] == "bound-agent"
    assert result["capability_count"] == 2
    assert result["frontier_boundary"] == pytest.approx(0.8, abs=0.01)


def test_measure_frontier_expansion_rate(engine: CapabilityFrontierMapperEngine) -> None:
    for i in range(4):
        engine.add_record(
            agent_id="expand-agent",
            capability_name="cap-c",
            zone=FrontierZone.FRONTIER,
            frontier_score=0.5 + i * 0.1,
            expansion_rate=0.05,
            iteration=i,
        )
    results = engine.measure_frontier_expansion_rate()
    assert len(results) >= 1
    assert results[0]["agent_id"] == "expand-agent"


def test_identify_frontier_bottlenecks(engine: CapabilityFrontierMapperEngine) -> None:
    for i in range(4):
        engine.add_record(
            agent_id="bot-agent",
            capability_name="stuck-cap",
            zone=FrontierZone.FRONTIER,
            frontier_score=0.6,
            iteration=i,
        )
    bottlenecks = engine.identify_frontier_bottlenecks()
    assert len(bottlenecks) >= 1
    assert bottlenecks[0]["capability_name"] == "stuck-cap"
    assert bottlenecks[0]["is_bottleneck"] is True
