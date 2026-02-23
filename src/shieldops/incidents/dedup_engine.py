"""Incident Deduplication Engine — real-time duplicate detection, fingerprinting, auto-merge."""

from __future__ import annotations

import hashlib
import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DedupStrategy(StrEnum):
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    FINGERPRINT = "fingerprint"
    CONTENT_SIMILARITY = "content_similarity"


class MergeDecision(StrEnum):
    AUTO_MERGED = "auto_merged"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    MANUAL_MERGED = "manual_merged"


class IncidentSource(StrEnum):
    PAGERDUTY = "pagerduty"
    SLACK = "slack"
    EMAIL = "email"
    MONITORING = "monitoring"
    MANUAL = "manual"


# --- Models ---


class IncomingIncident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    source: IncidentSource = IncidentSource.MANUAL
    service: str = ""
    fingerprint: str = ""
    severity: str = ""
    received_at: float = Field(default_factory=time.time)


class DedupCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    duplicate_of: str
    similarity: float = 0.0
    strategy: DedupStrategy = DedupStrategy.FINGERPRINT
    decision: MergeDecision = MergeDecision.CANDIDATE
    decided_at: float | None = None


class MergedIncident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    primary_id: str
    merged_ids: list[str] = Field(default_factory=list)
    merged_at: float = Field(default_factory=time.time)
    source_count: int = 1


# --- Engine ---


class IncidentDeduplicationEngine:
    """Real-time duplicate detection across channels, fingerprinting, auto-merge."""

    def __init__(
        self,
        max_incidents: int = 100000,
        similarity_threshold: float = 0.8,
    ) -> None:
        self._max_incidents = max_incidents
        self._similarity_threshold = similarity_threshold
        self._incidents: dict[str, IncomingIncident] = {}
        self._candidates: dict[str, DedupCandidate] = {}
        self._merged: dict[str, MergedIncident] = {}
        logger.info(
            "incident_dedup.initialized",
            max_incidents=max_incidents,
            similarity_threshold=similarity_threshold,
        )

    def submit_incident(
        self,
        title: str,
        description: str = "",
        source: IncidentSource = IncidentSource.MANUAL,
        service: str = "",
        severity: str = "",
    ) -> IncomingIncident:
        fingerprint = self.compute_fingerprint(title, service)
        incident = IncomingIncident(
            title=title,
            description=description,
            source=source,
            service=service,
            fingerprint=fingerprint,
            severity=severity,
        )
        self._incidents[incident.id] = incident
        if len(self._incidents) > self._max_incidents:
            oldest = next(iter(self._incidents))
            del self._incidents[oldest]
        logger.info(
            "incident_dedup.incident_submitted",
            incident_id=incident.id,
            title=title,
        )
        return incident

    def compute_fingerprint(self, title: str, service: str = "") -> str:
        normalized = f"{title.lower().strip()}:{service.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def find_duplicates(
        self,
        incident_id: str,
        strategy: DedupStrategy = DedupStrategy.FINGERPRINT,
    ) -> list[DedupCandidate]:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return []
        candidates: list[DedupCandidate] = []
        for other in self._incidents.values():
            if other.id == incident_id:
                continue
            sim = self._compute_similarity(incident, other, strategy)
            if sim >= self._similarity_threshold:
                candidate = DedupCandidate(
                    incident_id=incident_id,
                    duplicate_of=other.id,
                    similarity=round(sim, 3),
                    strategy=strategy,
                )
                candidates.append(candidate)
                self._candidates[candidate.id] = candidate
        return candidates

    def _compute_similarity(
        self,
        a: IncomingIncident,
        b: IncomingIncident,
        strategy: DedupStrategy,
    ) -> float:
        if strategy == DedupStrategy.EXACT_MATCH:
            return 1.0 if a.title == b.title and a.service == b.service else 0.0
        if strategy == DedupStrategy.FINGERPRINT:
            return 1.0 if a.fingerprint == b.fingerprint else 0.0
        # fuzzy / content_similarity: token overlap
        tokens_a = set(a.title.lower().split())
        tokens_b = set(b.title.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        overlap = len(tokens_a & tokens_b)
        return overlap / max(len(tokens_a | tokens_b), 1)

    def auto_merge(self, incident_id: str) -> MergedIncident | None:
        candidates = [
            c
            for c in self._candidates.values()
            if c.incident_id == incident_id and c.decision == MergeDecision.CANDIDATE
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda c: c.similarity)
        best.decision = MergeDecision.AUTO_MERGED
        best.decided_at = time.time()
        merged_ids = [incident_id]
        merged = MergedIncident(
            primary_id=best.duplicate_of,
            merged_ids=merged_ids,
            source_count=len(merged_ids) + 1,
        )
        self._merged[merged.id] = merged
        logger.info(
            "incident_dedup.auto_merged",
            merged_id=merged.id,
            primary_id=best.duplicate_of,
        )
        return merged

    def manual_merge(
        self,
        primary_id: str,
        merge_ids: list[str],
    ) -> MergedIncident | None:
        if primary_id not in self._incidents:
            return None
        valid_ids = [mid for mid in merge_ids if mid in self._incidents]
        if not valid_ids:
            return None
        merged = MergedIncident(
            primary_id=primary_id,
            merged_ids=valid_ids,
            source_count=len(valid_ids) + 1,
        )
        self._merged[merged.id] = merged
        logger.info(
            "incident_dedup.manual_merged",
            merged_id=merged.id,
            primary_id=primary_id,
        )
        return merged

    def reject_candidate(self, candidate_id: str) -> DedupCandidate | None:
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            return None
        candidate.decision = MergeDecision.REJECTED
        candidate.decided_at = time.time()
        logger.info("incident_dedup.candidate_rejected", candidate_id=candidate_id)
        return candidate

    def list_candidates(
        self,
        incident_id: str | None = None,
        decision: MergeDecision | None = None,
    ) -> list[DedupCandidate]:
        results = list(self._candidates.values())
        if incident_id is not None:
            results = [c for c in results if c.incident_id == incident_id]
        if decision is not None:
            results = [c for c in results if c.decision == decision]
        return results

    def get_merged(self, merged_id: str) -> MergedIncident | None:
        return self._merged.get(merged_id)

    def list_merged(self) -> list[MergedIncident]:
        return list(self._merged.values())

    def get_stats(self) -> dict[str, Any]:
        source_counts: dict[str, int] = {}
        for i in self._incidents.values():
            source_counts[i.source] = source_counts.get(i.source, 0) + 1
        decision_counts: dict[str, int] = {}
        for c in self._candidates.values():
            decision_counts[c.decision] = decision_counts.get(c.decision, 0) + 1
        return {
            "total_incidents": len(self._incidents),
            "total_candidates": len(self._candidates),
            "total_merged": len(self._merged),
            "source_distribution": source_counts,
            "decision_distribution": decision_counts,
        }
