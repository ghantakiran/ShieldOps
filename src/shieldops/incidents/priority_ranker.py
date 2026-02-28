"""Incident Priority Ranker — rank and calibrate incident priorities for accurate triage."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PriorityLevel(StrEnum):
    P0_CRITICAL = "p0_critical"
    P1_HIGH = "p1_high"
    P2_MEDIUM = "p2_medium"
    P3_LOW = "p3_low"
    P4_INFORMATIONAL = "p4_informational"


class PriorityFactor(StrEnum):
    USER_IMPACT = "user_impact"
    REVENUE_LOSS = "revenue_loss"
    SLA_RISK = "sla_risk"
    SECURITY_EXPOSURE = "security_exposure"
    DATA_INTEGRITY = "data_integrity"


class RankingMethod(StrEnum):
    WEIGHTED_SCORE = "weighted_score"
    MACHINE_LEARNING = "machine_learning"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    MANUAL = "manual"


# --- Models ---


class PriorityRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    incident_id: str = ""
    incident_title: str = ""
    assigned_priority: PriorityLevel = PriorityLevel.P2_MEDIUM
    computed_priority: PriorityLevel = PriorityLevel.P2_MEDIUM
    ranking_method: RankingMethod = RankingMethod.WEIGHTED_SCORE
    priority_score: float = 0.0
    factors_used: list[str] = Field(default_factory=list)
    is_misranked: bool = False
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PriorityFactorDetail(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    factor_name: str = ""
    factor_type: PriorityFactor = PriorityFactor.USER_IMPACT
    weight: float = 1.0
    description: str = ""
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)


class PriorityRankerReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_factors: int = 0
    misranked_count: int = 0
    accuracy_pct: float = 0.0
    by_assigned_priority: dict[str, int] = Field(default_factory=dict)
    by_computed_priority: dict[str, int] = Field(default_factory=dict)
    by_ranking_method: dict[str, int] = Field(default_factory=dict)
    priority_drift_detected: bool = False
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentPriorityRanker:
    """Rank and calibrate incident priorities to ensure accurate, consistent triage."""

    def __init__(
        self,
        max_records: int = 200000,
        min_accuracy_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_accuracy_pct = min_accuracy_pct
        self._records: list[PriorityRecord] = []
        self._factors: list[PriorityFactorDetail] = []
        logger.info(
            "priority_ranker.initialized",
            max_records=max_records,
            min_accuracy_pct=min_accuracy_pct,
        )

    # -- CRUD --

    def record_priority(
        self,
        incident_id: str,
        incident_title: str = "",
        assigned_priority: PriorityLevel = PriorityLevel.P2_MEDIUM,
        computed_priority: PriorityLevel = PriorityLevel.P2_MEDIUM,
        ranking_method: RankingMethod = RankingMethod.WEIGHTED_SCORE,
        priority_score: float = 0.0,
        factors_used: list[str] | None = None,
        is_misranked: bool = False,
        details: str = "",
    ) -> PriorityRecord:
        record = PriorityRecord(
            incident_id=incident_id,
            incident_title=incident_title,
            assigned_priority=assigned_priority,
            computed_priority=computed_priority,
            ranking_method=ranking_method,
            priority_score=priority_score,
            factors_used=factors_used or [],
            is_misranked=is_misranked,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "priority_ranker.recorded",
            record_id=record.id,
            incident_id=incident_id,
            assigned_priority=assigned_priority.value,
            computed_priority=computed_priority.value,
        )
        return record

    def get_priority(self, record_id: str) -> PriorityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_priorities(
        self,
        assigned_priority: PriorityLevel | None = None,
        ranking_method: RankingMethod | None = None,
        limit: int = 50,
    ) -> list[PriorityRecord]:
        results = list(self._records)
        if assigned_priority is not None:
            results = [r for r in results if r.assigned_priority == assigned_priority]
        if ranking_method is not None:
            results = [r for r in results if r.ranking_method == ranking_method]
        return results[-limit:]

    def add_factor(
        self,
        factor_name: str,
        factor_type: PriorityFactor = PriorityFactor.USER_IMPACT,
        weight: float = 1.0,
        description: str = "",
        enabled: bool = True,
    ) -> PriorityFactorDetail:
        factor = PriorityFactorDetail(
            factor_name=factor_name,
            factor_type=factor_type,
            weight=weight,
            description=description,
            enabled=enabled,
        )
        self._factors.append(factor)
        if len(self._factors) > self._max_records:
            self._factors = self._factors[-self._max_records :]
        logger.info(
            "priority_ranker.factor_added",
            factor_id=factor.id,
            factor_name=factor_name,
            factor_type=factor_type.value,
        )
        return factor

    # -- Domain operations --

    def analyze_priority_distribution(self) -> dict[str, Any]:
        """Analyze how incidents are distributed across priority levels."""
        if not self._records:
            return {"total": 0, "by_assigned": {}, "by_computed": {}}
        by_assigned: dict[str, int] = {}
        by_computed: dict[str, int] = {}
        for r in self._records:
            by_assigned[r.assigned_priority.value] = (
                by_assigned.get(r.assigned_priority.value, 0) + 1
            )
            by_computed[r.computed_priority.value] = (
                by_computed.get(r.computed_priority.value, 0) + 1
            )
        total = len(self._records)
        p0_count = by_assigned.get(PriorityLevel.P0_CRITICAL.value, 0)
        p0_ratio = round(p0_count / total * 100, 2) if total else 0.0
        return {
            "total": total,
            "by_assigned": by_assigned,
            "by_computed": by_computed,
            "p0_ratio_pct": p0_ratio,
            "p0_count": p0_count,
        }

    def identify_misranked_incidents(self) -> list[dict[str, Any]]:
        """Return incidents where assigned priority differs from computed priority."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.assigned_priority != r.computed_priority or r.is_misranked:
                results.append(
                    {
                        "id": r.id,
                        "incident_id": r.incident_id,
                        "incident_title": r.incident_title,
                        "assigned_priority": r.assigned_priority.value,
                        "computed_priority": r.computed_priority.value,
                        "priority_score": r.priority_score,
                        "is_misranked": r.is_misranked,
                    }
                )
        results.sort(key=lambda x: x["priority_score"], reverse=True)
        return results

    def rank_by_priority_score(self) -> list[dict[str, Any]]:
        """Rank all incidents by their computed priority score (highest first)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "id": r.id,
                    "incident_id": r.incident_id,
                    "incident_title": r.incident_title,
                    "assigned_priority": r.assigned_priority.value,
                    "computed_priority": r.computed_priority.value,
                    "priority_score": r.priority_score,
                    "ranking_method": r.ranking_method.value,
                }
            )
        results.sort(key=lambda x: x["priority_score"], reverse=True)
        return results

    def detect_priority_drift(self) -> dict[str, Any]:
        """Detect whether priority accuracy is drifting over time."""
        if len(self._records) < 4:
            return {"drift_detected": False, "reason": "insufficient_data"}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _accuracy(records: list[PriorityRecord]) -> float:
            if not records:
                return 100.0
            correct = sum(
                1
                for r in records
                if r.assigned_priority == r.computed_priority and not r.is_misranked
            )
            return round(correct / len(records) * 100, 2)

        first_acc = _accuracy(first_half)
        second_acc = _accuracy(second_half)
        delta = round(second_acc - first_acc, 2)
        drift_detected = abs(delta) > 10.0
        logger.info(
            "priority_ranker.drift_detected",
            drift_detected=drift_detected,
            first_acc=first_acc,
            second_acc=second_acc,
        )
        return {
            "drift_detected": drift_detected,
            "first_half_accuracy_pct": first_acc,
            "second_half_accuracy_pct": second_acc,
            "delta_pct": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> PriorityRankerReport:
        by_assigned: dict[str, int] = {}
        by_computed: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_assigned[r.assigned_priority.value] = (
                by_assigned.get(r.assigned_priority.value, 0) + 1
            )
            by_computed[r.computed_priority.value] = (
                by_computed.get(r.computed_priority.value, 0) + 1
            )
            by_method[r.ranking_method.value] = by_method.get(r.ranking_method.value, 0) + 1
        total = len(self._records)
        misranked = sum(
            1 for r in self._records if r.is_misranked or r.assigned_priority != r.computed_priority
        )
        accuracy = round((total - misranked) / total * 100, 2) if total else 100.0
        drift_info = self.detect_priority_drift()
        drift_detected = drift_info.get("drift_detected", False)
        recs: list[str] = []
        if accuracy < self._min_accuracy_pct:
            recs.append(
                f"Priority accuracy {accuracy}% below target {self._min_accuracy_pct}%"
                " — review ranking model"
            )
        if misranked > 0:
            recs.append(f"{misranked} misranked incident(s) detected — review assignments")
        if drift_detected:
            recs.append("Priority drift detected — recalibrate ranking thresholds")
        if not recs:
            recs.append("Priority ranking is performing within targets")
        return PriorityRankerReport(
            total_records=total,
            total_factors=len(self._factors),
            misranked_count=misranked,
            accuracy_pct=accuracy,
            by_assigned_priority=by_assigned,
            by_computed_priority=by_computed,
            by_ranking_method=by_method,
            priority_drift_detected=bool(drift_detected),
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._factors.clear()
        logger.info("priority_ranker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            method_dist[r.ranking_method.value] = method_dist.get(r.ranking_method.value, 0) + 1
        total = len(self._records)
        misranked = sum(1 for r in self._records if r.is_misranked)
        accuracy = round((total - misranked) / total * 100, 2) if total else 100.0
        return {
            "total_records": total,
            "total_factors": len(self._factors),
            "misranked_count": misranked,
            "accuracy_pct": accuracy,
            "min_accuracy_pct": self._min_accuracy_pct,
            "method_distribution": method_dist,
        }
