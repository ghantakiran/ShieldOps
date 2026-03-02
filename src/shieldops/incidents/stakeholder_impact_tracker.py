"""Stakeholder Impact Tracker — track and analyze stakeholder impact from incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StakeholderGroup(StrEnum):
    EXECUTIVE = "executive"
    ENGINEERING = "engineering"
    PRODUCT = "product"
    CUSTOMER_SUCCESS = "customer_success"
    OPERATIONS = "operations"


class ImpactLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class CommunicationChannel(StrEnum):
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    STATUS_PAGE = "status_page"
    PHONE = "phone"


# --- Models ---


class StakeholderRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    stakeholder_group: StakeholderGroup = StakeholderGroup.EXECUTIVE
    impact_level: ImpactLevel = ImpactLevel.CRITICAL
    communication_channel: CommunicationChannel = CommunicationChannel.EMAIL
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class StakeholderAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    stakeholder_group: StakeholderGroup = StakeholderGroup.EXECUTIVE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class StakeholderImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_impact_count: int = 0
    avg_impact_score: float = 0.0
    by_group: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_channel: dict[str, int] = Field(default_factory=dict)
    top_high_impact: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class StakeholderImpactTracker:
    """Track stakeholder impact, identify high-impact stakeholders, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        impact_score_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._impact_score_threshold = impact_score_threshold
        self._records: list[StakeholderRecord] = []
        self._assessments: list[StakeholderAssessment] = []
        logger.info(
            "stakeholder_impact_tracker.initialized",
            max_records=max_records,
            impact_score_threshold=impact_score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_impact(
        self,
        incident_id: str,
        stakeholder_group: StakeholderGroup = StakeholderGroup.EXECUTIVE,
        impact_level: ImpactLevel = ImpactLevel.CRITICAL,
        communication_channel: CommunicationChannel = CommunicationChannel.EMAIL,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> StakeholderRecord:
        record = StakeholderRecord(
            incident_id=incident_id,
            stakeholder_group=stakeholder_group,
            impact_level=impact_level,
            communication_channel=communication_channel,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "stakeholder_impact_tracker.impact_recorded",
            record_id=record.id,
            incident_id=incident_id,
            stakeholder_group=stakeholder_group.value,
            impact_level=impact_level.value,
        )
        return record

    def get_impact(self, record_id: str) -> StakeholderRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        stakeholder_group: StakeholderGroup | None = None,
        impact_level: ImpactLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[StakeholderRecord]:
        results = list(self._records)
        if stakeholder_group is not None:
            results = [r for r in results if r.stakeholder_group == stakeholder_group]
        if impact_level is not None:
            results = [r for r in results if r.impact_level == impact_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        incident_id: str,
        stakeholder_group: StakeholderGroup = StakeholderGroup.EXECUTIVE,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> StakeholderAssessment:
        assessment = StakeholderAssessment(
            incident_id=incident_id,
            stakeholder_group=stakeholder_group,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "stakeholder_impact_tracker.assessment_added",
            incident_id=incident_id,
            stakeholder_group=stakeholder_group.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_impact_distribution(self) -> dict[str, Any]:
        """Group by stakeholder_group; return count and avg score."""
        group_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.stakeholder_group.value
            group_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for group, scores in group_data.items():
            result[group] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_stakeholders(self) -> list[dict[str, Any]]:
        """Return records where impact_score > threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_score > self._impact_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "stakeholder_group": r.stakeholder_group.value,
                        "impact_level": r.impact_level.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["impact_score"], reverse=True)
        return results

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Group by service, avg impact_score, sort desc (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                    "impact_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_impact_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta 5.0."""
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

    def generate_report(self) -> StakeholderImpactReport:
        by_group: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        for r in self._records:
            by_group[r.stakeholder_group.value] = by_group.get(r.stakeholder_group.value, 0) + 1
            by_level[r.impact_level.value] = by_level.get(r.impact_level.value, 0) + 1
            by_channel[r.communication_channel.value] = (
                by_channel.get(r.communication_channel.value, 0) + 1
            )
        high_impact_count = sum(
            1 for r in self._records if r.impact_score > self._impact_score_threshold
        )
        avg_impact = (
            round(
                sum(r.impact_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high = self.identify_high_impact_stakeholders()
        top_high_impact = [h["incident_id"] for h in high]
        recs: list[str] = []
        if high:
            recs.append(
                f"{len(high)} high-impact stakeholder(s) detected — review communication plans"
            )
        low_s = sum(1 for r in self._records if r.impact_score < self._impact_score_threshold)
        if low_s > 0:
            recs.append(f"{low_s} impact(s) below threshold ({self._impact_score_threshold}%)")
        if not recs:
            recs.append("Stakeholder impact levels are acceptable")
        return StakeholderImpactReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_impact_count=high_impact_count,
            avg_impact_score=avg_impact,
            by_group=by_group,
            by_level=by_level,
            by_channel=by_channel,
            top_high_impact=top_high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("stakeholder_impact_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        group_dist: dict[str, int] = {}
        for r in self._records:
            key = r.stakeholder_group.value
            group_dist[key] = group_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "impact_score_threshold": self._impact_score_threshold,
            "group_distribution": group_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
