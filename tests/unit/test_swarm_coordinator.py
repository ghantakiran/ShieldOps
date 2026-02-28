"""Tests for shieldops.agents.swarm_coordinator — AgentSwarmCoordinator."""

from __future__ import annotations

from shieldops.agents.swarm_coordinator import (
    AgentAssignment,
    AgentSwarmCoordinator,
    ConflictResolution,
    SwarmCoordinatorReport,
    SwarmRecord,
    SwarmRole,
    SwarmStatus,
)


def _engine(**kw) -> AgentSwarmCoordinator:
    return AgentSwarmCoordinator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # SwarmRole (5)
    def test_role_leader(self):
        assert SwarmRole.LEADER == "leader"

    def test_role_investigator(self):
        assert SwarmRole.INVESTIGATOR == "investigator"

    def test_role_remediator(self):
        assert SwarmRole.REMEDIATOR == "remediator"

    def test_role_observer(self):
        assert SwarmRole.OBSERVER == "observer"

    def test_role_validator(self):
        assert SwarmRole.VALIDATOR == "validator"

    # SwarmStatus (5)
    def test_status_forming(self):
        assert SwarmStatus.FORMING == "forming"

    def test_status_active(self):
        assert SwarmStatus.ACTIVE == "active"

    def test_status_converging(self):
        assert SwarmStatus.CONVERGING == "converging"

    def test_status_completed(self):
        assert SwarmStatus.COMPLETED == "completed"

    def test_status_dissolved(self):
        assert SwarmStatus.DISSOLVED == "dissolved"

    # ConflictResolution (5)
    def test_conflict_leader_decides(self):
        assert ConflictResolution.LEADER_DECIDES == "leader_decides"

    def test_conflict_majority_vote(self):
        assert ConflictResolution.MAJORITY_VOTE == "majority_vote"

    def test_conflict_priority_based(self):
        assert ConflictResolution.PRIORITY_BASED == "priority_based"

    def test_conflict_round_robin(self):
        assert ConflictResolution.ROUND_ROBIN == "round_robin"

    def test_conflict_escalate(self):
        assert ConflictResolution.ESCALATE == "escalate"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_swarm_record_defaults(self):
        r = SwarmRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.swarm_role == SwarmRole.LEADER
        assert r.swarm_status == SwarmStatus.FORMING
        assert r.conflict_resolution == ConflictResolution.LEADER_DECIDES
        assert r.agent_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_agent_assignment_defaults(self):
        r = AgentAssignment()
        assert r.id
        assert r.agent_name == ""
        assert r.swarm_role == SwarmRole.INVESTIGATOR
        assert r.swarm_status == SwarmStatus.ACTIVE
        assert r.utilization_pct == 0.0
        assert r.created_at > 0

    def test_swarm_coordinator_report_defaults(self):
        r = SwarmCoordinatorReport()
        assert r.total_swarms == 0
        assert r.total_assignments == 0
        assert r.completion_rate_pct == 0.0
        assert r.by_role == {}
        assert r.by_status == {}
        assert r.conflict_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_swarm
# -------------------------------------------------------------------


class TestRecordSwarm:
    def test_basic(self):
        eng = _engine()
        r = eng.record_swarm(
            "INC-001",
            swarm_role=SwarmRole.LEADER,
            swarm_status=SwarmStatus.ACTIVE,
        )
        assert r.incident_id == "INC-001"
        assert r.swarm_role == SwarmRole.LEADER

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_swarm(f"INC-{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_swarm("INC-001")
        assert eng.get_swarm(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_swarm("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_swarm("INC-001")
        eng.record_swarm("INC-002")
        results = eng.list_swarms(incident_id="INC-001")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_swarm(f"INC-{i}")
        results = eng.list_swarms(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_assignment
# -------------------------------------------------------------------


class TestAddAssignment:
    def test_basic(self):
        eng = _engine()
        r = eng.add_assignment(
            "agent-alpha",
            swarm_role=SwarmRole.INVESTIGATOR,
            swarm_status=SwarmStatus.ACTIVE,
            utilization_pct=75.0,
        )
        assert r.agent_name == "agent-alpha"
        assert r.utilization_pct == 75.0

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_assignment(f"agent-{i}")
        assert len(eng._assignments) == 2


# -------------------------------------------------------------------
# analyze_swarm_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeSwarmEffectiveness:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_swarm_effectiveness("INC-999")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_swarm("INC-001", swarm_status=SwarmStatus.COMPLETED)
        eng.record_swarm("INC-001", swarm_status=SwarmStatus.DISSOLVED)
        result = eng.analyze_swarm_effectiveness("INC-001")
        assert result["incident_id"] == "INC-001"
        assert result["total_swarms"] == 2
        assert result["completion_rate_pct"] == 50.0

    def test_meets_threshold(self):
        eng = _engine(max_agents=10)
        eng.record_swarm("INC-001", swarm_status=SwarmStatus.COMPLETED)
        result = eng.analyze_swarm_effectiveness("INC-001")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_idle_agents
# -------------------------------------------------------------------


class TestIdentifyIdleAgents:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_idle_agents() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_swarm("INC-001", swarm_status=SwarmStatus.DISSOLVED)
        eng.record_swarm("INC-001", swarm_status=SwarmStatus.DISSOLVED)
        eng.record_swarm("INC-002", swarm_status=SwarmStatus.COMPLETED)
        results = eng.identify_idle_agents()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"


# -------------------------------------------------------------------
# rank_by_completion_rate
# -------------------------------------------------------------------


class TestRankByCompletionRate:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completion_rate() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_swarm("INC-001")
        eng.record_swarm("INC-001")
        eng.record_swarm("INC-002")
        results = eng.rank_by_completion_rate()
        assert results[0]["incident_id"] == "INC-001"
        assert results[0]["swarm_count"] == 2


# -------------------------------------------------------------------
# detect_coordination_conflicts
# -------------------------------------------------------------------


class TestDetectCoordinationConflicts:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_coordination_conflicts() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_swarm("INC-001", swarm_status=SwarmStatus.DISSOLVED)
        eng.record_swarm("INC-002", swarm_status=SwarmStatus.COMPLETED)
        results = eng.detect_coordination_conflicts()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"
        assert results[0]["conflict_detected"] is True


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_swarms == 0
        assert "below" in report.recommendations[0]

    def test_with_data(self):
        eng = _engine()
        eng.record_swarm("INC-001", swarm_status=SwarmStatus.COMPLETED)
        eng.record_swarm("INC-002", swarm_status=SwarmStatus.DISSOLVED)
        eng.record_swarm("INC-002", swarm_status=SwarmStatus.DISSOLVED)
        eng.add_assignment("agent-1")
        report = eng.generate_report()
        assert report.total_swarms == 3
        assert report.total_assignments == 1
        assert report.by_role != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_swarm("INC-001", swarm_status=SwarmStatus.COMPLETED)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_swarm("INC-001")
        eng.add_assignment("agent-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._assignments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_swarms"] == 0
        assert stats["total_assignments"] == 0
        assert stats["role_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_swarm("INC-001", swarm_role=SwarmRole.LEADER)
        eng.record_swarm("INC-002", swarm_role=SwarmRole.INVESTIGATOR)
        eng.add_assignment("agent-1")
        stats = eng.get_stats()
        assert stats["total_swarms"] == 2
        assert stats["total_assignments"] == 1
        assert stats["unique_incidents"] == 2
