"""Tests for FormatComplianceRewardEngine."""

from __future__ import annotations

import pytest

from shieldops.security.format_compliance_reward_engine import (
    ComplianceLevel,
    FormatComplianceRewardEngine,
    FormatStandard,
    RewardComponent,
)


@pytest.fixture()
def engine() -> FormatComplianceRewardEngine:
    return FormatComplianceRewardEngine(max_records=100)


def test_add_record(engine: FormatComplianceRewardEngine) -> None:
    rec = engine.add_record(
        agent_id="agent-1",
        format_standard=FormatStandard.MITRE_MAPPED,
        compliance_level=ComplianceLevel.FULL_COMPLIANCE,
        reward_component=RewardComponent.STRUCTURE,
        compliance_score=0.95,
        reward_value=1.0,
        violation_count=0,
    )
    assert rec.agent_id == "agent-1"
    assert rec.compliance_score == 0.95
    assert len(engine._records) == 1


def test_process(engine: FormatComplianceRewardEngine) -> None:
    rec = engine.add_record(
        agent_id="a1",
        compliance_level=ComplianceLevel.MAJOR_DEVIATION,
        reward_value=1.0,
    )
    result = engine.process(rec.id)
    assert hasattr(result, "net_reward")
    assert result.penalty_applied > 0.0  # type: ignore[union-attr]


def test_process_not_found(engine: FormatComplianceRewardEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: FormatComplianceRewardEngine) -> None:
    engine.add_record(
        compliance_level=ComplianceLevel.NON_COMPLIANT,
        agent_id="agent-x",
        compliance_score=0.1,
    )
    engine.add_record(
        compliance_level=ComplianceLevel.FULL_COMPLIANCE,
        agent_id="agent-y",
        compliance_score=1.0,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "non_compliant" in report.by_compliance_level
    assert len(report.non_compliant_agents) >= 1


def test_get_stats(engine: FormatComplianceRewardEngine) -> None:
    engine.add_record(compliance_level=ComplianceLevel.MINOR_DEVIATION)
    stats = engine.get_stats()
    assert "compliance_level_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: FormatComplianceRewardEngine) -> None:
    engine.add_record(agent_id="a1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_score_format_compliance(engine: FormatComplianceRewardEngine) -> None:
    engine.add_record(agent_id="a1", compliance_score=0.9)
    engine.add_record(agent_id="a1", compliance_score=0.8)
    engine.add_record(agent_id="a2", compliance_score=0.4)
    result = engine.score_format_compliance()
    assert isinstance(result, list)
    assert result[0]["mean_compliance_score"] >= result[-1]["mean_compliance_score"]


def test_identify_format_violations(engine: FormatComplianceRewardEngine) -> None:
    engine.add_record(compliance_level=ComplianceLevel.NON_COMPLIANT, violation_count=5)
    engine.add_record(compliance_level=ComplianceLevel.FULL_COMPLIANCE, violation_count=0)
    result = engine.identify_format_violations()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["violation_count"] == 5


def test_compute_format_reward_impact(engine: FormatComplianceRewardEngine) -> None:
    engine.add_record(compliance_level=ComplianceLevel.FULL_COMPLIANCE, reward_value=1.0)
    engine.add_record(compliance_level=ComplianceLevel.MAJOR_DEVIATION, reward_value=1.0)
    result = engine.compute_format_reward_impact()
    assert "total_reward" in result
    assert "total_penalty" in result
    assert result["total_penalty"] > 0.0


def test_max_records_eviction(engine: FormatComplianceRewardEngine) -> None:
    for i in range(110):
        engine.add_record(agent_id=f"a-{i}")
    assert len(engine._records) == 100
