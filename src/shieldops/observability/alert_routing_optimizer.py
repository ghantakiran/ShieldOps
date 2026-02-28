"""Alert Routing Optimizer — optimize alert routing to reduce noise."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RoutingStrategy(StrEnum):
    ROUND_ROBIN = "round_robin"
    SKILL_BASED = "skill_based"
    LOAD_BALANCED = "load_balanced"
    ESCALATION_CHAIN = "escalation_chain"
    GEOGRAPHIC = "geographic"


class RoutingOutcome(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    SUPPRESSED = "suppressed"
    MISROUTED = "misrouted"
    IGNORED = "ignored"


class AlertPriority(StrEnum):
    PAGE = "page"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class RoutingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    outcome: RoutingOutcome = RoutingOutcome.ACKNOWLEDGED
    priority: AlertPriority = AlertPriority.MEDIUM
    response_time_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RoutingPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    priority: AlertPriority = AlertPriority.MEDIUM
    max_response_seconds: float = 300.0
    auto_escalate: bool = True
    created_at: float = Field(default_factory=time.time)


class AlertRoutingReport(BaseModel):
    total_routings: int = 0
    total_policies: int = 0
    ack_rate_pct: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    misrouted_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertRoutingOptimizer:
    """Optimize alert routing to reduce noise."""

    def __init__(
        self,
        max_records: int = 200000,
        max_response_seconds: float = 300.0,
    ) -> None:
        self._max_records = max_records
        self._max_response_seconds = max_response_seconds
        self._records: list[RoutingRecord] = []
        self._policies: list[RoutingPolicy] = []
        logger.info(
            "alert_routing_optimizer.initialized",
            max_records=max_records,
            max_response_seconds=max_response_seconds,
        )

    # -- record / get / list ----------------------------------------

    def record_routing(
        self,
        alert_name: str,
        strategy: RoutingStrategy = (RoutingStrategy.SKILL_BASED),
        outcome: RoutingOutcome = (RoutingOutcome.ACKNOWLEDGED),
        priority: AlertPriority = AlertPriority.MEDIUM,
        response_time_seconds: float = 0.0,
        details: str = "",
    ) -> RoutingRecord:
        record = RoutingRecord(
            alert_name=alert_name,
            strategy=strategy,
            outcome=outcome,
            priority=priority,
            response_time_seconds=response_time_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_routing_optimizer.routing_recorded",
            record_id=record.id,
            alert_name=alert_name,
            strategy=strategy.value,
            outcome=outcome.value,
        )
        return record

    def get_routing(self, record_id: str) -> RoutingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_routings(
        self,
        alert_name: str | None = None,
        strategy: RoutingStrategy | None = None,
        limit: int = 50,
    ) -> list[RoutingRecord]:
        results = list(self._records)
        if alert_name is not None:
            results = [r for r in results if r.alert_name == alert_name]
        if strategy is not None:
            results = [r for r in results if r.strategy == strategy]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        strategy: RoutingStrategy = (RoutingStrategy.SKILL_BASED),
        priority: AlertPriority = AlertPriority.MEDIUM,
        max_response_seconds: float = 300.0,
        auto_escalate: bool = True,
    ) -> RoutingPolicy:
        policy = RoutingPolicy(
            policy_name=policy_name,
            strategy=strategy,
            priority=priority,
            max_response_seconds=max_response_seconds,
            auto_escalate=auto_escalate,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "alert_routing_optimizer.policy_added",
            policy_name=policy_name,
            strategy=strategy.value,
            priority=priority.value,
        )
        return policy

    # -- domain operations ------------------------------------------

    def analyze_routing_effectiveness(self, alert_name: str) -> dict[str, Any]:
        """Analyze routing effectiveness for an alert."""
        records = [r for r in self._records if r.alert_name == alert_name]
        if not records:
            return {
                "alert_name": alert_name,
                "status": "no_data",
            }
        ack_count = sum(1 for r in records if r.outcome == RoutingOutcome.ACKNOWLEDGED)
        ack_rate = round(ack_count / len(records) * 100, 2)
        avg_response = round(
            sum(r.response_time_seconds for r in records) / len(records),
            2,
        )
        return {
            "alert_name": alert_name,
            "routing_count": len(records),
            "ack_count": ack_count,
            "ack_rate": ack_rate,
            "avg_response": avg_response,
            "meets_threshold": (avg_response <= self._max_response_seconds),
        }

    def identify_misrouted_alerts(
        self,
    ) -> list[dict[str, Any]]:
        """Find alerts with repeated misrouting."""
        misroute_counts: dict[str, int] = {}
        for r in self._records:
            if r.outcome in (
                RoutingOutcome.MISROUTED,
                RoutingOutcome.IGNORED,
            ):
                misroute_counts[r.alert_name] = misroute_counts.get(r.alert_name, 0) + 1
        results: list[dict[str, Any]] = []
        for alert, count in misroute_counts.items():
            if count > 1:
                results.append(
                    {
                        "alert_name": alert,
                        "misrouted_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["misrouted_count"],
            reverse=True,
        )
        return results

    def rank_by_response_time(
        self,
    ) -> list[dict[str, Any]]:
        """Rank alerts by avg response time descending."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.alert_name] = totals.get(r.alert_name, 0.0) + r.response_time_seconds
            counts[r.alert_name] = counts.get(r.alert_name, 0) + 1
        results: list[dict[str, Any]] = []
        for alert in totals:
            avg = round(totals[alert] / counts[alert], 2)
            results.append(
                {
                    "alert_name": alert,
                    "avg_response_time": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_response_time"],
            reverse=True,
        )
        return results

    def detect_routing_issues(
        self,
    ) -> list[dict[str, Any]]:
        """Detect alerts with >3 non-ACKNOWLEDGED."""
        non_ack: dict[str, int] = {}
        for r in self._records:
            if r.outcome != RoutingOutcome.ACKNOWLEDGED:
                non_ack[r.alert_name] = non_ack.get(r.alert_name, 0) + 1
        results: list[dict[str, Any]] = []
        for alert, count in non_ack.items():
            if count > 3:
                results.append(
                    {
                        "alert_name": alert,
                        "non_ack_count": count,
                        "issue_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_ack_count"],
            reverse=True,
        )
        return results

    # -- report / stats ---------------------------------------------

    def generate_report(self) -> AlertRoutingReport:
        by_strategy: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.strategy.value] = by_strategy.get(r.strategy.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        ack_count = sum(1 for r in self._records if r.outcome == RoutingOutcome.ACKNOWLEDGED)
        ack_rate = (
            round(
                ack_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        misrouted = sum(1 for d in self.identify_misrouted_alerts())
        recs: list[str] = []
        if self._records and ack_rate < 80.0:
            recs.append(f"Ack rate {ack_rate}% is below 80.0% threshold")
        if misrouted > 0:
            recs.append(f"{misrouted} alert(s) with repeated misrouting")
        issues = len(self.detect_routing_issues())
        if issues > 0:
            recs.append(f"{issues} alert(s) detected with routing issues")
        if not recs:
            recs.append("Alert routing is healthy and optimized")
        return AlertRoutingReport(
            total_routings=len(self._records),
            total_policies=len(self._policies),
            ack_rate_pct=ack_rate,
            by_strategy=by_strategy,
            by_outcome=by_outcome,
            misrouted_count=misrouted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("alert_routing_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_routings": len(self._records),
            "total_policies": len(self._policies),
            "max_response_seconds": (self._max_response_seconds),
            "strategy_distribution": strategy_dist,
            "unique_alerts": len({r.alert_name for r in self._records}),
        }
