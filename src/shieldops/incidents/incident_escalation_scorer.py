"""Incident Escalation Scorer — score escalation quality and effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationQuality(StrEnum):
    EXCELLENT = "excellent"
    APPROPRIATE = "appropriate"
    PREMATURE = "premature"
    LATE = "late"
    UNNECESSARY = "unnecessary"


class EscalationTarget(StrEnum):
    TIER2 = "tier2"
    TIER3 = "tier3"
    MANAGEMENT = "management"
    VENDOR = "vendor"
    EXECUTIVE = "executive"


class EscalationTrigger(StrEnum):
    SEVERITY_THRESHOLD = "severity_threshold"
    TIME_BREACH = "time_breach"
    CUSTOMER_IMPACT = "customer_impact"
    MANUAL = "manual"
    AUTOMATED = "automated"


# --- Models ---


class EscalationScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escalation_id: str = ""
    escalation_quality: EscalationQuality = EscalationQuality.APPROPRIATE
    escalation_target: EscalationTarget = EscalationTarget.TIER2
    escalation_trigger: EscalationTrigger = EscalationTrigger.MANUAL
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escalation_id: str = ""
    escalation_quality: EscalationQuality = EscalationQuality.APPROPRIATE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentEscalationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    poor_escalations: int = 0
    avg_quality_score: float = 0.0
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_target: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
    top_poor: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentEscalationScorer:
    """Score escalation quality, detect premature/late escalations."""

    def __init__(
        self,
        max_records: int = 200000,
        min_quality_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_quality_score = min_quality_score
        self._records: list[EscalationScoreRecord] = []
        self._assessments: list[EscalationAssessment] = []
        logger.info(
            "incident_escalation_scorer.initialized",
            max_records=max_records,
            min_quality_score=min_quality_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_escalation(
        self,
        escalation_id: str,
        escalation_quality: EscalationQuality = EscalationQuality.APPROPRIATE,
        escalation_target: EscalationTarget = EscalationTarget.TIER2,
        escalation_trigger: EscalationTrigger = EscalationTrigger.MANUAL,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EscalationScoreRecord:
        record = EscalationScoreRecord(
            escalation_id=escalation_id,
            escalation_quality=escalation_quality,
            escalation_target=escalation_target,
            escalation_trigger=escalation_trigger,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_escalation_scorer.escalation_recorded",
            record_id=record.id,
            escalation_id=escalation_id,
            escalation_quality=escalation_quality.value,
            escalation_target=escalation_target.value,
        )
        return record

    def get_escalation(self, record_id: str) -> EscalationScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_escalations(
        self,
        escalation_quality: EscalationQuality | None = None,
        escalation_target: EscalationTarget | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EscalationScoreRecord]:
        results = list(self._records)
        if escalation_quality is not None:
            results = [r for r in results if r.escalation_quality == escalation_quality]
        if escalation_target is not None:
            results = [r for r in results if r.escalation_target == escalation_target]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        escalation_id: str,
        escalation_quality: EscalationQuality = EscalationQuality.APPROPRIATE,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EscalationAssessment:
        assessment = EscalationAssessment(
            escalation_id=escalation_id,
            escalation_quality=escalation_quality,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "incident_escalation_scorer.assessment_added",
            escalation_id=escalation_id,
            escalation_quality=escalation_quality.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_escalation_distribution(self) -> dict[str, Any]:
        """Group by escalation_quality; return count and avg score."""
        quality_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.escalation_quality.value
            quality_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for quality, scores in quality_data.items():
            result[quality] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_escalations(self) -> list[dict[str, Any]]:
        """Return escalations where quality is PREMATURE or LATE or UNNECESSARY."""
        poor_qualities = {
            EscalationQuality.PREMATURE,
            EscalationQuality.LATE,
            EscalationQuality.UNNECESSARY,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.escalation_quality in poor_qualities:
                results.append(
                    {
                        "record_id": r.id,
                        "escalation_id": r.escalation_id,
                        "escalation_quality": r.escalation_quality.value,
                        "escalation_target": r.escalation_target.value,
                        "quality_score": r.quality_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["quality_score"], reverse=False)
        return results

    def rank_by_quality(self) -> list[dict[str, Any]]:
        """Group by service, avg quality_score, sort asc (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                    "escalation_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"], reverse=False)
        return results

    def detect_escalation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> IncidentEscalationReport:
        by_quality: dict[str, int] = {}
        by_target: dict[str, int] = {}
        by_trigger: dict[str, int] = {}
        for r in self._records:
            by_quality[r.escalation_quality.value] = (
                by_quality.get(r.escalation_quality.value, 0) + 1
            )
            by_target[r.escalation_target.value] = by_target.get(r.escalation_target.value, 0) + 1
            by_trigger[r.escalation_trigger.value] = (
                by_trigger.get(r.escalation_trigger.value, 0) + 1
            )
        poor_escalations = sum(
            1
            for r in self._records
            if r.escalation_quality
            in {
                EscalationQuality.PREMATURE,
                EscalationQuality.LATE,
                EscalationQuality.UNNECESSARY,
            }
        )
        avg_quality = (
            round(
                sum(r.quality_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        poor = self.identify_poor_escalations()
        top_poor = [p["escalation_id"] for p in poor]
        recs: list[str] = []
        if poor:
            recs.append(f"{len(poor)} poor escalation(s) detected — review escalation policies")
        low_q = sum(1 for r in self._records if r.quality_score < self._min_quality_score)
        if low_q > 0:
            recs.append(
                f"{low_q} escalation(s) below quality threshold ({self._min_quality_score}%)"
            )
        if not recs:
            recs.append("Escalation quality levels are acceptable")
        return IncidentEscalationReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            poor_escalations=poor_escalations,
            avg_quality_score=avg_quality,
            by_quality=by_quality,
            by_target=by_target,
            by_trigger=by_trigger,
            top_poor=top_poor,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("incident_escalation_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        quality_dist: dict[str, int] = {}
        for r in self._records:
            key = r.escalation_quality.value
            quality_dist[key] = quality_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_quality_score": self._min_quality_score,
            "quality_distribution": quality_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
