"""Reliability Automation Engine — auto-adjust reliability targets and degradation response."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AdjustmentType(StrEnum):
    TIGHTEN_SLO = "tighten_slo"
    RELAX_SLO = "relax_slo"
    ADD_REDUNDANCY = "add_redundancy"
    INCREASE_MONITORING = "increase_monitoring"
    TRIGGER_RUNBOOK = "trigger_runbook"


class AdjustmentTrigger(StrEnum):
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    DEGRADATION_DETECTED = "degradation_detected"
    ERROR_BUDGET_LOW = "error_budget_low"
    INCIDENT_PATTERN = "incident_pattern"
    MANUAL = "manual"


class AdjustmentOutcome(StrEnum):
    APPLIED = "applied"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"
    SCHEDULED = "scheduled"


# --- Models ---


class AdjustmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    adjustment_type: AdjustmentType = AdjustmentType.TIGHTEN_SLO
    adjustment_trigger: AdjustmentTrigger = AdjustmentTrigger.PERFORMANCE_IMPROVEMENT
    adjustment_outcome: AdjustmentOutcome = AdjustmentOutcome.APPLIED
    impact_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AdjustmentRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    adjustment_type: AdjustmentType = AdjustmentType.ADD_REDUNDANCY
    adjustment_trigger: AdjustmentTrigger = AdjustmentTrigger.DEGRADATION_DETECTED
    threshold_value: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ReliabilityAutomatorReport(BaseModel):
    total_adjustments: int = 0
    total_rules: int = 0
    applied_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    rejection_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReliabilityAutomationEngine:
    """Auto-adjust reliability targets and degradation response."""

    def __init__(
        self,
        max_records: int = 200000,
        min_impact_score: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._min_impact_score = min_impact_score
        self._records: list[AdjustmentRecord] = []
        self._rules: list[AdjustmentRule] = []
        logger.info(
            "reliability_automation_engine.initialized",
            max_records=max_records,
            min_impact_score=min_impact_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_adjustment(
        self,
        service_name: str,
        adjustment_type: AdjustmentType = AdjustmentType.TIGHTEN_SLO,
        adjustment_trigger: AdjustmentTrigger = AdjustmentTrigger.PERFORMANCE_IMPROVEMENT,
        adjustment_outcome: AdjustmentOutcome = AdjustmentOutcome.APPLIED,
        impact_score: float = 0.0,
        details: str = "",
    ) -> AdjustmentRecord:
        record = AdjustmentRecord(
            service_name=service_name,
            adjustment_type=adjustment_type,
            adjustment_trigger=adjustment_trigger,
            adjustment_outcome=adjustment_outcome,
            impact_score=impact_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reliability_automation_engine.adjustment_recorded",
            record_id=record.id,
            service_name=service_name,
            adjustment_outcome=adjustment_outcome.value,
        )
        return record

    def get_adjustment(self, record_id: str) -> AdjustmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_adjustments(
        self,
        service_name: str | None = None,
        adjustment_type: AdjustmentType | None = None,
        limit: int = 50,
    ) -> list[AdjustmentRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if adjustment_type is not None:
            results = [r for r in results if r.adjustment_type == adjustment_type]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        adjustment_type: AdjustmentType = AdjustmentType.ADD_REDUNDANCY,
        adjustment_trigger: AdjustmentTrigger = AdjustmentTrigger.DEGRADATION_DETECTED,
        threshold_value: float = 0.0,
    ) -> AdjustmentRule:
        rule = AdjustmentRule(
            rule_name=rule_name,
            adjustment_type=adjustment_type,
            adjustment_trigger=adjustment_trigger,
            threshold_value=threshold_value,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "reliability_automation_engine.rule_added",
            rule_name=rule_name,
            adjustment_type=adjustment_type.value,
        )
        return rule

    # -- domain operations -----------------------------------------------

    def analyze_adjustment_effectiveness(self, service_name: str) -> dict[str, Any]:
        """Analyze applied rate for a service and check threshold."""
        svc_records = [r for r in self._records if r.service_name == service_name]
        if not svc_records:
            return {"service_name": service_name, "status": "no_data"}
        applied_count = sum(
            1 for r in svc_records if r.adjustment_outcome == AdjustmentOutcome.APPLIED
        )
        applied_rate = round((applied_count / len(svc_records)) * 100, 2)
        avg_impact = round(sum(r.impact_score for r in svc_records) / len(svc_records), 2)
        meets_threshold = avg_impact >= self._min_impact_score
        return {
            "service_name": service_name,
            "applied_rate": applied_rate,
            "record_count": len(svc_records),
            "avg_impact_score": avg_impact,
            "meets_threshold": meets_threshold,
            "min_impact_score": self._min_impact_score,
        }

    def identify_rejected_adjustments(self) -> list[dict[str, Any]]:
        """Find services with more than one REJECTED or ROLLED_BACK adjustment."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.adjustment_outcome in (
                AdjustmentOutcome.REJECTED,
                AdjustmentOutcome.ROLLED_BACK,
            ):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "rejected_count": count})
        results.sort(key=lambda x: x["rejected_count"], reverse=True)
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        """Rank services by average impact score descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_name, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_impact_score": avg,
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_adjustment_conflicts(self) -> list[dict[str, Any]]:
        """Detect services with more than 3 adjustment records."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ReliabilityAutomatorReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_type[r.adjustment_type.value] = by_type.get(r.adjustment_type.value, 0) + 1
            by_outcome[r.adjustment_outcome.value] = (
                by_outcome.get(r.adjustment_outcome.value, 0) + 1
            )
        applied_count = sum(
            1 for r in self._records if r.adjustment_outcome == AdjustmentOutcome.APPLIED
        )
        applied_rate = (
            round((applied_count / len(self._records)) * 100, 2) if self._records else 0.0
        )
        rejection_count = sum(
            1 for r in self._records if r.adjustment_outcome == AdjustmentOutcome.REJECTED
        )
        recs: list[str] = []
        if rejection_count > 0:
            recs.append(f"{rejection_count} adjustment(s) rejected")
        rolled_back = sum(
            1 for r in self._records if r.adjustment_outcome == AdjustmentOutcome.ROLLED_BACK
        )
        if rolled_back > 0:
            recs.append(f"{rolled_back} adjustment(s) rolled back")
        if not recs:
            recs.append("Reliability automation is healthy")
        return ReliabilityAutomatorReport(
            total_adjustments=len(self._records),
            total_rules=len(self._rules),
            applied_rate_pct=applied_rate,
            by_type=by_type,
            by_outcome=by_outcome,
            rejection_count=rejection_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("reliability_automation_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.adjustment_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_adjustments": len(self._records),
            "total_rules": len(self._rules),
            "min_impact_score": self._min_impact_score,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
