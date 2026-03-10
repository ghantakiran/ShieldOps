"""ObservabilityAutomationEngine — automation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationTrigger(StrEnum):
    THRESHOLD_BREACH = "threshold_breach"
    ANOMALY_DETECTED = "anomaly_detected"
    SLO_VIOLATION = "slo_violation"
    SCHEDULE = "schedule"


class ActionType(StrEnum):
    ALERT_CREATE = "alert_create"
    DASHBOARD_UPDATE = "dashboard_update"
    RULE_MODIFY = "rule_modify"
    ESCALATE = "escalate"


class AutomationOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Models ---


class AutomationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    trigger: AutomationTrigger = AutomationTrigger.THRESHOLD_BREACH
    action_type: ActionType = ActionType.ALERT_CREATE
    outcome: AutomationOutcome = AutomationOutcome.SUCCESS
    score: float = 0.0
    execution_time_ms: float = 0.0
    effectiveness: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    trigger: AutomationTrigger = AutomationTrigger.THRESHOLD_BREACH
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    success_rate: float = 0.0
    by_trigger: dict[str, int] = Field(default_factory=dict)
    by_action_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityAutomationEngine:
    """Observability Automation Engine.

    Automates observability responses including
    alert creation, dashboard updates, and
    rule modifications based on triggers.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AutomationRecord] = []
        self._analyses: list[AutomationAnalysis] = []
        logger.info(
            "obs_automation_engine.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        trigger: AutomationTrigger = (AutomationTrigger.THRESHOLD_BREACH),
        action_type: ActionType = (ActionType.ALERT_CREATE),
        outcome: AutomationOutcome = (AutomationOutcome.SUCCESS),
        score: float = 0.0,
        execution_time_ms: float = 0.0,
        effectiveness: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AutomationRecord:
        record = AutomationRecord(
            name=name,
            trigger=trigger,
            action_type=action_type,
            outcome=outcome,
            score=score,
            execution_time_ms=execution_time_ms,
            effectiveness=effectiveness,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "obs_automation_engine.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        success = sum(1 for r in matching if r.outcome == AutomationOutcome.SUCCESS)
        rate = round(success / len(matching) * 100, 1)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "success_rate": rate,
        }

    def generate_report(self) -> AutomationReport:
        by_tr: dict[str, int] = {}
        by_at: dict[str, int] = {}
        by_oc: dict[str, int] = {}
        for r in self._records:
            v1 = r.trigger.value
            by_tr[v1] = by_tr.get(v1, 0) + 1
            v2 = r.action_type.value
            by_at[v2] = by_at.get(v2, 0) + 1
            v3 = r.outcome.value
            by_oc[v3] = by_oc.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        total = len(self._records)
        success_cnt = by_oc.get("success", 0)
        success_rate = round(success_cnt / total * 100, 1) if total > 0 else 0.0
        recs: list[str] = []
        failed = by_oc.get("failed", 0)
        if failed > 0:
            recs.append(f"{failed} automation(s) failed")
        if success_rate < 90.0 and total > 0:
            recs.append(f"Success rate {success_rate}% below 90% target")
        if not recs:
            recs.append("Automation engine healthy")
        return AutomationReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            success_rate=success_rate,
            by_trigger=by_tr,
            by_action_type=by_at,
            by_outcome=by_oc,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        tr_dist: dict[str, int] = {}
        for r in self._records:
            k = r.trigger.value
            tr_dist[k] = tr_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "trigger_distribution": tr_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("obs_automation_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_trigger_conditions(
        self,
    ) -> dict[str, Any]:
        """Evaluate trigger condition distribution."""
        if not self._records:
            return {"status": "no_data"}
        trigger_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            tv = r.trigger.value
            if tv not in trigger_data:
                trigger_data[tv] = {
                    "count": 0,
                    "success": 0,
                    "total_time": 0.0,
                }
            trigger_data[tv]["count"] += 1
            if r.outcome == AutomationOutcome.SUCCESS:
                trigger_data[tv]["success"] += 1
            trigger_data[tv]["total_time"] += r.execution_time_ms
        result: dict[str, Any] = {}
        for tv, data in trigger_data.items():
            cnt = data["count"]
            result[tv] = {
                "count": cnt,
                "success_rate": round(data["success"] / cnt * 100, 1),
                "avg_exec_time_ms": round(data["total_time"] / cnt, 2),
            }
        return result

    def execute_automated_response(
        self,
        trigger: AutomationTrigger,
        action: ActionType,
        service: str = "",
    ) -> dict[str, Any]:
        """Execute an automated response."""
        matching = [r for r in self._records if r.trigger == trigger and r.action_type == action]
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "status": "no_matching_rules",
                "trigger": trigger.value,
                "action": action.value,
            }
        success = sum(1 for r in matching if r.outcome == AutomationOutcome.SUCCESS)
        rate = round(success / len(matching) * 100, 1)
        return {
            "trigger": trigger.value,
            "action": action.value,
            "historical_success_rate": rate,
            "sample_size": len(matching),
            "recommended": rate >= 80.0,
        }

    def measure_automation_effectiveness(
        self,
    ) -> dict[str, Any]:
        """Measure automation effectiveness."""
        if not self._records:
            return {"status": "no_data"}
        action_eff: dict[str, dict[str, float]] = {}
        for r in self._records:
            av = r.action_type.value
            if av not in action_eff:
                action_eff[av] = {
                    "total_eff": 0.0,
                    "total_time": 0.0,
                    "count": 0,
                }
            action_eff[av]["total_eff"] += r.effectiveness
            action_eff[av]["total_time"] += r.execution_time_ms
            action_eff[av]["count"] += 1
        result: dict[str, Any] = {}
        for av, data in action_eff.items():
            cnt = data["count"]
            avg_eff = round(data["total_eff"] / cnt, 4)
            avg_time = round(data["total_time"] / cnt, 2)
            result[av] = {
                "avg_effectiveness": avg_eff,
                "avg_exec_time_ms": avg_time,
                "count": int(cnt),
                "needs_improvement": avg_eff < 0.7,
            }
        overall_eff = round(
            sum(r.effectiveness for r in self._records) / len(self._records),
            4,
        )
        return {
            "overall_effectiveness": overall_eff,
            "by_action_type": result,
        }
