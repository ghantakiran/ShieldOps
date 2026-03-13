"""Alert Suppression Intelligence
learn suppression windows, evaluate suppression safety,
auto tune suppression rules."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SuppressionReason(StrEnum):
    MAINTENANCE = "maintenance"
    DEPLOYMENT = "deployment"
    KNOWN_ISSUE = "known_issue"
    RECURRING = "recurring"


class SafetyLevel(StrEnum):
    SAFE = "safe"
    CAUTION = "caution"
    RISKY = "risky"
    UNSAFE = "unsafe"


class WindowType(StrEnum):
    SCHEDULED = "scheduled"
    LEARNED = "learned"
    MANUAL = "manual"
    EMERGENCY = "emergency"


# --- Models ---


class AlertSuppressionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    suppression_reason: SuppressionReason = SuppressionReason.MAINTENANCE
    safety_level: SafetyLevel = SafetyLevel.SAFE
    window_type: WindowType = WindowType.SCHEDULED
    duration_min: float = 0.0
    alerts_suppressed: int = 0
    missed_incidents: int = 0
    source: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertSuppressionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    safety_level: SafetyLevel = SafetyLevel.SAFE
    suppression_score: float = 0.0
    total_suppressed: int = 0
    missed_incident_rate: float = 0.0
    avg_duration_min: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertSuppressionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_suppression_score: float = 0.0
    by_suppression_reason: dict[str, int] = Field(default_factory=dict)
    by_safety_level: dict[str, int] = Field(default_factory=dict)
    by_window_type: dict[str, int] = Field(default_factory=dict)
    risky_suppressions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertSuppressionIntelligence:
    """Learn suppression windows, evaluate suppression
    safety, auto tune suppression rules."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AlertSuppressionRecord] = []
        self._analyses: dict[str, AlertSuppressionAnalysis] = {}
        logger.info(
            "alert_suppression_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        alert_name: str = "",
        suppression_reason: SuppressionReason = (SuppressionReason.MAINTENANCE),
        safety_level: SafetyLevel = SafetyLevel.SAFE,
        window_type: WindowType = (WindowType.SCHEDULED),
        duration_min: float = 0.0,
        alerts_suppressed: int = 0,
        missed_incidents: int = 0,
        source: str = "",
    ) -> AlertSuppressionRecord:
        record = AlertSuppressionRecord(
            alert_name=alert_name,
            suppression_reason=suppression_reason,
            safety_level=safety_level,
            window_type=window_type,
            duration_min=duration_min,
            alerts_suppressed=alerts_suppressed,
            missed_incidents=missed_incidents,
            source=source,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_suppression.record_added",
            record_id=record.id,
            alert_name=alert_name,
        )
        return record

    def process(self, key: str) -> AlertSuppressionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.alert_name == rec.alert_name]
        count = len(related)
        total_sup = sum(r.alerts_suppressed for r in related)
        total_missed = sum(r.missed_incidents for r in related)
        miss_rate = total_missed / total_sup if total_sup else 0.0
        avg_dur = sum(r.duration_min for r in related) / count if count else 0.0
        score = max(
            0.0,
            100.0 - miss_rate * 100 - avg_dur * 0.1,
        )
        analysis = AlertSuppressionAnalysis(
            alert_name=rec.alert_name,
            safety_level=rec.safety_level,
            suppression_score=round(score, 2),
            total_suppressed=total_sup,
            missed_incident_rate=round(miss_rate, 2),
            avg_duration_min=round(avg_dur, 2),
            description=(f"Alert {rec.alert_name} suppression score {score:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> AlertSuppressionReport:
        by_sr: dict[str, int] = {}
        by_sl: dict[str, int] = {}
        by_wt: dict[str, int] = {}
        durations: list[float] = []
        for r in self._records:
            k = r.suppression_reason.value
            by_sr[k] = by_sr.get(k, 0) + 1
            k2 = r.safety_level.value
            by_sl[k2] = by_sl.get(k2, 0) + 1
            k3 = r.window_type.value
            by_wt[k3] = by_wt.get(k3, 0) + 1
            durations.append(r.duration_min)
        avg = round(sum(durations) / len(durations), 2) if durations else 0.0
        risky = list(
            {
                r.alert_name
                for r in self._records
                if r.safety_level
                in (
                    SafetyLevel.RISKY,
                    SafetyLevel.UNSAFE,
                )
            }
        )[:10]
        recs: list[str] = []
        if risky:
            recs.append(f"{len(risky)} risky suppressions")
        if not recs:
            recs.append("Suppression rules within norms")
        return AlertSuppressionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_suppression_score=avg,
            by_suppression_reason=by_sr,
            by_safety_level=by_sl,
            by_window_type=by_wt,
            risky_suppressions=risky,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sr_dist: dict[str, int] = {}
        for r in self._records:
            k = r.suppression_reason.value
            sr_dist[k] = sr_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "reason_distribution": sr_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("alert_suppression_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def learn_suppression_windows(
        self,
    ) -> list[dict[str, Any]]:
        """Learn optimal suppression windows."""
        alert_windows: dict[str, list[float]] = {}
        alert_reasons: dict[str, dict[str, int]] = {}
        for r in self._records:
            alert_windows.setdefault(r.alert_name, []).append(r.duration_min)
            if r.alert_name not in alert_reasons:
                alert_reasons[r.alert_name] = {}
            k = r.suppression_reason.value
            alert_reasons[r.alert_name][k] = alert_reasons[r.alert_name].get(k, 0) + 1
        results: list[dict[str, Any]] = []
        for name, durs in alert_windows.items():
            avg = sum(durs) / len(durs) if durs else 0.0
            results.append(
                {
                    "alert_name": name,
                    "avg_window_min": round(avg, 2),
                    "window_count": len(durs),
                    "reasons": alert_reasons[name],
                    "recommended_window_min": round(avg * 1.2, 2),
                }
            )
        results.sort(
            key=lambda x: x["window_count"],
            reverse=True,
        )
        return results

    def evaluate_suppression_safety(
        self,
    ) -> list[dict[str, Any]]:
        """Evaluate safety of suppressions."""
        alert_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            if r.alert_name not in alert_data:
                alert_data[r.alert_name] = {
                    "suppressed": 0,
                    "missed": 0,
                }
            alert_data[r.alert_name]["suppressed"] += r.alerts_suppressed
            alert_data[r.alert_name]["missed"] += r.missed_incidents
        results: list[dict[str, Any]] = []
        for name, data in alert_data.items():
            miss_rate = data["missed"] / data["suppressed"] if data["suppressed"] else 0.0
            safety = (
                "safe"
                if miss_rate < 0.01
                else "caution"
                if miss_rate < 0.05
                else "risky"
                if miss_rate < 0.1
                else "unsafe"
            )
            results.append(
                {
                    "alert_name": name,
                    "total_suppressed": (data["suppressed"]),
                    "missed_incidents": (data["missed"]),
                    "miss_rate": round(miss_rate, 4),
                    "safety_assessment": safety,
                }
            )
        results.sort(
            key=lambda x: x["miss_rate"],
            reverse=True,
        )
        return results

    def auto_tune_suppression_rules(
        self,
    ) -> list[dict[str, Any]]:
        """Auto tune suppression rules."""
        alert_perf: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.alert_name not in alert_perf:
                alert_perf[r.alert_name] = {
                    "durations": [],
                    "missed": 0,
                    "suppressed": 0,
                }
            alert_perf[r.alert_name]["durations"].append(r.duration_min)
            alert_perf[r.alert_name]["missed"] += r.missed_incidents
            alert_perf[r.alert_name]["suppressed"] += r.alerts_suppressed
        results: list[dict[str, Any]] = []
        for name, perf in alert_perf.items():
            durs = perf["durations"]
            avg_dur = sum(durs) / len(durs) if durs else 0.0
            miss_rate = perf["missed"] / perf["suppressed"] if perf["suppressed"] else 0.0
            if miss_rate > 0.05:
                action = "shorten_window"
                new_dur = avg_dur * 0.7
            elif miss_rate < 0.01:
                action = "extend_window"
                new_dur = avg_dur * 1.3
            else:
                action = "maintain"
                new_dur = avg_dur
            results.append(
                {
                    "alert_name": name,
                    "current_avg_min": round(avg_dur, 2),
                    "recommended_min": round(new_dur, 2),
                    "action": action,
                    "miss_rate": round(miss_rate, 4),
                }
            )
        results.sort(
            key=lambda x: x["miss_rate"],
            reverse=True,
        )
        return results
