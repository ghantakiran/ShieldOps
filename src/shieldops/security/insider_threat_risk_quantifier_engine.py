"""Insider Threat Risk Quantifier Engine —
quantify insider threat risk scores,
detect threat escalation, rank users by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatIndicator(StrEnum):
    DATA_HOARDING = "data_hoarding"
    PRIVILEGE_ABUSE = "privilege_abuse"
    ACCESS_ANOMALY = "access_anomaly"
    RESIGNATION_SIGNAL = "resignation_signal"


class RiskCategory(StrEnum):
    IMMINENT = "imminent"
    ELEVATED = "elevated"
    MODERATE = "moderate"
    BASELINE = "baseline"


class AssessmentMethod(StrEnum):
    BEHAVIORAL = "behavioral"
    CONTEXTUAL = "contextual"
    COMPOSITE = "composite"
    TEMPORAL = "temporal"


# --- Models ---


class InsiderThreatRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    threat_indicator: ThreatIndicator = ThreatIndicator.ACCESS_ANOMALY
    risk_category: RiskCategory = RiskCategory.BASELINE
    assessment_method: AssessmentMethod = AssessmentMethod.BEHAVIORAL
    risk_score: float = 0.0
    indicator_weight: float = 1.0
    department: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InsiderThreatAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    risk_category: RiskCategory = RiskCategory.BASELINE
    composite_risk_score: float = 0.0
    escalation_detected: bool = False
    dominant_indicator: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InsiderThreatReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_threat_indicator: dict[str, int] = Field(default_factory=dict)
    by_risk_category: dict[str, int] = Field(default_factory=dict)
    by_assessment_method: dict[str, int] = Field(default_factory=dict)
    high_risk_users: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InsiderThreatRiskQuantifierEngine:
    """Quantify insider threat risk scores, detect threat escalation,
    and rank users by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[InsiderThreatRecord] = []
        self._analyses: dict[str, InsiderThreatAnalysis] = {}
        logger.info(
            "insider_threat_risk_quantifier_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        user_id: str = "",
        threat_indicator: ThreatIndicator = ThreatIndicator.ACCESS_ANOMALY,
        risk_category: RiskCategory = RiskCategory.BASELINE,
        assessment_method: AssessmentMethod = AssessmentMethod.BEHAVIORAL,
        risk_score: float = 0.0,
        indicator_weight: float = 1.0,
        department: str = "",
        description: str = "",
    ) -> InsiderThreatRecord:
        record = InsiderThreatRecord(
            user_id=user_id,
            threat_indicator=threat_indicator,
            risk_category=risk_category,
            assessment_method=assessment_method,
            risk_score=risk_score,
            indicator_weight=indicator_weight,
            department=department,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "insider_threat_risk.record_added",
            record_id=record.id,
            user_id=user_id,
        )
        return record

    def process(self, key: str) -> InsiderThreatAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        composite = round(rec.risk_score * rec.indicator_weight, 2)
        escalated = rec.risk_category in (RiskCategory.IMMINENT, RiskCategory.ELEVATED)
        analysis = InsiderThreatAnalysis(
            user_id=rec.user_id,
            risk_category=rec.risk_category,
            composite_risk_score=composite,
            escalation_detected=escalated,
            dominant_indicator=rec.threat_indicator.value,
            description=(f"User {rec.user_id} composite risk {composite}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> InsiderThreatReport:
        by_ti: dict[str, int] = {}
        by_rc: dict[str, int] = {}
        by_am: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.threat_indicator.value
            by_ti[k] = by_ti.get(k, 0) + 1
            k2 = r.risk_category.value
            by_rc[k2] = by_rc.get(k2, 0) + 1
            k3 = r.assessment_method.value
            by_am[k3] = by_am.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_risk = list(
            {
                r.user_id
                for r in self._records
                if r.risk_category in (RiskCategory.IMMINENT, RiskCategory.ELEVATED)
            }
        )[:10]
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} users with elevated insider threat risk")
        if not recs:
            recs.append("Insider threat levels within acceptable range")
        return InsiderThreatReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_threat_indicator=by_ti,
            by_risk_category=by_rc,
            by_assessment_method=by_am,
            high_risk_users=high_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rc_dist: dict[str, int] = {}
        for r in self._records:
            k = r.risk_category.value
            rc_dist[k] = rc_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_category_distribution": rc_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("insider_threat_risk_quantifier_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def quantify_insider_risk(self) -> list[dict[str, Any]]:
        """Quantify aggregated insider risk per user."""
        user_data: dict[str, list[InsiderThreatRecord]] = {}
        for r in self._records:
            user_data.setdefault(r.user_id, []).append(r)
        results: list[dict[str, Any]] = []
        for uid, recs in user_data.items():
            total_score = sum(rec.risk_score * rec.indicator_weight for rec in recs)
            indicators = list({rec.threat_indicator.value for rec in recs})
            worst_cat = max(
                recs,
                key=lambda x: ["baseline", "moderate", "elevated", "imminent"].index(
                    x.risk_category.value
                ),
            ).risk_category.value
            results.append(
                {
                    "user_id": uid,
                    "composite_risk": round(total_score, 2),
                    "indicators": indicators,
                    "worst_category": worst_cat,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        return results

    def detect_threat_escalation(self) -> list[dict[str, Any]]:
        """Detect users with escalating threat indicators."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.risk_category == RiskCategory.IMMINENT and r.user_id not in seen:
                seen.add(r.user_id)
                results.append(
                    {
                        "user_id": r.user_id,
                        "threat_indicator": r.threat_indicator.value,
                        "risk_score": r.risk_score,
                        "department": r.department,
                        "escalation_level": r.risk_category.value,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_users_by_risk(self) -> list[dict[str, Any]]:
        """Rank all users by composite insider threat risk score."""
        cat_weights = {"imminent": 4, "elevated": 3, "moderate": 2, "baseline": 1}
        user_scores: dict[str, float] = {}
        for r in self._records:
            w = cat_weights.get(r.risk_category.value, 1)
            user_scores[r.user_id] = user_scores.get(r.user_id, 0.0) + (r.risk_score * w)
        results: list[dict[str, Any]] = []
        for uid, score in user_scores.items():
            results.append(
                {
                    "user_id": uid,
                    "total_risk_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_risk_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
