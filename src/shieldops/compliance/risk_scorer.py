"""Compliance Risk Scorer — score compliance risks, identify critical controls."""

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
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class RiskDomain(StrEnum):
    DATA_PRIVACY = "data_privacy"
    ACCESS_CONTROL = "access_control"
    ENCRYPTION = "encryption"
    AUDIT_LOGGING = "audit_logging"
    CHANGE_MANAGEMENT = "change_management"


class AssessmentStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    SCHEDULED = "scheduled"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


# --- Models ---


class RiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    risk_domain: RiskDomain = RiskDomain.DATA_PRIVACY
    assessment_status: AssessmentStatus = AssessmentStatus.SCHEDULED
    risk_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_pattern: str = ""
    risk_domain: RiskDomain = RiskDomain.DATA_PRIVACY
    max_acceptable_risk: float = 0.0
    review_frequency_days: int = 90
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    high_risk_count: int = 0
    avg_risk_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    critical_risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceRiskScorer:
    """Score compliance risks, identify critical controls, track risk trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_risk_score: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._max_risk_score = max_risk_score
        self._records: list[RiskRecord] = []
        self._rules: list[RiskRule] = []
        logger.info(
            "risk_scorer.initialized",
            max_records=max_records,
            max_risk_score=max_risk_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_risk(
        self,
        control_id: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        risk_domain: RiskDomain = RiskDomain.DATA_PRIVACY,
        assessment_status: AssessmentStatus = AssessmentStatus.SCHEDULED,
        risk_score: float = 0.0,
        team: str = "",
    ) -> RiskRecord:
        record = RiskRecord(
            control_id=control_id,
            risk_level=risk_level,
            risk_domain=risk_domain,
            assessment_status=assessment_status,
            risk_score=risk_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_scorer.risk_recorded",
            record_id=record.id,
            control_id=control_id,
            risk_level=risk_level.value,
            risk_domain=risk_domain.value,
        )
        return record

    def get_risk(self, record_id: str) -> RiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_risks(
        self,
        risk_level: RiskLevel | None = None,
        risk_domain: RiskDomain | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RiskRecord]:
        results = list(self._records)
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if risk_domain is not None:
            results = [r for r in results if r.risk_domain == risk_domain]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        domain_pattern: str,
        risk_domain: RiskDomain = RiskDomain.DATA_PRIVACY,
        max_acceptable_risk: float = 0.0,
        review_frequency_days: int = 90,
        description: str = "",
    ) -> RiskRule:
        rule = RiskRule(
            domain_pattern=domain_pattern,
            risk_domain=risk_domain,
            max_acceptable_risk=max_acceptable_risk,
            review_frequency_days=review_frequency_days,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "risk_scorer.rule_added",
            domain_pattern=domain_pattern,
            risk_domain=risk_domain.value,
            max_acceptable_risk=max_acceptable_risk,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_risk_distribution(self) -> dict[str, Any]:
        """Group by risk_level; return count and avg risk_score per level."""
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

    def identify_critical_risks(self) -> list[dict[str, Any]]:
        """Return records where risk_level is CRITICAL or HIGH."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                results.append(
                    {
                        "record_id": r.id,
                        "control_id": r.control_id,
                        "risk_level": r.risk_level.value,
                        "risk_score": r.risk_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by team, average risk_score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
        """Split-half on risk_score; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.risk_score for r in self._records]
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

    def generate_report(self) -> ComplianceRiskReport:
        by_level: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_level[r.risk_level.value] = by_level.get(r.risk_level.value, 0) + 1
            by_domain[r.risk_domain.value] = by_domain.get(r.risk_domain.value, 0) + 1
            by_status[r.assessment_status.value] = by_status.get(r.assessment_status.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
        )
        avg_score = (
            round(sum(r.risk_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        critical_ids = [r.control_id for r in self._records if r.risk_level == RiskLevel.CRITICAL][
            :5
        ]
        recs: list[str] = []
        if high_risk_count > 0:
            recs.append(f"{high_risk_count} high/critical risk(s) detected — review controls")
        if avg_score > self._max_risk_score:
            recs.append(
                f"Average risk score {avg_score} exceeds threshold ({self._max_risk_score})"
            )
        if not recs:
            recs.append("Compliance risk levels are acceptable")
        return ComplianceRiskReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            high_risk_count=high_risk_count,
            avg_risk_score=avg_score,
            by_level=by_level,
            by_domain=by_domain,
            by_status=by_status,
            critical_risks=critical_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("risk_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_risk_score": self._max_risk_score,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_controls": len({r.control_id for r in self._records}),
        }
