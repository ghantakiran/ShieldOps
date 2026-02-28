"""Incident Knowledge Linker — link incidents to relevant knowledge resources."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LinkType(StrEnum):
    RUNBOOK = "runbook"
    POSTMORTEM = "postmortem"
    DOCUMENTATION = "documentation"
    TRAINING = "training"
    SIMILAR_INCIDENT = "similar_incident"


class LinkRelevance(StrEnum):
    EXACT_MATCH = "exact_match"
    HIGHLY_RELEVANT = "highly_relevant"
    SOMEWHAT_RELEVANT = "somewhat_relevant"
    LOOSELY_RELATED = "loosely_related"
    NOT_RELEVANT = "not_relevant"


class KnowledgeSource(StrEnum):
    INTERNAL_WIKI = "internal_wiki"
    RUNBOOK_LIBRARY = "runbook_library"
    INCIDENT_HISTORY = "incident_history"
    EXTERNAL_DOCS = "external_docs"
    AI_GENERATED = "ai_generated"


# --- Models ---


class KnowledgeLinkRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    incident_id: str = ""
    knowledge_resource_id: str = ""
    link_type: LinkType = LinkType.DOCUMENTATION
    relevance: LinkRelevance = LinkRelevance.SOMEWHAT_RELEVANT
    knowledge_source: KnowledgeSource = KnowledgeSource.INTERNAL_WIKI
    relevance_score_pct: float = 0.0
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class LinkSuggestion(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    incident_pattern: str = ""
    suggested_resource_id: str = ""
    link_type: LinkType = LinkType.RUNBOOK
    knowledge_source: KnowledgeSource = KnowledgeSource.RUNBOOK_LIBRARY
    confidence_pct: float = 0.0
    auto_link: bool = False
    created_at: float = Field(default_factory=time.time)


class KnowledgeLinkerReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_links: int = 0
    total_suggestions: int = 0
    avg_relevance_score_pct: float = 0.0
    by_link_type: dict[str, int] = Field(default_factory=dict)
    by_knowledge_source: dict[str, int] = Field(default_factory=dict)
    unlinked_incident_count: int = 0
    high_relevance_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentKnowledgeLinker:
    """Link incidents to relevant knowledge resources."""

    def __init__(
        self,
        max_records: int = 200000,
        min_relevance_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_relevance_pct = min_relevance_pct
        self._records: list[KnowledgeLinkRecord] = []
        self._suggestions: list[LinkSuggestion] = []
        logger.info(
            "knowledge_linker.initialized",
            max_records=max_records,
            min_relevance_pct=min_relevance_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_link(
        self,
        incident_id: str,
        knowledge_resource_id: str = "",
        link_type: LinkType = LinkType.DOCUMENTATION,
        relevance: LinkRelevance = LinkRelevance.SOMEWHAT_RELEVANT,
        knowledge_source: KnowledgeSource = KnowledgeSource.INTERNAL_WIKI,
        relevance_score_pct: float = 0.0,
        notes: str = "",
    ) -> KnowledgeLinkRecord:
        record = KnowledgeLinkRecord(
            incident_id=incident_id,
            knowledge_resource_id=knowledge_resource_id,
            link_type=link_type,
            relevance=relevance,
            knowledge_source=knowledge_source,
            relevance_score_pct=relevance_score_pct,
            notes=notes,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_linker.link_recorded",
            record_id=record.id,
            incident_id=incident_id,
            link_type=link_type.value,
            relevance=relevance.value,
        )
        return record

    def get_link(self, record_id: str) -> KnowledgeLinkRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_links(
        self,
        incident_id: str | None = None,
        link_type: LinkType | None = None,
        limit: int = 50,
    ) -> list[KnowledgeLinkRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if link_type is not None:
            results = [r for r in results if r.link_type == link_type]
        return results[-limit:]

    def add_suggestion(
        self,
        incident_pattern: str,
        suggested_resource_id: str = "",
        link_type: LinkType = LinkType.RUNBOOK,
        knowledge_source: KnowledgeSource = KnowledgeSource.RUNBOOK_LIBRARY,
        confidence_pct: float = 0.0,
        auto_link: bool = False,
    ) -> LinkSuggestion:
        suggestion = LinkSuggestion(
            incident_pattern=incident_pattern,
            suggested_resource_id=suggested_resource_id,
            link_type=link_type,
            knowledge_source=knowledge_source,
            confidence_pct=confidence_pct,
            auto_link=auto_link,
        )
        self._suggestions.append(suggestion)
        if len(self._suggestions) > self._max_records:
            self._suggestions = self._suggestions[-self._max_records :]
        logger.info(
            "knowledge_linker.suggestion_added",
            incident_pattern=incident_pattern,
            link_type=link_type.value,
            confidence_pct=confidence_pct,
        )
        return suggestion

    # -- domain operations -----------------------------------------------

    def analyze_link_effectiveness(self, incident_id: str) -> dict[str, Any]:
        """Analyze link effectiveness for a specific incident."""
        records = [r for r in self._records if r.incident_id == incident_id]
        if not records:
            return {"incident_id": incident_id, "status": "no_data"}
        avg_score = round(sum(r.relevance_score_pct for r in records) / len(records), 2)
        high_rel_count = sum(
            1
            for r in records
            if r.relevance in (LinkRelevance.EXACT_MATCH, LinkRelevance.HIGHLY_RELEVANT)
        )
        return {
            "incident_id": incident_id,
            "link_count": len(records),
            "avg_relevance_score_pct": avg_score,
            "high_relevance_count": high_rel_count,
            "meets_threshold": avg_score >= self._min_relevance_pct,
        }

    def identify_unlinked_incidents(self) -> list[dict[str, Any]]:
        """Find incidents that appear only once with low relevance score."""
        incident_counts: dict[str, int] = {}
        for r in self._records:
            incident_counts[r.incident_id] = incident_counts.get(r.incident_id, 0) + 1
        results: list[dict[str, Any]] = []
        for incident_id, count in incident_counts.items():
            if count == 1:
                record = next(r for r in self._records if r.incident_id == incident_id)
                if record.relevance_score_pct < self._min_relevance_pct:
                    results.append(
                        {
                            "incident_id": incident_id,
                            "link_count": count,
                            "relevance_score_pct": record.relevance_score_pct,
                            "needs_linking": True,
                        }
                    )
        results.sort(key=lambda x: x["relevance_score_pct"])
        return results

    def rank_by_relevance_score(self) -> list[dict[str, Any]]:
        """Rank links by relevance score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "incident_id": r.incident_id,
                    "knowledge_resource_id": r.knowledge_resource_id,
                    "link_type": r.link_type.value,
                    "relevance": r.relevance.value,
                    "relevance_score_pct": r.relevance_score_pct,
                }
            )
        results.sort(key=lambda x: x["relevance_score_pct"], reverse=True)
        return results

    def detect_knowledge_gaps(self) -> list[dict[str, Any]]:
        """Detect incident patterns without high-confidence suggestions."""
        high_conf_patterns: set[str] = {
            s.incident_pattern
            for s in self._suggestions
            if s.confidence_pct >= self._min_relevance_pct
        }
        all_patterns: set[str] = {s.incident_pattern for s in self._suggestions}
        gap_patterns = all_patterns - high_conf_patterns
        results: list[dict[str, Any]] = []
        for pattern in gap_patterns:
            matching = [s for s in self._suggestions if s.incident_pattern == pattern]
            max_conf = max((s.confidence_pct for s in matching), default=0.0)
            results.append(
                {
                    "incident_pattern": pattern,
                    "max_confidence_pct": max_conf,
                    "suggestion_count": len(matching),
                    "gap_detected": True,
                }
            )
        results.sort(key=lambda x: x["max_confidence_pct"])
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> KnowledgeLinkerReport:
        by_link_type: dict[str, int] = {}
        by_knowledge_source: dict[str, int] = {}
        total_score = 0.0
        for r in self._records:
            by_link_type[r.link_type.value] = by_link_type.get(r.link_type.value, 0) + 1
            by_knowledge_source[r.knowledge_source.value] = (
                by_knowledge_source.get(r.knowledge_source.value, 0) + 1
            )
            total_score += r.relevance_score_pct
        avg_score = round(total_score / len(self._records), 2) if self._records else 0.0
        high_relevance_count = sum(
            1
            for r in self._records
            if r.relevance in (LinkRelevance.EXACT_MATCH, LinkRelevance.HIGHLY_RELEVANT)
        )
        unlinked_count = len(self.identify_unlinked_incidents())
        recs: list[str] = []
        if avg_score < self._min_relevance_pct and self._records:
            recs.append(
                f"Average relevance score {avg_score}% is below"
                f" threshold {self._min_relevance_pct}%"
            )
        if unlinked_count > 0:
            recs.append(f"{unlinked_count} incident(s) have insufficient knowledge links")
        gap_count = len(self.detect_knowledge_gaps())
        if gap_count > 0:
            recs.append(f"{gap_count} knowledge gap(s) detected in suggestion coverage")
        if not recs:
            recs.append("Incident knowledge linking meets targets")
        return KnowledgeLinkerReport(
            total_links=len(self._records),
            total_suggestions=len(self._suggestions),
            avg_relevance_score_pct=avg_score,
            by_link_type=by_link_type,
            by_knowledge_source=by_knowledge_source,
            unlinked_incident_count=unlinked_count,
            high_relevance_count=high_relevance_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._suggestions.clear()
        logger.info("knowledge_linker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        link_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.link_type.value
            link_type_dist[key] = link_type_dist.get(key, 0) + 1
        return {
            "total_links": len(self._records),
            "total_suggestions": len(self._suggestions),
            "min_relevance_pct": self._min_relevance_pct,
            "link_type_distribution": link_type_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
