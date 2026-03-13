"""Risk Response Automator
select response actions, compute response
effectiveness, detect response delays."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResponseAction(StrEnum):
    BLOCK = "block"
    ISOLATE = "isolate"
    ALERT = "alert"
    INVESTIGATE = "investigate"


class AutomationLevel(StrEnum):
    FULLY_AUTOMATED = "fully_automated"
    SEMI_AUTOMATED = "semi_automated"
    MANUAL = "manual"
    DISABLED = "disabled"


class ResponseOutcome(StrEnum):
    CONTAINED = "contained"
    MITIGATED = "mitigated"
    ESCALATED = "escalated"
    FAILED = "failed"


# --- Models ---


class RiskResponseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    response_id: str = ""
    action: ResponseAction = ResponseAction.ALERT
    automation: AutomationLevel = AutomationLevel.SEMI_AUTOMATED
    outcome: ResponseOutcome = ResponseOutcome.MITIGATED
    entity_id: str = ""
    risk_score: float = 0.0
    response_time_sec: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskResponseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    response_id: str = ""
    action: ResponseAction = ResponseAction.ALERT
    effectiveness_score: float = 0.0
    is_delayed: bool = False
    automation_match: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskResponseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_response_time: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_automation: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    delayed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskResponseAutomator:
    """Select response actions, compute effectiveness,
    detect response delays."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RiskResponseRecord] = []
        self._analyses: dict[str, RiskResponseAnalysis] = {}
        logger.info(
            "risk_response_automator.init",
            max_records=max_records,
        )

    def add_record(
        self,
        response_id: str = "",
        action: ResponseAction = ResponseAction.ALERT,
        automation: AutomationLevel = (AutomationLevel.SEMI_AUTOMATED),
        outcome: ResponseOutcome = (ResponseOutcome.MITIGATED),
        entity_id: str = "",
        risk_score: float = 0.0,
        response_time_sec: float = 0.0,
        description: str = "",
    ) -> RiskResponseRecord:
        record = RiskResponseRecord(
            response_id=response_id,
            action=action,
            automation=automation,
            outcome=outcome,
            entity_id=entity_id,
            risk_score=risk_score,
            response_time_sec=response_time_sec,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_response_automator.record_added",
            record_id=record.id,
            response_id=response_id,
        )
        return record

    def process(self, key: str) -> RiskResponseAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        outcome_scores = {
            "contained": 1.0,
            "mitigated": 0.8,
            "escalated": 0.4,
            "failed": 0.0,
        }
        eff = outcome_scores.get(rec.outcome.value, 0.5)
        is_delayed = rec.response_time_sec > 300.0
        analysis = RiskResponseAnalysis(
            response_id=rec.response_id,
            action=rec.action,
            effectiveness_score=round(eff, 2),
            is_delayed=is_delayed,
            automation_match=rec.automation != AutomationLevel.DISABLED,
            description=(f"Response {rec.response_id} effectiveness={eff}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RiskResponseReport:
        by_a: dict[str, int] = {}
        by_au: dict[str, int] = {}
        by_o: dict[str, int] = {}
        times: list[float] = []
        delayed = 0
        for r in self._records:
            k = r.action.value
            by_a[k] = by_a.get(k, 0) + 1
            k2 = r.automation.value
            by_au[k2] = by_au.get(k2, 0) + 1
            k3 = r.outcome.value
            by_o[k3] = by_o.get(k3, 0) + 1
            times.append(r.response_time_sec)
            if r.response_time_sec > 300.0:
                delayed += 1
        avg_time = round(sum(times) / len(times), 2) if times else 0.0
        recs: list[str] = []
        failed = by_o.get("failed", 0)
        if failed > 0:
            recs.append(f"{failed} failed responses")
        if delayed > 0:
            recs.append(f"{delayed} delayed responses")
        if not recs:
            recs.append("Response automation healthy")
        return RiskResponseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_response_time=avg_time,
            by_action=by_a,
            by_automation=by_au,
            by_outcome=by_o,
            delayed_count=delayed,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            k = r.action.value
            action_dist[k] = action_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "action_distribution": action_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_response_automator.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def select_response_action(
        self,
    ) -> list[dict[str, Any]]:
        """Select optimal action per entity."""
        entity_data: dict[str, list[RiskResponseRecord]] = {}
        for r in self._records:
            entity_data.setdefault(r.entity_id, []).append(r)
        results: list[dict[str, Any]] = []
        for eid, recs in entity_data.items():
            max_risk = max(r.risk_score for r in recs)
            if max_risk >= 90:
                recommended = "block"
            elif max_risk >= 70:
                recommended = "isolate"
            elif max_risk >= 40:
                recommended = "alert"
            else:
                recommended = "investigate"
            results.append(
                {
                    "entity_id": eid,
                    "max_risk_score": max_risk,
                    "recommended_action": recommended,
                    "event_count": len(recs),
                }
            )
        results.sort(
            key=lambda x: x["max_risk_score"],
            reverse=True,
        )
        return results

    def compute_response_effectiveness(
        self,
    ) -> dict[str, Any]:
        """Compute response effectiveness."""
        if not self._records:
            return {
                "overall_effectiveness": 0.0,
                "by_action": {},
            }
        outcome_scores = {
            "contained": 1.0,
            "mitigated": 0.8,
            "escalated": 0.4,
            "failed": 0.0,
        }
        action_eff: dict[str, list[float]] = {}
        for r in self._records:
            k = r.action.value
            s = outcome_scores.get(r.outcome.value, 0.5)
            action_eff.setdefault(k, []).append(s)
        by_action: dict[str, float] = {}
        all_scores: list[float] = []
        for act, scores in action_eff.items():
            avg = round(sum(scores) / len(scores), 2)
            by_action[act] = avg
            all_scores.extend(scores)
        overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
        return {
            "overall_effectiveness": overall,
            "by_action": by_action,
        }

    def detect_response_delays(
        self,
    ) -> list[dict[str, Any]]:
        """Find delayed responses."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.response_time_sec > 300.0:
                results.append(
                    {
                        "response_id": (r.response_id),
                        "entity_id": r.entity_id,
                        "response_time_sec": (r.response_time_sec),
                        "action": r.action.value,
                        "delay_sec": round(
                            r.response_time_sec - 300.0,
                            2,
                        ),
                    }
                )
        results.sort(
            key=lambda x: x["response_time_sec"],
            reverse=True,
        )
        return results
