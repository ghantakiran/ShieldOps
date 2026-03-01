"""Incident Cluster Engine — cluster incidents by method, size, and confidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ClusterMethod(StrEnum):
    SYMPTOM = "symptom"
    ROOT_CAUSE = "root_cause"
    SERVICE_AFFINITY = "service_affinity"
    TIMELINE_PROXIMITY = "timeline_proximity"
    IMPACT_PATTERN = "impact_pattern"


class ClusterSize(StrEnum):
    SINGLE = "single"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    STORM = "storm"


class ClusterStatus(StrEnum):
    FORMING = "forming"
    ACTIVE = "active"
    RESOLVED = "resolved"
    MERGED = "merged"
    SPLIT = "split"


# --- Models ---


class ClusterRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    cluster_method: ClusterMethod = ClusterMethod.SYMPTOM
    cluster_size: ClusterSize = ClusterSize.SINGLE
    cluster_status: ClusterStatus = ClusterStatus.FORMING
    confidence_score: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ClusterMember(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cluster_id: str = ""
    incident_id: str = ""
    similarity_score: float = 0.0
    joined_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class IncidentClusterReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_members: int = 0
    active_clusters: int = 0
    avg_confidence_score: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_size: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    storm_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentClusterEngine:
    """Cluster incidents by symptom, root cause, affinity, proximity, and pattern."""

    def __init__(
        self,
        max_records: int = 200000,
        min_cluster_confidence: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_cluster_confidence = min_cluster_confidence
        self._records: list[ClusterRecord] = []
        self._members: list[ClusterMember] = []
        logger.info(
            "incident_cluster.initialized",
            max_records=max_records,
            min_cluster_confidence=min_cluster_confidence,
        )

    # -- record / get / list ------------------------------------------------

    def record_cluster(
        self,
        incident_id: str,
        cluster_method: ClusterMethod = ClusterMethod.SYMPTOM,
        cluster_size: ClusterSize = ClusterSize.SINGLE,
        cluster_status: ClusterStatus = ClusterStatus.FORMING,
        confidence_score: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> ClusterRecord:
        record = ClusterRecord(
            incident_id=incident_id,
            cluster_method=cluster_method,
            cluster_size=cluster_size,
            cluster_status=cluster_status,
            confidence_score=confidence_score,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_cluster.cluster_recorded",
            record_id=record.id,
            incident_id=incident_id,
            cluster_method=cluster_method.value,
            cluster_size=cluster_size.value,
        )
        return record

    def get_cluster(self, record_id: str) -> ClusterRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_clusters(
        self,
        method: ClusterMethod | None = None,
        size: ClusterSize | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ClusterRecord]:
        results = list(self._records)
        if method is not None:
            results = [r for r in results if r.cluster_method == method]
        if size is not None:
            results = [r for r in results if r.cluster_size == size]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_member(
        self,
        cluster_id: str,
        incident_id: str,
        similarity_score: float = 0.0,
    ) -> ClusterMember:
        member = ClusterMember(
            cluster_id=cluster_id,
            incident_id=incident_id,
            similarity_score=similarity_score,
        )
        self._members.append(member)
        if len(self._members) > self._max_records:
            self._members = self._members[-self._max_records :]
        logger.info(
            "incident_cluster.member_added",
            cluster_id=cluster_id,
            incident_id=incident_id,
            similarity_score=similarity_score,
        )
        return member

    # -- domain operations --------------------------------------------------

    def analyze_cluster_patterns(self) -> dict[str, Any]:
        """Group clusters by method; return count and avg confidence per method."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cluster_method.value
            method_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_confidence": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_incident_storms(self) -> list[dict[str, Any]]:
        """Return clusters whose size is LARGE or STORM."""
        storm_sizes = {ClusterSize.LARGE, ClusterSize.STORM}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.cluster_size in storm_sizes:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "cluster_size": r.cluster_size.value,
                        "cluster_status": r.cluster_status.value,
                        "confidence_score": r.confidence_score,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["confidence_score"], reverse=True)
        return results

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by team, compute avg confidence, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_confidence": round(sum(scores) / len(scores), 2),
                    "cluster_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_confidence"], reverse=True)
        return results

    def detect_cluster_trends(self) -> dict[str, Any]:
        """Split-half comparison on confidence_scores; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.confidence_score for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> IncidentClusterReport:
        by_method: dict[str, int] = {}
        by_size: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_method[r.cluster_method.value] = by_method.get(r.cluster_method.value, 0) + 1
            by_size[r.cluster_size.value] = by_size.get(r.cluster_size.value, 0) + 1
            by_status[r.cluster_status.value] = by_status.get(r.cluster_status.value, 0) + 1
        active_clusters = sum(1 for r in self._records if r.cluster_status == ClusterStatus.ACTIVE)
        avg_confidence = (
            round(
                sum(r.confidence_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        storms = self.identify_incident_storms()
        storm_alerts = [s["incident_id"] for s in storms]
        recs: list[str] = []
        if storms:
            recs.append(f"{len(storms)} incident storm(s) detected — escalate immediately")
        low_conf = sum(
            1 for r in self._records if r.confidence_score < self._min_cluster_confidence
        )
        if low_conf > 0:
            recs.append(
                f"{low_conf} cluster(s) below confidence threshold "
                f"({self._min_cluster_confidence}%)"
            )
        if not recs:
            recs.append("Cluster confidence levels are healthy")
        return IncidentClusterReport(
            total_records=len(self._records),
            total_members=len(self._members),
            active_clusters=active_clusters,
            avg_confidence_score=avg_confidence,
            by_method=by_method,
            by_size=by_size,
            by_status=by_status,
            storm_alerts=storm_alerts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._members.clear()
        logger.info("incident_cluster.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cluster_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_members": len(self._members),
            "min_cluster_confidence": self._min_cluster_confidence,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
