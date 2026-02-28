"""Agent Consensus Engine — multi-agent voting and quorum-based decision approval."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VoteType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"
    CONDITIONAL = "conditional"
    DEFER = "defer"


class ConsensusStrategy(StrEnum):
    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    SUPERMAJORITY = "supermajority"
    WEIGHTED = "weighted"
    QUORUM = "quorum"


class DisagreementAction(StrEnum):
    ESCALATE = "escalate"
    RE_VOTE = "re_vote"
    LEADER_OVERRIDE = "leader_override"
    DEFER = "defer"
    ABORT = "abort"


# --- Models ---


class ConsensusRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    vote_type: VoteType = VoteType.APPROVE
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY
    disagreement_action: DisagreementAction = DisagreementAction.ESCALATE
    voter_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AgentVote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    vote_type: VoteType = VoteType.APPROVE
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY
    confidence_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ConsensusEngineReport(BaseModel):
    total_decisions: int = 0
    total_votes: int = 0
    approval_rate_pct: float = 0.0
    by_vote_type: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    disagreement_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentConsensusEngine:
    """Multi-agent voting and quorum-based decision approval."""

    def __init__(
        self,
        max_records: int = 200000,
        quorum_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._quorum_pct = quorum_pct
        self._records: list[ConsensusRecord] = []
        self._votes: list[AgentVote] = []
        logger.info(
            "consensus_engine.initialized",
            max_records=max_records,
            quorum_pct=quorum_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        vote_type: VoteType = VoteType.APPROVE,
        consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY,
        disagreement_action: DisagreementAction = DisagreementAction.ESCALATE,
        voter_count: int = 0,
        details: str = "",
    ) -> ConsensusRecord:
        record = ConsensusRecord(
            decision_id=decision_id,
            vote_type=vote_type,
            consensus_strategy=consensus_strategy,
            disagreement_action=disagreement_action,
            voter_count=voter_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "consensus_engine.decision_recorded",
            record_id=record.id,
            decision_id=decision_id,
            vote_type=vote_type.value,
            consensus_strategy=consensus_strategy.value,
        )
        return record

    def get_decision(self, record_id: str) -> ConsensusRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_decisions(
        self,
        decision_id: str | None = None,
        consensus_strategy: ConsensusStrategy | None = None,
        limit: int = 50,
    ) -> list[ConsensusRecord]:
        results = list(self._records)
        if decision_id is not None:
            results = [r for r in results if r.decision_id == decision_id]
        if consensus_strategy is not None:
            results = [r for r in results if r.consensus_strategy == consensus_strategy]
        return results[-limit:]

    def add_vote(
        self,
        agent_name: str,
        vote_type: VoteType = VoteType.APPROVE,
        consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY,
        confidence_score: float = 0.0,
    ) -> AgentVote:
        vote = AgentVote(
            agent_name=agent_name,
            vote_type=vote_type,
            consensus_strategy=consensus_strategy,
            confidence_score=confidence_score,
        )
        self._votes.append(vote)
        if len(self._votes) > self._max_records:
            self._votes = self._votes[-self._max_records :]
        logger.info(
            "consensus_engine.vote_added",
            agent_name=agent_name,
            vote_type=vote_type.value,
            consensus_strategy=consensus_strategy.value,
        )
        return vote

    # -- domain operations -----------------------------------------------

    def analyze_consensus_quality(self, decision_id: str) -> dict[str, Any]:
        """Analyze consensus quality for a specific decision."""
        records = [r for r in self._records if r.decision_id == decision_id]
        if not records:
            return {"decision_id": decision_id, "status": "no_data"}
        approvals = sum(1 for r in records if r.vote_type == VoteType.APPROVE)
        approval_rate = round(approvals / len(records) * 100, 2)
        avg_voters = round(sum(r.voter_count for r in records) / len(records), 2)
        return {
            "decision_id": decision_id,
            "total_decisions": len(records),
            "approval_count": approvals,
            "approval_rate_pct": approval_rate,
            "avg_voter_count": avg_voters,
            "meets_threshold": approval_rate >= self._quorum_pct,
        }

    def identify_disputed_decisions(self) -> list[dict[str, Any]]:
        """Find decisions with repeated rejections."""
        rejection_counts: dict[str, int] = {}
        for r in self._records:
            if r.vote_type in (VoteType.REJECT, VoteType.ABSTAIN, VoteType.DEFER):
                rejection_counts[r.decision_id] = rejection_counts.get(r.decision_id, 0) + 1
        results: list[dict[str, Any]] = []
        for dec, count in rejection_counts.items():
            if count > 1:
                results.append(
                    {
                        "decision_id": dec,
                        "rejection_count": count,
                    }
                )
        results.sort(key=lambda x: x["rejection_count"], reverse=True)
        return results

    def rank_by_disagreement_rate(self) -> list[dict[str, Any]]:
        """Rank decisions by disagreement count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.decision_id] = freq.get(r.decision_id, 0) + 1
        results: list[dict[str, Any]] = []
        for dec, count in freq.items():
            results.append(
                {
                    "decision_id": dec,
                    "decision_count": count,
                }
            )
        results.sort(key=lambda x: x["decision_count"], reverse=True)
        return results

    def detect_voting_deadlocks(self) -> list[dict[str, Any]]:
        """Detect decisions caught in voting deadlocks (>3 non-approve)."""
        dec_non_approve: dict[str, int] = {}
        for r in self._records:
            if r.vote_type != VoteType.APPROVE:
                dec_non_approve[r.decision_id] = dec_non_approve.get(r.decision_id, 0) + 1
        results: list[dict[str, Any]] = []
        for dec, count in dec_non_approve.items():
            if count > 3:
                results.append(
                    {
                        "decision_id": dec,
                        "non_approve_count": count,
                        "deadlock_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_approve_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ConsensusEngineReport:
        by_vote_type: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_vote_type[r.vote_type.value] = by_vote_type.get(r.vote_type.value, 0) + 1
            by_strategy[r.consensus_strategy.value] = (
                by_strategy.get(r.consensus_strategy.value, 0) + 1
            )
        approval_count = sum(1 for r in self._records if r.vote_type == VoteType.APPROVE)
        approval_rate = (
            round(approval_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        disputed = sum(1 for d in self.identify_disputed_decisions())
        recs: list[str] = []
        if approval_rate < self._quorum_pct:
            recs.append(f"Approval rate {approval_rate}% is below {self._quorum_pct}% threshold")
        if disputed > 0:
            recs.append(f"{disputed} decision(s) with repeated disputes")
        deadlocks = len(self.detect_voting_deadlocks())
        if deadlocks > 0:
            recs.append(f"{deadlocks} decision(s) detected in voting deadlocks")
        if not recs:
            recs.append("Consensus engine effectiveness meets targets")
        return ConsensusEngineReport(
            total_decisions=len(self._records),
            total_votes=len(self._votes),
            approval_rate_pct=approval_rate,
            by_vote_type=by_vote_type,
            by_strategy=by_strategy,
            disagreement_count=disputed,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._votes.clear()
        logger.info("consensus_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        vote_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.vote_type.value
            vote_type_dist[key] = vote_type_dist.get(key, 0) + 1
        return {
            "total_decisions": len(self._records),
            "total_votes": len(self._votes),
            "quorum_pct": self._quorum_pct,
            "vote_type_distribution": vote_type_dist,
            "unique_decision_ids": len({r.decision_id for r in self._records}),
        }
