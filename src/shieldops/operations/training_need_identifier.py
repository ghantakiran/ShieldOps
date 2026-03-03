"""Training Need Identifier — identify and prioritize team training needs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrainingDomain(StrEnum):
    SECURITY = "security"
    CLOUD = "cloud"
    KUBERNETES = "kubernetes"
    OBSERVABILITY = "observability"
    INCIDENT_MGMT = "incident_mgmt"


class NeedUrgency(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class DeliveryMethod(StrEnum):
    SELF_PACED = "self_paced"
    INSTRUCTOR_LED = "instructor_led"
    MENTORING = "mentoring"
    WORKSHOP = "workshop"
    CERTIFICATION = "certification"


# --- Models ---


class TrainingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    team: str = ""
    training_domain: TrainingDomain = TrainingDomain.CLOUD
    need_urgency: NeedUrgency = NeedUrgency.MEDIUM
    delivery_method: DeliveryMethod = DeliveryMethod.SELF_PACED
    need_score: float = 0.0
    estimated_hours: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TrainingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    training_domain: TrainingDomain = TrainingDomain.CLOUD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TrainingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_need_score: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TrainingNeedIdentifier:
    """Identify training needs across domains and prioritize delivery methods."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TrainingRecord] = []
        self._analyses: list[TrainingAnalysis] = []
        logger.info(
            "training_need_identifier.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_training(
        self,
        engineer: str,
        team: str = "",
        training_domain: TrainingDomain = TrainingDomain.CLOUD,
        need_urgency: NeedUrgency = NeedUrgency.MEDIUM,
        delivery_method: DeliveryMethod = DeliveryMethod.SELF_PACED,
        need_score: float = 0.0,
        estimated_hours: float = 0.0,
    ) -> TrainingRecord:
        record = TrainingRecord(
            engineer=engineer,
            team=team,
            training_domain=training_domain,
            need_urgency=need_urgency,
            delivery_method=delivery_method,
            need_score=need_score,
            estimated_hours=estimated_hours,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "training_need_identifier.training_recorded",
            record_id=record.id,
            engineer=engineer,
            training_domain=training_domain.value,
            need_urgency=need_urgency.value,
        )
        return record

    def get_training(self, record_id: str) -> TrainingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_trainings(
        self,
        training_domain: TrainingDomain | None = None,
        need_urgency: NeedUrgency | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TrainingRecord]:
        results = list(self._records)
        if training_domain is not None:
            results = [r for r in results if r.training_domain == training_domain]
        if need_urgency is not None:
            results = [r for r in results if r.need_urgency == need_urgency]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        engineer: str,
        training_domain: TrainingDomain = TrainingDomain.CLOUD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TrainingAnalysis:
        analysis = TrainingAnalysis(
            engineer=engineer,
            training_domain=training_domain,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "training_need_identifier.analysis_added",
            engineer=engineer,
            training_domain=training_domain.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by training_domain; return count and avg need_score."""
        domain_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.training_domain.value
            domain_data.setdefault(key, []).append(r.need_score)
        result: dict[str, Any] = {}
        for domain, scores in domain_data.items():
            result[domain] = {
                "count": len(scores),
                "avg_need_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_training_gaps(self) -> list[dict[str, Any]]:
        """Return records where need_score >= threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.need_score >= self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "engineer": r.engineer,
                        "training_domain": r.training_domain.value,
                        "need_score": r.need_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["need_score"], reverse=True)

    def rank_by_need(self) -> list[dict[str, Any]]:
        """Group by engineer, avg need_score, sort descending."""
        eng_scores: dict[str, list[float]] = {}
        for r in self._records:
            eng_scores.setdefault(r.engineer, []).append(r.need_score)
        results: list[dict[str, Any]] = []
        for engineer, scores in eng_scores.items():
            results.append(
                {
                    "engineer": engineer,
                    "avg_need_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_need_score"], reverse=True)
        return results

    def detect_training_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "worsening"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> TrainingReport:
        by_domain: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_domain[r.training_domain.value] = by_domain.get(r.training_domain.value, 0) + 1
            by_urgency[r.need_urgency.value] = by_urgency.get(r.need_urgency.value, 0) + 1
            by_method[r.delivery_method.value] = by_method.get(r.delivery_method.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.need_score >= self._threshold)
        scores = [r.need_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_training_gaps()
        top_gaps = [o["engineer"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} engineer(s) above training need threshold ({self._threshold})"
            )
        if self._records and avg_score >= self._threshold:
            recs.append(f"Avg need score {avg_score} at or above threshold ({self._threshold})")
        if not recs:
            recs.append("Training needs are at healthy levels")
        return TrainingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_need_score=avg_score,
            by_domain=by_domain,
            by_urgency=by_urgency,
            by_method=by_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("training_need_identifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.training_domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "domain_distribution": domain_dist,
            "unique_engineers": len({r.engineer for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
