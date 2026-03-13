"""Alert Quality Lifecycle Scorer
score alert actionability, identify low value alerts,
track alert quality trend."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QualityGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class AlertPhase(StrEnum):
    CREATION = "creation"
    ACTIVE = "active"
    TUNING = "tuning"
    RETIREMENT = "retirement"


class ActionabilityLevel(StrEnum):
    IMMEDIATE = "immediate"
    DEFERRED = "deferred"
    INFORMATIONAL = "informational"
    NOISE = "noise"


# --- Models ---


class AlertQualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    quality_grade: QualityGrade = QualityGrade.FAIR
    alert_phase: AlertPhase = AlertPhase.ACTIVE
    actionability: ActionabilityLevel = ActionabilityLevel.INFORMATIONAL
    quality_score: float = 0.0
    action_taken: bool = False
    resolution_time_min: float = 0.0
    source: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertQualityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    quality_grade: QualityGrade = QualityGrade.FAIR
    computed_score: float = 0.0
    action_rate: float = 0.0
    avg_resolution_min: float = 0.0
    alert_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_quality_score: float = 0.0
    by_quality_grade: dict[str, int] = Field(default_factory=dict)
    by_alert_phase: dict[str, int] = Field(default_factory=dict)
    by_actionability: dict[str, int] = Field(default_factory=dict)
    low_quality_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertQualityLifecycleScorer:
    """Score alert actionability, identify low value
    alerts, track alert quality trend."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AlertQualityRecord] = []
        self._analyses: dict[str, AlertQualityAnalysis] = {}
        logger.info(
            "alert_quality_lifecycle_scorer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        alert_name: str = "",
        quality_grade: QualityGrade = QualityGrade.FAIR,
        alert_phase: AlertPhase = AlertPhase.ACTIVE,
        actionability: ActionabilityLevel = (ActionabilityLevel.INFORMATIONAL),
        quality_score: float = 0.0,
        action_taken: bool = False,
        resolution_time_min: float = 0.0,
        source: str = "",
    ) -> AlertQualityRecord:
        record = AlertQualityRecord(
            alert_name=alert_name,
            quality_grade=quality_grade,
            alert_phase=alert_phase,
            actionability=actionability,
            quality_score=quality_score,
            action_taken=action_taken,
            resolution_time_min=resolution_time_min,
            source=source,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_quality.record_added",
            record_id=record.id,
            alert_name=alert_name,
        )
        return record

    def process(self, key: str) -> AlertQualityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.alert_name == rec.alert_name]
        count = len(related)
        action_rate = sum(1 for r in related if r.action_taken) / count if count else 0.0
        avg_res = sum(r.resolution_time_min for r in related) / count if count else 0.0
        analysis = AlertQualityAnalysis(
            alert_name=rec.alert_name,
            quality_grade=rec.quality_grade,
            computed_score=round(rec.quality_score, 2),
            action_rate=round(action_rate, 2),
            avg_resolution_min=round(avg_res, 2),
            alert_count=count,
            description=(f"Alert {rec.alert_name} quality {rec.quality_score:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AlertQualityReport:
        by_qg: dict[str, int] = {}
        by_ap: dict[str, int] = {}
        by_al: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.quality_grade.value
            by_qg[k] = by_qg.get(k, 0) + 1
            k2 = r.alert_phase.value
            by_ap[k2] = by_ap.get(k2, 0) + 1
            k3 = r.actionability.value
            by_al[k3] = by_al.get(k3, 0) + 1
            scores.append(r.quality_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        low = list(
            {
                r.alert_name
                for r in self._records
                if r.quality_grade in (QualityGrade.FAIR, QualityGrade.POOR)
            }
        )[:10]
        recs: list[str] = []
        if low:
            recs.append(f"{len(low)} low-quality alerts found")
        if not recs:
            recs.append("Alert quality within norms")
        return AlertQualityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_quality_score=avg,
            by_quality_grade=by_qg,
            by_alert_phase=by_ap,
            by_actionability=by_al,
            low_quality_alerts=low,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        qg_dist: dict[str, int] = {}
        for r in self._records:
            k = r.quality_grade.value
            qg_dist[k] = qg_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_grade_distribution": qg_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("alert_quality_lifecycle_scorer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def score_alert_actionability(
        self,
    ) -> list[dict[str, Any]]:
        """Score actionability per alert name."""
        alert_data: dict[str, list[bool]] = {}
        alert_scores: dict[str, list[float]] = {}
        for r in self._records:
            alert_data.setdefault(r.alert_name, []).append(r.action_taken)
            alert_scores.setdefault(r.alert_name, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for name, actions in alert_data.items():
            rate = sum(1 for a in actions if a) / len(actions) if actions else 0.0
            scores = alert_scores[name]
            avg_q = sum(scores) / len(scores) if scores else 0.0
            results.append(
                {
                    "alert_name": name,
                    "action_rate": round(rate, 2),
                    "avg_quality_score": round(avg_q, 2),
                    "total_fires": len(actions),
                    "actionability": "high" if rate > 0.7 else "low",
                }
            )
        results.sort(
            key=lambda x: x["action_rate"],
            reverse=True,
        )
        return results

    def identify_low_value_alerts(
        self,
    ) -> list[dict[str, Any]]:
        """Identify alerts with low value."""
        alert_data: dict[str, list[float]] = {}
        alert_actions: dict[str, list[bool]] = {}
        for r in self._records:
            alert_data.setdefault(r.alert_name, []).append(r.quality_score)
            alert_actions.setdefault(r.alert_name, []).append(r.action_taken)
        results: list[dict[str, Any]] = []
        for name, scores in alert_data.items():
            avg = sum(scores) / len(scores) if scores else 0.0
            acts = alert_actions[name]
            act_rate = sum(1 for a in acts if a) / len(acts) if acts else 0.0
            if avg < 50.0 or act_rate < 0.3:
                results.append(
                    {
                        "alert_name": name,
                        "avg_quality": round(avg, 2),
                        "action_rate": round(act_rate, 2),
                        "fire_count": len(scores),
                        "recommendation": "retire" if avg < 20.0 else "tune",
                    }
                )
        results.sort(
            key=lambda x: x["avg_quality"],
        )
        return results

    def track_alert_quality_trend(
        self,
    ) -> list[dict[str, Any]]:
        """Track quality trend over time."""
        alert_ts: dict[str, list[tuple[float, float]]] = {}
        for r in self._records:
            alert_ts.setdefault(r.alert_name, []).append((r.created_at, r.quality_score))
        results: list[dict[str, Any]] = []
        for name, ts_data in alert_ts.items():
            ts_data.sort(key=lambda x: x[0])
            if len(ts_data) < 2:
                trend = "stable"
            else:
                mid = len(ts_data) // 2
                first = sum(s for _, s in ts_data[:mid]) / max(mid, 1)
                second = sum(s for _, s in ts_data[mid:]) / max(len(ts_data) - mid, 1)
                if second > first * 1.1:
                    trend = "improving"
                elif second < first * 0.9:
                    trend = "degrading"
                else:
                    trend = "stable"
            results.append(
                {
                    "alert_name": name,
                    "data_points": len(ts_data),
                    "trend": trend,
                    "latest_score": round(ts_data[-1][1], 2),
                }
            )
        results.sort(
            key=lambda x: x["latest_score"],
            reverse=True,
        )
        return results
