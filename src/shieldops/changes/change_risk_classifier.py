"""Change Risk Classifier — classify change risk levels and patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class RiskFactor(StrEnum):
    BLAST_RADIUS = "blast_radius"
    ROLLBACK_COMPLEXITY = "rollback_complexity"
    DEPENDENCY_COUNT = "dependency_count"
    CHANGE_FREQUENCY = "change_frequency"
    TEAM_EXPERIENCE = "team_experience"


class ClassificationMethod(StrEnum):
    RULE_BASED = "rule_based"
    ML_PREDICTED = "ml_predicted"
    HISTORICAL = "historical"
    EXPERT_OVERRIDE = "expert_override"
    HYBRID = "hybrid"


# --- Models ---


class RiskClassificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    classification_id: str = ""
    risk_level: RiskLevel = RiskLevel.MODERATE
    risk_factor: RiskFactor = RiskFactor.BLAST_RADIUS
    classification_method: ClassificationMethod = ClassificationMethod.RULE_BASED
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    classification_id: str = ""
    risk_level: RiskLevel = RiskLevel.MODERATE
    assessment_score: float = 0.0
    threshold: float = 15.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_risk_count: int = 0
    avg_risk_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_factor: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_risky_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeRiskClassifier:
    """Classify change risk levels, analyze risk factors."""

    def __init__(
        self,
        max_records: int = 200000,
        max_high_risk_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_high_risk_pct = max_high_risk_pct
        self._records: list[RiskClassificationRecord] = []
        self._assessments: list[RiskAssessment] = []
        logger.info(
            "change_risk_classifier.initialized",
            max_records=max_records,
            max_high_risk_pct=max_high_risk_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_classification(
        self,
        classification_id: str,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        risk_factor: RiskFactor = RiskFactor.BLAST_RADIUS,
        classification_method: ClassificationMethod = (ClassificationMethod.RULE_BASED),
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RiskClassificationRecord:
        record = RiskClassificationRecord(
            classification_id=classification_id,
            risk_level=risk_level,
            risk_factor=risk_factor,
            classification_method=classification_method,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_risk_classifier.classification_recorded",
            record_id=record.id,
            classification_id=classification_id,
            risk_level=risk_level.value,
            risk_factor=risk_factor.value,
        )
        return record

    def get_classification(self, record_id: str) -> RiskClassificationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_classifications(
        self,
        risk_level: RiskLevel | None = None,
        risk_factor: RiskFactor | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RiskClassificationRecord]:
        results = list(self._records)
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if risk_factor is not None:
            results = [r for r in results if r.risk_factor == risk_factor]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        classification_id: str,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        assessment_score: float = 0.0,
        threshold: float = 15.0,
        description: str = "",
    ) -> RiskAssessment:
        breached = assessment_score > threshold
        assessment = RiskAssessment(
            classification_id=classification_id,
            risk_level=risk_level,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "change_risk_classifier.assessment_added",
            classification_id=classification_id,
            risk_level=risk_level.value,
            assessment_score=assessment_score,
            breached=breached,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_risk_distribution(self) -> dict[str, Any]:
        """Group by risk_level; return count and avg risk_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.risk_level.value
            level_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risk_changes(self) -> list[dict[str, Any]]:
        """Return classifications where risk_level is CRITICAL or HIGH."""
        high_risk_levels = {
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_level in high_risk_levels:
                results.append(
                    {
                        "record_id": r.id,
                        "classification_id": r.classification_id,
                        "risk_level": r.risk_level.value,
                        "risk_factor": r.risk_factor.value,
                        "risk_score": r.risk_score,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort desc."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                    "classification_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
        """Split-half on assessment_score; delta threshold 5.0."""
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
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ChangeRiskReport:
        by_level: dict[str, int] = {}
        by_factor: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_level[r.risk_level.value] = by_level.get(r.risk_level.value, 0) + 1
            by_factor[r.risk_factor.value] = by_factor.get(r.risk_factor.value, 0) + 1
            by_method[r.classification_method.value] = (
                by_method.get(r.classification_method.value, 0) + 1
            )
        high_risk_count = sum(
            1 for r in self._records if r.risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}
        )
        avg_risk = (
            round(
                sum(r.risk_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_risk_list = self.identify_high_risk_changes()
        top_risky_services = [h["classification_id"] for h in high_risk_list]
        recs: list[str] = []
        if high_risk_count > 0:
            high_risk_pct = round(high_risk_count / len(self._records) * 100, 2)
            recs.append(
                f"{high_risk_count} high-risk change(s) detected"
                f" ({high_risk_pct}%) — review before deploying"
            )
        high_score = sum(1 for r in self._records if r.risk_score > self._max_high_risk_pct)
        if high_score > 0:
            recs.append(
                f"{high_score} classification(s) above risk threshold ({self._max_high_risk_pct}%)"
            )
        if not recs:
            recs.append("Change risk levels are acceptable")
        return ChangeRiskReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_risk_count=high_risk_count,
            avg_risk_score=avg_risk,
            by_level=by_level,
            by_factor=by_factor,
            by_method=by_method,
            top_risky_services=top_risky_services,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("change_risk_classifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_high_risk_pct": self._max_high_risk_pct,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
