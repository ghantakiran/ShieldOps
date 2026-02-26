"""Reliability Anti-Pattern Detector — detect reliability anti-patterns and plan remediation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AntiPatternType(StrEnum):
    SINGLE_POINT_OF_FAILURE = "single_point_of_failure"
    CASCADING_DEPENDENCY = "cascading_dependency"
    MISSING_RETRY = "missing_retry"
    NO_CIRCUIT_BREAKER = "no_circuit_breaker"
    SYNCHRONOUS_CHAIN = "synchronous_chain"


class DetectionMethod(StrEnum):
    STATIC_ANALYSIS = "static_analysis"
    RUNTIME_OBSERVATION = "runtime_observation"
    DEPENDENCY_GRAPH = "dependency_graph"
    FAILURE_CORRELATION = "failure_correlation"
    MANUAL_REVIEW = "manual_review"


class RemediationUrgency(StrEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    ACCEPTED_RISK = "accepted_risk"


# --- Models ---


class AntiPatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    pattern_type: AntiPatternType = AntiPatternType.SINGLE_POINT_OF_FAILURE
    detection_method: DetectionMethod = DetectionMethod.STATIC_ANALYSIS
    urgency: RemediationUrgency = RemediationUrgency.MEDIUM_TERM
    impact_score: float = 0.0
    affected_services_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    plan_name: str = ""
    urgency: RemediationUrgency = RemediationUrgency.MEDIUM_TERM
    estimated_effort_days: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReliabilityAntiPatternReport(BaseModel):
    total_patterns: int = 0
    total_plans: int = 0
    avg_impact_score: float = 0.0
    by_pattern_type: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    immediate_risk_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReliabilityAntiPatternDetector:
    """Detect reliability anti-patterns and plan remediation."""

    def __init__(
        self,
        max_records: int = 200000,
        max_accepted_risks: int = 10,
    ) -> None:
        self._max_records = max_records
        self._max_accepted_risks = max_accepted_risks
        self._records: list[AntiPatternRecord] = []
        self._plans: list[RemediationPlan] = []
        logger.info(
            "reliability_antipattern.initialized",
            max_records=max_records,
            max_accepted_risks=max_accepted_risks,
        )

    # -- record / get / list ---------------------------------------------

    def record_pattern(
        self,
        service_name: str,
        pattern_type: AntiPatternType = AntiPatternType.SINGLE_POINT_OF_FAILURE,
        detection_method: DetectionMethod = DetectionMethod.STATIC_ANALYSIS,
        urgency: RemediationUrgency = RemediationUrgency.MEDIUM_TERM,
        impact_score: float = 0.0,
        affected_services_count: int = 0,
        details: str = "",
    ) -> AntiPatternRecord:
        record = AntiPatternRecord(
            service_name=service_name,
            pattern_type=pattern_type,
            detection_method=detection_method,
            urgency=urgency,
            impact_score=impact_score,
            affected_services_count=affected_services_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reliability_antipattern.pattern_recorded",
            record_id=record.id,
            service_name=service_name,
            pattern_type=pattern_type.value,
        )
        return record

    def get_pattern(self, record_id: str) -> AntiPatternRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_patterns(
        self,
        service_name: str | None = None,
        pattern_type: AntiPatternType | None = None,
        limit: int = 50,
    ) -> list[AntiPatternRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if pattern_type is not None:
            results = [r for r in results if r.pattern_type == pattern_type]
        return results[-limit:]

    def add_remediation_plan(
        self,
        pattern_id: str,
        plan_name: str,
        urgency: RemediationUrgency = RemediationUrgency.MEDIUM_TERM,
        estimated_effort_days: float = 0.0,
        description: str = "",
    ) -> RemediationPlan:
        plan = RemediationPlan(
            pattern_id=pattern_id,
            plan_name=plan_name,
            urgency=urgency,
            estimated_effort_days=estimated_effort_days,
            description=description,
        )
        self._plans.append(plan)
        if len(self._plans) > self._max_records:
            self._plans = self._plans[-self._max_records :]
        logger.info(
            "reliability_antipattern.plan_added",
            plan_name=plan_name,
            pattern_id=pattern_id,
        )
        return plan

    # -- domain operations -----------------------------------------------

    def analyze_service_antipatterns(self, service_name: str) -> dict[str, Any]:
        """Analyze anti-patterns for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        latest = records[-1]
        return {
            "service_name": service_name,
            "total_patterns": len(records),
            "latest_type": latest.pattern_type.value,
            "latest_urgency": latest.urgency.value,
            "avg_impact_score": round(
                sum(r.impact_score for r in records) / len(records),
                2,
            ),
        }

    def identify_immediate_risks(self) -> list[dict[str, Any]]:
        """Find patterns with IMMEDIATE urgency."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.urgency == RemediationUrgency.IMMEDIATE:
                results.append(
                    {
                        "service_name": r.service_name,
                        "pattern_type": r.pattern_type.value,
                        "impact_score": r.impact_score,
                        "affected_services_count": r.affected_services_count,
                    }
                )
        results.sort(key=lambda x: x["impact_score"], reverse=True)
        return results

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Rank anti-patterns by impact score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "service_name": r.service_name,
                    "pattern_type": r.pattern_type.value,
                    "impact_score": r.impact_score,
                    "urgency": r.urgency.value,
                }
            )
        results.sort(key=lambda x: x["impact_score"], reverse=True)
        return results

    def detect_systemic_issues(self) -> list[dict[str, Any]]:
        """Detect systemic issues affecting multiple services."""
        type_services: dict[str, set[str]] = {}
        for r in self._records:
            type_services.setdefault(r.pattern_type.value, set()).add(r.service_name)
        results: list[dict[str, Any]] = []
        for ptype, services in type_services.items():
            if len(services) >= 2:
                results.append(
                    {
                        "pattern_type": ptype,
                        "affected_services": sorted(services),
                        "service_count": len(services),
                    }
                )
        results.sort(key=lambda x: x["service_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ReliabilityAntiPatternReport:
        by_type: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        for r in self._records:
            by_type[r.pattern_type.value] = by_type.get(r.pattern_type.value, 0) + 1
            by_urgency[r.urgency.value] = by_urgency.get(r.urgency.value, 0) + 1
        avg_impact = (
            round(
                sum(r.impact_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        immediate = sum(1 for r in self._records if r.urgency == RemediationUrgency.IMMEDIATE)
        recs: list[str] = []
        if immediate > 0:
            recs.append(f"{immediate} anti-pattern(s) require immediate attention")
        accepted = sum(1 for r in self._records if r.urgency == RemediationUrgency.ACCEPTED_RISK)
        if accepted > self._max_accepted_risks:
            recs.append(f"{accepted} accepted risks exceed limit of {self._max_accepted_risks}")
        if not recs:
            recs.append("Reliability anti-patterns within acceptable limits")
        return ReliabilityAntiPatternReport(
            total_patterns=len(self._records),
            total_plans=len(self._plans),
            avg_impact_score=avg_impact,
            by_pattern_type=by_type,
            by_urgency=by_urgency,
            immediate_risk_count=immediate,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._plans.clear()
        logger.info("reliability_antipattern.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pattern_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_patterns": len(self._records),
            "total_plans": len(self._plans),
            "max_accepted_risks": self._max_accepted_risks,
            "pattern_type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
