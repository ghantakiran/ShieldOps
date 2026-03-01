"""Knowledge Retention Tracker — track team knowledge retention, identify knowledge silos."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RetentionRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


class KnowledgeDomain(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    SECURITY = "security"
    NETWORKING = "networking"
    DATABASE = "database"


class RetentionStrategy(StrEnum):
    DOCUMENTATION = "documentation"
    CROSS_TRAINING = "cross_training"
    PAIRING = "pairing"
    ROTATION = "rotation"
    SHADOWING = "shadowing"


# --- Models ---


class RetentionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    retention_risk: RetentionRisk = RetentionRisk.NONE
    knowledge_domain: KnowledgeDomain = KnowledgeDomain.INFRASTRUCTURE
    retention_strategy: RetentionStrategy = RetentionStrategy.DOCUMENTATION
    retention_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RetentionAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    retention_risk: RetentionRisk = RetentionRisk.NONE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeRetentionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    at_risk_count: int = 0
    avg_retention_score: float = 0.0
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_at_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeRetentionTracker:
    """Track team knowledge retention, identify knowledge silos."""

    def __init__(
        self,
        max_records: int = 200000,
        min_retention_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_retention_score = min_retention_score
        self._records: list[RetentionRecord] = []
        self._assessments: list[RetentionAssessment] = []
        logger.info(
            "knowledge_retention.initialized",
            max_records=max_records,
            min_retention_score=min_retention_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_retention(
        self,
        team_id: str,
        retention_risk: RetentionRisk = RetentionRisk.NONE,
        knowledge_domain: KnowledgeDomain = KnowledgeDomain.INFRASTRUCTURE,
        retention_strategy: RetentionStrategy = RetentionStrategy.DOCUMENTATION,
        retention_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RetentionRecord:
        record = RetentionRecord(
            team_id=team_id,
            retention_risk=retention_risk,
            knowledge_domain=knowledge_domain,
            retention_strategy=retention_strategy,
            retention_score=retention_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_retention.retention_recorded",
            record_id=record.id,
            team_id=team_id,
            retention_risk=retention_risk.value,
            knowledge_domain=knowledge_domain.value,
        )
        return record

    def get_retention(self, record_id: str) -> RetentionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_retentions(
        self,
        risk: RetentionRisk | None = None,
        domain: KnowledgeDomain | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RetentionRecord]:
        results = list(self._records)
        if risk is not None:
            results = [r for r in results if r.retention_risk == risk]
        if domain is not None:
            results = [r for r in results if r.knowledge_domain == domain]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        team_id: str,
        retention_risk: RetentionRisk = RetentionRisk.NONE,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RetentionAssessment:
        assessment = RetentionAssessment(
            team_id=team_id,
            retention_risk=retention_risk,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "knowledge_retention.assessment_added",
            team_id=team_id,
            retention_risk=retention_risk.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_retention_distribution(self) -> dict[str, Any]:
        """Group by retention_risk; return count and avg retention_score."""
        risk_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.retention_risk.value
            risk_data.setdefault(key, []).append(r.retention_score)
        result: dict[str, Any] = {}
        for risk, scores in risk_data.items():
            result[risk] = {
                "count": len(scores),
                "avg_retention_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_at_risk_teams(self) -> list[dict[str, Any]]:
        """Return records where retention_risk is CRITICAL or HIGH."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.retention_risk in (RetentionRisk.CRITICAL, RetentionRisk.HIGH):
                results.append(
                    {
                        "record_id": r.id,
                        "team_id": r.team_id,
                        "retention_risk": r.retention_risk.value,
                        "retention_score": r.retention_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_retention_score(self) -> list[dict[str, Any]]:
        """Group by service, avg retention_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.retention_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_retention_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_retention_score"])
        return results

    def detect_retention_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> KnowledgeRetentionReport:
        by_risk: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_risk[r.retention_risk.value] = by_risk.get(r.retention_risk.value, 0) + 1
            by_domain[r.knowledge_domain.value] = by_domain.get(r.knowledge_domain.value, 0) + 1
            by_strategy[r.retention_strategy.value] = (
                by_strategy.get(r.retention_strategy.value, 0) + 1
            )
        at_risk_count = sum(
            1
            for r in self._records
            if r.retention_risk in (RetentionRisk.CRITICAL, RetentionRisk.HIGH)
        )
        scores = [r.retention_score for r in self._records]
        avg_retention_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        at_risk_list = self.identify_at_risk_teams()
        top_at_risk = [o["team_id"] for o in at_risk_list[:5]]
        recs: list[str] = []
        if self._records and avg_retention_score < self._min_retention_score:
            recs.append(
                f"Avg retention score {avg_retention_score} below threshold "
                f"({self._min_retention_score})"
            )
        if at_risk_count > 0:
            recs.append(f"{at_risk_count} at-risk team(s) — initiate retention strategies")
        if not recs:
            recs.append("Knowledge retention levels are healthy")
        return KnowledgeRetentionReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            at_risk_count=at_risk_count,
            avg_retention_score=avg_retention_score,
            by_risk=by_risk,
            by_domain=by_domain,
            by_strategy=by_strategy,
            top_at_risk=top_at_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("knowledge_retention.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for r in self._records:
            key = r.retention_risk.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_retention_score": self._min_retention_score,
            "retention_risk_distribution": risk_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
