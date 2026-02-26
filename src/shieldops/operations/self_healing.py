"""Self-Healing Orchestrator — track automated self-healing executions and outcomes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealingAction(StrEnum):
    RESTART_SERVICE = "restart_service"
    SCALE_OUT = "scale_out"
    CLEAR_CACHE = "clear_cache"
    ROTATE_CREDENTIALS = "rotate_credentials"
    FAILOVER = "failover"


class HealingOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ROLLBACK = "rollback"
    TIMEOUT = "timeout"


class HealingTrigger(StrEnum):
    ALERT = "alert"
    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    SCHEDULE = "schedule"
    MANUAL = "manual"


# --- Models ---


class HealingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    action: HealingAction = HealingAction.RESTART_SERVICE
    outcome: HealingOutcome = HealingOutcome.SUCCESS
    trigger: HealingTrigger = HealingTrigger.ALERT
    duration_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class HealingPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    action: HealingAction = HealingAction.RESTART_SERVICE
    trigger: HealingTrigger = HealingTrigger.ALERT
    max_retries: int = 3
    cooldown_seconds: float = 300.0
    created_at: float = Field(default_factory=time.time)


class SelfHealingReport(BaseModel):
    total_healings: int = 0
    total_policies: int = 0
    success_rate_pct: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    repeat_failure_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SelfHealingOrchestrator:
    """Track automated self-healing executions and outcomes."""

    def __init__(
        self,
        max_records: int = 200000,
        min_success_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_success_rate_pct = min_success_rate_pct
        self._records: list[HealingRecord] = []
        self._policies: list[HealingPolicy] = []
        logger.info(
            "self_healing.initialized",
            max_records=max_records,
            min_success_rate_pct=min_success_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_healing(
        self,
        service_name: str,
        action: HealingAction = HealingAction.RESTART_SERVICE,
        outcome: HealingOutcome = HealingOutcome.SUCCESS,
        trigger: HealingTrigger = HealingTrigger.ALERT,
        duration_seconds: float = 0.0,
        details: str = "",
    ) -> HealingRecord:
        record = HealingRecord(
            service_name=service_name,
            action=action,
            outcome=outcome,
            trigger=trigger,
            duration_seconds=duration_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "self_healing.healing_recorded",
            record_id=record.id,
            service_name=service_name,
            action=action.value,
            outcome=outcome.value,
        )
        return record

    def get_healing(self, record_id: str) -> HealingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_healings(
        self,
        service_name: str | None = None,
        action: HealingAction | None = None,
        limit: int = 50,
    ) -> list[HealingRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if action is not None:
            results = [r for r in results if r.action == action]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        action: HealingAction = HealingAction.RESTART_SERVICE,
        trigger: HealingTrigger = HealingTrigger.ALERT,
        max_retries: int = 3,
        cooldown_seconds: float = 300.0,
    ) -> HealingPolicy:
        policy = HealingPolicy(
            policy_name=policy_name,
            action=action,
            trigger=trigger,
            max_retries=max_retries,
            cooldown_seconds=cooldown_seconds,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "self_healing.policy_added",
            policy_name=policy_name,
            action=action.value,
            trigger=trigger.value,
        )
        return policy

    # -- domain operations -----------------------------------------------

    def analyze_healing_effectiveness(self, service_name: str) -> dict[str, Any]:
        """Analyze effectiveness for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        successes = sum(1 for r in records if r.outcome == HealingOutcome.SUCCESS)
        success_rate = round(successes / len(records) * 100, 2)
        avg_duration = round(sum(r.duration_seconds for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total_healings": len(records),
            "success_count": successes,
            "success_rate_pct": success_rate,
            "avg_duration_seconds": avg_duration,
            "meets_threshold": success_rate >= self._min_success_rate_pct,
        }

    def identify_repeat_failures(self) -> list[dict[str, Any]]:
        """Find services with repeated healing failures."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.outcome in (
                HealingOutcome.FAILED,
                HealingOutcome.ROLLBACK,
                HealingOutcome.TIMEOUT,
            ):
                failure_counts[r.service_name] = failure_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "failure_count": count,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_healing_frequency(self) -> list[dict[str, Any]]:
        """Rank services by healing event count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.service_name] = freq.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in freq.items():
            results.append(
                {
                    "service_name": svc,
                    "healing_count": count,
                }
            )
        results.sort(key=lambda x: x["healing_count"], reverse=True)
        return results

    def detect_healing_loops(self) -> list[dict[str, Any]]:
        """Detect services caught in healing loops (>3 non-success)."""
        svc_non_success: dict[str, int] = {}
        for r in self._records:
            if r.outcome != HealingOutcome.SUCCESS:
                svc_non_success[r.service_name] = svc_non_success.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non_success.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_success_count": count,
                        "loop_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_success_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SelfHealingReport:
        by_action: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_action[r.action.value] = by_action.get(r.action.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        success_count = sum(1 for r in self._records if r.outcome == HealingOutcome.SUCCESS)
        success_rate = round(success_count / len(self._records) * 100, 2) if self._records else 0.0
        repeat_failures = sum(1 for d in self.identify_repeat_failures())
        recs: list[str] = []
        if success_rate < self._min_success_rate_pct:
            recs.append(
                f"Success rate {success_rate}% is below {self._min_success_rate_pct}% threshold"
            )
        if repeat_failures > 0:
            recs.append(f"{repeat_failures} service(s) with repeat failures")
        loops = len(self.detect_healing_loops())
        if loops > 0:
            recs.append(f"{loops} service(s) detected in healing loops")
        if not recs:
            recs.append("Self-healing effectiveness meets targets")
        return SelfHealingReport(
            total_healings=len(self._records),
            total_policies=len(self._policies),
            success_rate_pct=success_rate,
            by_action=by_action,
            by_outcome=by_outcome,
            repeat_failure_count=repeat_failures,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("self_healing.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_healings": len(self._records),
            "total_policies": len(self._policies),
            "min_success_rate_pct": self._min_success_rate_pct,
            "action_distribution": action_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
