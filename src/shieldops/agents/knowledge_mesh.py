"""Agent Knowledge Mesh — real-time knowledge federation across agents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class KnowledgeType(StrEnum):
    REASONING_CHAIN = "reasoning_chain"
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    CONCLUSION = "conclusion"


class PropagationScope(StrEnum):
    LOCAL = "local"
    TEAM = "team"
    SWARM = "swarm"
    GLOBAL = "global"
    SELECTIVE = "selective"


class FreshnessLevel(StrEnum):
    REAL_TIME = "real_time"
    RECENT = "recent"
    STALE = "stale"
    EXPIRED = "expired"
    ARCHIVED = "archived"


# --- Models ---


class KnowledgeEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str = ""
    knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION
    propagation_scope: PropagationScope = PropagationScope.LOCAL
    freshness_level: FreshnessLevel = FreshnessLevel.REAL_TIME
    relevance_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PropagationEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_label: str = ""
    knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION
    propagation_scope: PropagationScope = PropagationScope.TEAM
    hop_count: int = 0
    created_at: float = Field(default_factory=time.time)


class KnowledgeMeshReport(BaseModel):
    total_entries: int = 0
    total_propagations: int = 0
    freshness_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentKnowledgeMesh:
    """Real-time knowledge federation across agents."""

    def __init__(
        self,
        max_records: int = 200000,
        ttl_seconds: float = 3600,
    ) -> None:
        self._max_records = max_records
        self._ttl_seconds = ttl_seconds
        self._records: list[KnowledgeEntry] = []
        self._propagations: list[PropagationEvent] = []
        logger.info(
            "knowledge_mesh.initialized",
            max_records=max_records,
            ttl_seconds=ttl_seconds,
        )

    # -- record / get / list ---------------------------------------------

    def record_entry(
        self,
        source_agent: str,
        knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION,
        propagation_scope: PropagationScope = PropagationScope.LOCAL,
        freshness_level: FreshnessLevel = FreshnessLevel.REAL_TIME,
        relevance_score: float = 0.0,
        details: str = "",
    ) -> KnowledgeEntry:
        record = KnowledgeEntry(
            source_agent=source_agent,
            knowledge_type=knowledge_type,
            propagation_scope=propagation_scope,
            freshness_level=freshness_level,
            relevance_score=relevance_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_mesh.entry_recorded",
            record_id=record.id,
            source_agent=source_agent,
            knowledge_type=knowledge_type.value,
            freshness_level=freshness_level.value,
        )
        return record

    def get_entry(self, record_id: str) -> KnowledgeEntry | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_entries(
        self,
        source_agent: str | None = None,
        knowledge_type: KnowledgeType | None = None,
        limit: int = 50,
    ) -> list[KnowledgeEntry]:
        results = list(self._records)
        if source_agent is not None:
            results = [r for r in results if r.source_agent == source_agent]
        if knowledge_type is not None:
            results = [r for r in results if r.knowledge_type == knowledge_type]
        return results[-limit:]

    def add_propagation(
        self,
        event_label: str,
        knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION,
        propagation_scope: PropagationScope = PropagationScope.TEAM,
        hop_count: int = 0,
    ) -> PropagationEvent:
        event = PropagationEvent(
            event_label=event_label,
            knowledge_type=knowledge_type,
            propagation_scope=propagation_scope,
            hop_count=hop_count,
        )
        self._propagations.append(event)
        if len(self._propagations) > self._max_records:
            self._propagations = self._propagations[-self._max_records :]
        logger.info(
            "knowledge_mesh.propagation_added",
            event_label=event_label,
            knowledge_type=knowledge_type.value,
            propagation_scope=propagation_scope.value,
        )
        return event

    # -- domain operations -----------------------------------------------

    def analyze_knowledge_freshness(self, source_agent: str) -> dict[str, Any]:
        """Analyze knowledge freshness for a specific agent."""
        records = [r for r in self._records if r.source_agent == source_agent]
        if not records:
            return {"source_agent": source_agent, "status": "no_data"}
        fresh = sum(1 for r in records if r.freshness_level == FreshnessLevel.REAL_TIME)
        freshness_rate = round(fresh / len(records) * 100, 2)
        avg_relevance = round(sum(r.relevance_score for r in records) / len(records), 2)
        return {
            "source_agent": source_agent,
            "total_entries": len(records),
            "fresh_count": fresh,
            "freshness_rate_pct": freshness_rate,
            "avg_relevance_score": avg_relevance,
            "meets_threshold": freshness_rate >= 50.0,
        }

    def identify_stale_knowledge(self) -> list[dict[str, Any]]:
        """Find agents with repeated stale knowledge."""
        stale_counts: dict[str, int] = {}
        for r in self._records:
            if r.freshness_level in (
                FreshnessLevel.STALE,
                FreshnessLevel.EXPIRED,
                FreshnessLevel.ARCHIVED,
            ):
                stale_counts[r.source_agent] = stale_counts.get(r.source_agent, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in stale_counts.items():
            if count > 1:
                results.append(
                    {
                        "source_agent": agent,
                        "stale_count": count,
                    }
                )
        results.sort(key=lambda x: x["stale_count"], reverse=True)
        return results

    def rank_by_propagation_reach(self) -> list[dict[str, Any]]:
        """Rank agents by knowledge entry count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.source_agent] = freq.get(r.source_agent, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in freq.items():
            results.append(
                {
                    "source_agent": agent,
                    "entry_count": count,
                }
            )
        results.sort(key=lambda x: x["entry_count"], reverse=True)
        return results

    def detect_knowledge_gaps(self) -> list[dict[str, Any]]:
        """Detect agents with knowledge gaps (>3 non-real_time entries)."""
        agent_non_fresh: dict[str, int] = {}
        for r in self._records:
            if r.freshness_level != FreshnessLevel.REAL_TIME:
                agent_non_fresh[r.source_agent] = agent_non_fresh.get(r.source_agent, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_non_fresh.items():
            if count > 3:
                results.append(
                    {
                        "source_agent": agent,
                        "non_fresh_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_fresh_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> KnowledgeMeshReport:
        by_type: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_type[r.knowledge_type.value] = by_type.get(r.knowledge_type.value, 0) + 1
            by_scope[r.propagation_scope.value] = by_scope.get(r.propagation_scope.value, 0) + 1
        fresh_count = sum(1 for r in self._records if r.freshness_level == FreshnessLevel.REAL_TIME)
        freshness_rate = round(fresh_count / len(self._records) * 100, 2) if self._records else 0.0
        stale = sum(1 for d in self.identify_stale_knowledge())
        recs: list[str] = []
        if freshness_rate < 50.0:
            recs.append(f"Freshness rate {freshness_rate}% is below 50.0% threshold")
        if stale > 0:
            recs.append(f"{stale} agent(s) with stale knowledge")
        gaps = len(self.detect_knowledge_gaps())
        if gaps > 0:
            recs.append(f"{gaps} agent(s) detected with knowledge gaps")
        if not recs:
            recs.append("Knowledge mesh effectiveness meets targets")
        return KnowledgeMeshReport(
            total_entries=len(self._records),
            total_propagations=len(self._propagations),
            freshness_rate_pct=freshness_rate,
            by_type=by_type,
            by_scope=by_scope,
            stale_count=stale,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._propagations.clear()
        logger.info("knowledge_mesh.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.knowledge_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_entries": len(self._records),
            "total_propagations": len(self._propagations),
            "ttl_seconds": self._ttl_seconds,
            "type_distribution": type_dist,
            "unique_agents": len({r.source_agent for r in self._records}),
        }
