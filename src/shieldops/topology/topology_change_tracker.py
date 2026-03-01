"""Topology Change Tracker — track topology changes and analyze change impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeType(StrEnum):
    NODE_ADDED = "node_added"
    NODE_REMOVED = "node_removed"
    EDGE_MODIFIED = "edge_modified"
    WEIGHT_CHANGED = "weight_changed"
    DEPENDENCY_SHIFTED = "dependency_shifted"


class ChangeImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


class ChangeSource(StrEnum):
    DEPLOYMENT = "deployment"
    SCALING = "scaling"
    FAILOVER = "failover"
    CONFIGURATION = "configuration"
    MANUAL = "manual"


# --- Models ---


class TopologyChangeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    change_type: ChangeType = ChangeType.NODE_ADDED
    change_impact: ChangeImpact = ChangeImpact.NONE
    change_source: ChangeSource = ChangeSource.DEPLOYMENT
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeImpactAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    change_type: ChangeType = ChangeType.NODE_ADDED
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TopologyChangeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_impact_changes: int = 0
    avg_impact_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_impactful: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TopologyChangeTracker:
    """Track topology changes, detect unauthorized changes, analyze impact."""

    def __init__(
        self,
        max_records: int = 200000,
        max_high_impact_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_high_impact_pct = max_high_impact_pct
        self._records: list[TopologyChangeRecord] = []
        self._assessments: list[ChangeImpactAssessment] = []
        logger.info(
            "topology_change_tracker.initialized",
            max_records=max_records,
            max_high_impact_pct=max_high_impact_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_change(
        self,
        change_id: str,
        change_type: ChangeType = ChangeType.NODE_ADDED,
        change_impact: ChangeImpact = ChangeImpact.NONE,
        change_source: ChangeSource = ChangeSource.DEPLOYMENT,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TopologyChangeRecord:
        record = TopologyChangeRecord(
            change_id=change_id,
            change_type=change_type,
            change_impact=change_impact,
            change_source=change_source,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "topology_change_tracker.change_recorded",
            record_id=record.id,
            change_id=change_id,
            change_type=change_type.value,
            change_impact=change_impact.value,
        )
        return record

    def get_change(self, record_id: str) -> TopologyChangeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_changes(
        self,
        change_type: ChangeType | None = None,
        change_impact: ChangeImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TopologyChangeRecord]:
        results = list(self._records)
        if change_type is not None:
            results = [r for r in results if r.change_type == change_type]
        if change_impact is not None:
            results = [r for r in results if r.change_impact == change_impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        change_id: str,
        change_type: ChangeType = ChangeType.NODE_ADDED,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ChangeImpactAssessment:
        assessment = ChangeImpactAssessment(
            change_id=change_id,
            change_type=change_type,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "topology_change_tracker.assessment_added",
            change_id=change_id,
            change_type=change_type.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_change_distribution(self) -> dict[str, Any]:
        """Group by change_type; return count and avg impact_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.change_type.value
            type_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_changes(self) -> list[dict[str, Any]]:
        """Return changes where impact is CRITICAL or HIGH."""
        high_impacts = {ChangeImpact.CRITICAL, ChangeImpact.HIGH}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.change_impact in high_impacts:
                results.append(
                    {
                        "record_id": r.id,
                        "change_id": r.change_id,
                        "change_type": r.change_type.value,
                        "change_impact": r.change_impact.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["impact_score"], reverse=True)
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        """Group by service, avg impact_score, sort desc."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_change_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> TopologyChangeReport:
        by_type: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_type[r.change_type.value] = by_type.get(r.change_type.value, 0) + 1
            by_impact[r.change_impact.value] = by_impact.get(r.change_impact.value, 0) + 1
            by_source[r.change_source.value] = by_source.get(r.change_source.value, 0) + 1
        high_impact_changes = len(self.identify_high_impact_changes())
        avg_impact = (
            round(
                sum(r.impact_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_list = self.identify_high_impact_changes()
        top_impactful = list(dict.fromkeys(h["service"] for h in high_list))
        recs: list[str] = []
        if high_impact_changes > 0:
            recs.append(
                f"{high_impact_changes} high-impact change(s) detected"
                f" — review topology modifications"
            )
        hi_pct = round(high_impact_changes / len(self._records) * 100, 2) if self._records else 0.0
        if hi_pct > self._max_high_impact_pct:
            recs.append(
                f"High-impact rate {hi_pct}% exceeds threshold ({self._max_high_impact_pct}%)"
            )
        if not recs:
            recs.append("Topology change levels are acceptable")
        return TopologyChangeReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_impact_changes=high_impact_changes,
            avg_impact_score=avg_impact,
            by_type=by_type,
            by_impact=by_impact,
            by_source=by_source,
            top_impactful=top_impactful,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("topology_change_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.change_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_high_impact_pct": self._max_high_impact_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
