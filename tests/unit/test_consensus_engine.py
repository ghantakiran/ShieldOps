"""Tests for shieldops.agents.consensus_engine — AgentConsensusEngine."""

from __future__ import annotations

from shieldops.agents.consensus_engine import (
    AgentConsensusEngine,
    AgentVote,
    ConsensusEngineReport,
    ConsensusRecord,
    ConsensusStrategy,
    DisagreementAction,
    VoteType,
)


def _engine(**kw) -> AgentConsensusEngine:
    return AgentConsensusEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # VoteType (5)
    def test_vote_approve(self):
        assert VoteType.APPROVE == "approve"

    def test_vote_reject(self):
        assert VoteType.REJECT == "reject"

    def test_vote_abstain(self):
        assert VoteType.ABSTAIN == "abstain"

    def test_vote_conditional(self):
        assert VoteType.CONDITIONAL == "conditional"

    def test_vote_defer(self):
        assert VoteType.DEFER == "defer"

    # ConsensusStrategy (5)
    def test_strategy_unanimous(self):
        assert ConsensusStrategy.UNANIMOUS == "unanimous"

    def test_strategy_majority(self):
        assert ConsensusStrategy.MAJORITY == "majority"

    def test_strategy_supermajority(self):
        assert ConsensusStrategy.SUPERMAJORITY == "supermajority"

    def test_strategy_weighted(self):
        assert ConsensusStrategy.WEIGHTED == "weighted"

    def test_strategy_quorum(self):
        assert ConsensusStrategy.QUORUM == "quorum"

    # DisagreementAction (5)
    def test_disagreement_escalate(self):
        assert DisagreementAction.ESCALATE == "escalate"

    def test_disagreement_re_vote(self):
        assert DisagreementAction.RE_VOTE == "re_vote"

    def test_disagreement_leader_override(self):
        assert DisagreementAction.LEADER_OVERRIDE == "leader_override"

    def test_disagreement_defer(self):
        assert DisagreementAction.DEFER == "defer"

    def test_disagreement_abort(self):
        assert DisagreementAction.ABORT == "abort"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_consensus_record_defaults(self):
        r = ConsensusRecord()
        assert r.id
        assert r.decision_id == ""
        assert r.vote_type == VoteType.APPROVE
        assert r.consensus_strategy == ConsensusStrategy.MAJORITY
        assert r.disagreement_action == DisagreementAction.ESCALATE
        assert r.voter_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_agent_vote_defaults(self):
        r = AgentVote()
        assert r.id
        assert r.agent_name == ""
        assert r.vote_type == VoteType.APPROVE
        assert r.consensus_strategy == ConsensusStrategy.MAJORITY
        assert r.confidence_score == 0.0
        assert r.created_at > 0

    def test_consensus_engine_report_defaults(self):
        r = ConsensusEngineReport()
        assert r.total_decisions == 0
        assert r.total_votes == 0
        assert r.approval_rate_pct == 0.0
        assert r.by_vote_type == {}
        assert r.by_strategy == {}
        assert r.disagreement_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_decision
# -------------------------------------------------------------------


class TestRecordDecision:
    def test_basic(self):
        eng = _engine()
        r = eng.record_decision(
            "dec-1",
            vote_type=VoteType.APPROVE,
            consensus_strategy=ConsensusStrategy.MAJORITY,
        )
        assert r.decision_id == "dec-1"
        assert r.vote_type == VoteType.APPROVE

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_decision(f"dec-{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_decision("dec-1")
        assert eng.get_decision(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_decision("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_decision("dec-1")
        eng.record_decision("dec-2")
        results = eng.list_decisions(decision_id="dec-1")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_decision(f"dec-{i}")
        results = eng.list_decisions(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_vote
# -------------------------------------------------------------------


class TestAddVote:
    def test_basic(self):
        eng = _engine()
        v = eng.add_vote(
            "agent-alpha",
            vote_type=VoteType.APPROVE,
            consensus_strategy=ConsensusStrategy.MAJORITY,
            confidence_score=0.95,
        )
        assert v.agent_name == "agent-alpha"
        assert v.confidence_score == 0.95

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_vote(f"agent-{i}")
        assert len(eng._votes) == 2


# -------------------------------------------------------------------
# analyze_consensus_quality
# -------------------------------------------------------------------


class TestAnalyze:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_consensus_quality("ghost")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_decision("dec-1", vote_type=VoteType.APPROVE)
        eng.record_decision("dec-1", vote_type=VoteType.REJECT)
        result = eng.analyze_consensus_quality("dec-1")
        assert result["decision_id"] == "dec-1"
        assert result["total_decisions"] == 2
        assert result["approval_rate_pct"] == 50.0

    def test_meets_threshold(self):
        eng = _engine(quorum_pct=50.0)
        eng.record_decision("dec-1", vote_type=VoteType.APPROVE)
        result = eng.analyze_consensus_quality("dec-1")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_disputed_decisions
# -------------------------------------------------------------------


class TestIdentify:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_disputed_decisions() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_decision("dec-1", vote_type=VoteType.REJECT)
        eng.record_decision("dec-1", vote_type=VoteType.REJECT)
        eng.record_decision("dec-2", vote_type=VoteType.APPROVE)
        results = eng.identify_disputed_decisions()
        assert len(results) == 1
        assert results[0]["decision_id"] == "dec-1"


# -------------------------------------------------------------------
# rank_by_disagreement_rate
# -------------------------------------------------------------------


class TestRank:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_disagreement_rate() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_decision("dec-1")
        eng.record_decision("dec-1")
        eng.record_decision("dec-2")
        results = eng.rank_by_disagreement_rate()
        assert results[0]["decision_id"] == "dec-1"
        assert results[0]["decision_count"] == 2


# -------------------------------------------------------------------
# detect_voting_deadlocks
# -------------------------------------------------------------------


class TestDetect:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_voting_deadlocks() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_decision("dec-1", vote_type=VoteType.REJECT)
        eng.record_decision("dec-2", vote_type=VoteType.APPROVE)
        results = eng.detect_voting_deadlocks()
        assert len(results) == 1
        assert results[0]["decision_id"] == "dec-1"
        assert results[0]["deadlock_detected"] is True


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_decisions == 0
        assert "below" in report.recommendations[0]

    def test_with_data(self):
        eng = _engine()
        eng.record_decision("dec-1", vote_type=VoteType.APPROVE)
        eng.record_decision("dec-2", vote_type=VoteType.REJECT)
        eng.record_decision("dec-2", vote_type=VoteType.REJECT)
        eng.add_vote("agent-1")
        report = eng.generate_report()
        assert report.total_decisions == 3
        assert report.total_votes == 1
        assert report.by_vote_type != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_decision("dec-1", vote_type=VoteType.APPROVE)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_decision("dec-1")
        eng.add_vote("agent-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._votes) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_decisions"] == 0
        assert stats["total_votes"] == 0
        assert stats["vote_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_decision("dec-1", vote_type=VoteType.APPROVE)
        eng.record_decision("dec-2", vote_type=VoteType.REJECT)
        eng.add_vote("agent-1")
        stats = eng.get_stats()
        assert stats["total_decisions"] == 2
        assert stats["total_votes"] == 1
        assert stats["unique_decision_ids"] == 2
