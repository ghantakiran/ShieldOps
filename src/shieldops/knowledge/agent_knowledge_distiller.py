"""Agent Knowledge Distiller

Distill, compress, and prioritize agent learnings
for efficient knowledge retention and transfer.
"""

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
    PROCEDURAL = "procedural"
    DECLARATIVE = "declarative"
    HEURISTIC = "heuristic"
    CONTEXTUAL = "contextual"


class DistillationMethod(StrEnum):
    SUMMARIZATION = "summarization"
    COMPRESSION = "compression"
    EXTRACTION = "extraction"
    SYNTHESIS = "synthesis"


class RetentionPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class KnowledgeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    knowledge_type: KnowledgeType = KnowledgeType.PROCEDURAL
    method: DistillationMethod = DistillationMethod.SUMMARIZATION
    priority: RetentionPriority = RetentionPriority.MEDIUM
    density_score: float = 0.0
    agent_id: str = ""
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    knowledge_type: KnowledgeType = KnowledgeType.PROCEDURAL
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_density: float = 0.0
    critical_count: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentKnowledgeDistiller:
    """Distill and prioritize agent learnings for
    efficient knowledge retention and transfer.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[KnowledgeRecord] = []
        self._analyses: dict[str, KnowledgeAnalysis] = {}
        logger.info(
            "agent_knowledge_distiller.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        topic: str = "",
        knowledge_type: KnowledgeType = (KnowledgeType.PROCEDURAL),
        method: DistillationMethod = (DistillationMethod.SUMMARIZATION),
        priority: RetentionPriority = (RetentionPriority.MEDIUM),
        density_score: float = 0.0,
        agent_id: str = "",
        service: str = "",
    ) -> KnowledgeRecord:
        record = KnowledgeRecord(
            topic=topic,
            knowledge_type=knowledge_type,
            method=method,
            priority=priority,
            density_score=density_score,
            agent_id=agent_id,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "agent_knowledge_distiller.record_added",
            record_id=record.id,
            topic=topic,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = KnowledgeAnalysis(
            topic=rec.topic,
            knowledge_type=rec.knowledge_type,
            analysis_score=rec.density_score,
            description=(f"Knowledge {rec.topic} density={rec.density_score}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "score": analysis.analysis_score,
        }

    def generate_report(self) -> KnowledgeReport:
        by_type: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_prio: dict[str, int] = {}
        critical = 0
        densities: list[float] = []
        for r in self._records:
            t = r.knowledge_type.value
            by_type[t] = by_type.get(t, 0) + 1
            m = r.method.value
            by_method[m] = by_method.get(m, 0) + 1
            p = r.priority.value
            by_prio[p] = by_prio.get(p, 0) + 1
            if r.priority == RetentionPriority.CRITICAL:
                critical += 1
            densities.append(r.density_score)
        avg_d = round(sum(densities) / len(densities), 4) if densities else 0.0
        recs: list[str] = []
        if avg_d < 0.3:
            recs.append("Low knowledge density — improve distillation methods")
        if not recs:
            recs.append("Knowledge distillation is healthy")
        return KnowledgeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_density=avg_d,
            critical_count=critical,
            by_type=by_type,
            by_method=by_method,
            by_priority=by_prio,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.knowledge_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("agent_knowledge_distiller.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def distill_agent_learnings(self, agent_id: str) -> list[dict[str, Any]]:
        """Distill learnings for a specific agent."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        return [
            {
                "topic": r.topic,
                "knowledge_type": r.knowledge_type.value,
                "density_score": r.density_score,
                "priority": r.priority.value,
            }
            for r in sorted(
                matching,
                key=lambda x: x.density_score,
                reverse=True,
            )
        ]

    def compute_knowledge_density(self, agent_id: str) -> dict[str, Any]:
        """Compute knowledge density for an agent."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        densities = [r.density_score for r in matching]
        return {
            "agent_id": agent_id,
            "avg_density": round(sum(densities) / len(densities), 4),
            "max_density": max(densities),
            "topic_count": len(matching),
        }

    def identify_knowledge_gaps(self, agent_id: str) -> list[dict[str, Any]]:
        """Identify knowledge gaps for an agent."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        gaps = [r for r in matching if r.density_score < 0.3]
        return [
            {
                "topic": r.topic,
                "density_score": r.density_score,
                "knowledge_type": r.knowledge_type.value,
            }
            for r in gaps
        ]
