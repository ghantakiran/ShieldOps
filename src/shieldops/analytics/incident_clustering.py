"""Incident clustering engine for pattern detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────────────


class ClusterStatus(StrEnum):
    """Lifecycle status of an incident cluster."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class SimilarityMetric(StrEnum):
    """Metrics used to compute incident similarity."""

    SYMPTOM = "symptom"
    SERVICE = "service"
    TIME_WINDOW = "time_window"
    ERROR_PATTERN = "error_pattern"


# ── Models ───────────────────────────────────────────────────────────────────


class IncidentRecord(BaseModel):
    """A single incident for clustering analysis."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    service: str = ""
    symptoms: list[str] = Field(default_factory=list)
    error_pattern: str = ""
    severity: str = "medium"
    occurred_at: float = Field(default_factory=time.time)


class IncidentCluster(BaseModel):
    """A group of similar incidents."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    incident_ids: list[str] = Field(default_factory=list)
    root_cause: str = ""
    status: ClusterStatus = ClusterStatus.ACTIVE
    similarity_scores: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float | None = None


# ── Engine ───────────────────────────────────────────────────────────────────


class IncidentClusteringEngine:
    """Groups similar incidents into clusters."""

    def __init__(
        self,
        max_incidents: int = 50000,
        max_clusters: int = 5000,
        similarity_threshold: float = 0.5,
    ) -> None:
        self.max_incidents = max_incidents
        self.max_clusters = max_clusters
        self.similarity_threshold = similarity_threshold

        self._incidents: dict[str, IncidentRecord] = {}
        self._clusters: dict[str, IncidentCluster] = {}

        logger.info(
            "incident_clustering.init",
            max_incidents=max_incidents,
            max_clusters=max_clusters,
            similarity_threshold=similarity_threshold,
        )

    # ── Similarity helpers ───────────────────────────────────────────

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        """Compute Jaccard similarity between two sets."""
        if not a and not b:
            return 0.0
        intersection = a & b
        union = a | b
        return len(intersection) / len(union) if union else 0.0

    def _compute_similarity(self, a: IncidentRecord, b: IncidentRecord) -> float:
        """Compute overall similarity between two incidents."""
        score = 0.0
        weights = 0.0

        # Symptom similarity (Jaccard) — weight 0.4
        symptom_sim = self._jaccard(set(a.symptoms), set(b.symptoms))
        score += 0.4 * symptom_sim
        weights += 0.4

        # Service match — weight 0.3
        if a.service and b.service:
            service_sim = 1.0 if a.service == b.service else 0.0
            score += 0.3 * service_sim
        weights += 0.3

        # Error pattern match — weight 0.3
        if a.error_pattern and b.error_pattern:
            if a.error_pattern == b.error_pattern:
                score += 0.3
            elif a.error_pattern in b.error_pattern or b.error_pattern in a.error_pattern:
                score += 0.15
        weights += 0.3

        return round(score / weights, 4) if weights > 0 else 0.0

    # ── Incident management ──────────────────────────────────────────

    def add_incident(
        self,
        title: str,
        service: str = "",
        symptoms: list[str] | None = None,
        error_pattern: str = "",
        severity: str = "medium",
    ) -> IncidentRecord:
        """Add an incident record for clustering."""
        if len(self._incidents) >= self.max_incidents:
            oldest = next(iter(self._incidents))
            del self._incidents[oldest]

        record = IncidentRecord(
            title=title,
            service=service,
            symptoms=symptoms or [],
            error_pattern=error_pattern,
            severity=severity,
        )
        self._incidents[record.id] = record
        logger.info(
            "incident_clustering.add_incident",
            incident_id=record.id,
            title=title,
        )
        return record

    def find_similar(self, incident_id: str, limit: int = 10) -> list[tuple[str, float]]:
        """Find incidents similar to the given one."""
        target = self._incidents.get(incident_id)
        if target is None:
            return []

        scored: list[tuple[str, float]] = []
        for iid, inc in self._incidents.items():
            if iid == incident_id:
                continue
            sim = self._compute_similarity(target, inc)
            if sim > 0:
                scored.append((iid, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    # ── Cluster management ───────────────────────────────────────────

    def create_cluster(self, name: str, incident_ids: list[str]) -> IncidentCluster:
        """Manually create a cluster from incident IDs."""
        if len(self._clusters) >= self.max_clusters:
            oldest = next(iter(self._clusters))
            del self._clusters[oldest]

        valid_ids = [i for i in incident_ids if i in self._incidents]
        cluster = IncidentCluster(name=name, incident_ids=valid_ids)
        self._clusters[cluster.id] = cluster
        logger.info(
            "incident_clustering.create_cluster",
            cluster_id=cluster.id,
            incidents=len(valid_ids),
        )
        return cluster

    def auto_cluster(self, time_window_seconds: int = 3600) -> list[IncidentCluster]:
        """Auto-cluster recent incidents by similarity."""
        now = time.time()
        recent = [
            inc for inc in self._incidents.values() if now - inc.occurred_at <= time_window_seconds
        ]

        clustered_ids: set[str] = set()
        new_clusters: list[IncidentCluster] = []

        for i, inc_a in enumerate(recent):
            if inc_a.id in clustered_ids:
                continue

            group = [inc_a.id]
            scores: dict[str, Any] = {}

            for inc_b in recent[i + 1 :]:
                if inc_b.id in clustered_ids:
                    continue
                sim = self._compute_similarity(inc_a, inc_b)
                if sim >= self.similarity_threshold:
                    group.append(inc_b.id)
                    scores[inc_b.id] = sim

            if len(group) < 2:
                continue

            clustered_ids.update(group)
            cluster = IncidentCluster(
                name=f"auto-cluster-{inc_a.service or 'mixed'}",
                incident_ids=group,
                similarity_scores=scores,
            )

            if len(self._clusters) >= self.max_clusters:
                oldest = next(iter(self._clusters))
                del self._clusters[oldest]

            self._clusters[cluster.id] = cluster
            new_clusters.append(cluster)

        logger.info(
            "incident_clustering.auto_cluster",
            new_clusters=len(new_clusters),
            time_window=time_window_seconds,
        )
        return new_clusters

    def add_to_cluster(self, cluster_id: str, incident_id: str) -> IncidentCluster | None:
        """Add an incident to an existing cluster."""
        cluster = self._clusters.get(cluster_id)
        if cluster is None:
            return None
        if incident_id not in cluster.incident_ids:
            cluster.incident_ids.append(incident_id)
            cluster.updated_at = time.time()
        return cluster

    def set_root_cause(self, cluster_id: str, root_cause: str) -> IncidentCluster | None:
        """Set the root cause for a cluster."""
        cluster = self._clusters.get(cluster_id)
        if cluster is None:
            return None
        cluster.root_cause = root_cause
        cluster.updated_at = time.time()
        logger.info(
            "incident_clustering.set_root_cause",
            cluster_id=cluster_id,
        )
        return cluster

    def resolve_cluster(self, cluster_id: str) -> IncidentCluster | None:
        """Mark a cluster as resolved."""
        cluster = self._clusters.get(cluster_id)
        if cluster is None:
            return None
        cluster.status = ClusterStatus.RESOLVED
        cluster.updated_at = time.time()
        return cluster

    def get_cluster(self, cluster_id: str) -> IncidentCluster | None:
        """Get a cluster by ID."""
        return self._clusters.get(cluster_id)

    def list_clusters(self, status: ClusterStatus | None = None) -> list[IncidentCluster]:
        """List clusters with optional status filter."""
        results = list(self._clusters.values())
        if status is not None:
            results = [c for c in results if c.status == status]
        return results

    def get_cluster_trends(self, days: int = 30) -> dict[str, Any]:
        """Return cluster counts per day for recent period."""
        cutoff = time.time() - (days * 86400)
        daily: dict[str, int] = {}
        for cluster in self._clusters.values():
            if cluster.created_at < cutoff:
                continue
            day_key = time.strftime("%Y-%m-%d", time.gmtime(cluster.created_at))
            daily[day_key] = daily.get(day_key, 0) + 1
        return {
            "days": days,
            "clusters_per_day": daily,
            "total_in_period": sum(daily.values()),
        }

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        return {
            "total_incidents": len(self._incidents),
            "total_clusters": len(self._clusters),
            "clusters_by_status": {
                s.value: sum(1 for c in self._clusters.values() if c.status == s)
                for s in ClusterStatus
            },
            "avg_cluster_size": (
                round(
                    sum(len(c.incident_ids) for c in self._clusters.values()) / len(self._clusters),
                    2,
                )
                if self._clusters
                else 0.0
            ),
        }
