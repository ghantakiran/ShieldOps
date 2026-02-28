"""Dynamic Risk Scorer — real-time risk scoring with adaptive signal weighting."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskFactor(StrEnum):
    INCIDENT_FREQUENCY = "incident_frequency"
    DEPLOYMENT_VELOCITY = "deployment_velocity"
    VULNERABILITY_COUNT = "vulnerability_count"
    SLO_BURN_RATE = "slo_burn_rate"
    THREAT_LEVEL = "threat_level"


class ScoreAdjustment(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    SPIKE = "spike"
    DECAY = "decay"
    STABLE = "stable"


class ScoringModel(StrEnum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    BAYESIAN = "bayesian"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"


# --- Models ---


class RiskScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    risk_factor: RiskFactor = RiskFactor.INCIDENT_FREQUENCY
    score_adjustment: ScoreAdjustment = ScoreAdjustment.STABLE
    scoring_model: ScoringModel = ScoringModel.LINEAR
    risk_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ScoreAdjustmentEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_label: str = ""
    risk_factor: RiskFactor = RiskFactor.INCIDENT_FREQUENCY
    score_adjustment: ScoreAdjustment = ScoreAdjustment.INCREASE
    magnitude: float = 0.0
    created_at: float = Field(default_factory=time.time)


class DynamicRiskReport(BaseModel):
    total_scores: int = 0
    total_adjustments: int = 0
    high_risk_rate_pct: float = 0.0
    by_factor: dict[str, int] = Field(default_factory=dict)
    by_adjustment: dict[str, int] = Field(default_factory=dict)
    spike_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DynamicRiskScorer:
    """Real-time risk scoring with adaptive signal weighting."""

    def __init__(
        self,
        max_records: int = 200000,
        high_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._high_threshold = high_threshold
        self._records: list[RiskScoreRecord] = []
        self._adjustments: list[ScoreAdjustmentEvent] = []
        logger.info(
            "dynamic_risk_scorer.initialized",
            max_records=max_records,
            high_threshold=high_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_score(
        self,
        service_name: str,
        risk_factor: RiskFactor = RiskFactor.INCIDENT_FREQUENCY,
        score_adjustment: ScoreAdjustment = ScoreAdjustment.STABLE,
        scoring_model: ScoringModel = ScoringModel.LINEAR,
        risk_score: float = 0.0,
        details: str = "",
    ) -> RiskScoreRecord:
        record = RiskScoreRecord(
            service_name=service_name,
            risk_factor=risk_factor,
            score_adjustment=score_adjustment,
            scoring_model=scoring_model,
            risk_score=risk_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dynamic_risk_scorer.score_recorded",
            record_id=record.id,
            service_name=service_name,
            risk_factor=risk_factor.value,
            score_adjustment=score_adjustment.value,
        )
        return record

    def get_score(self, record_id: str) -> RiskScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scores(
        self,
        service_name: str | None = None,
        risk_factor: RiskFactor | None = None,
        limit: int = 50,
    ) -> list[RiskScoreRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if risk_factor is not None:
            results = [r for r in results if r.risk_factor == risk_factor]
        return results[-limit:]

    def add_adjustment(
        self,
        event_label: str,
        risk_factor: RiskFactor = RiskFactor.INCIDENT_FREQUENCY,
        score_adjustment: ScoreAdjustment = ScoreAdjustment.INCREASE,
        magnitude: float = 0.0,
    ) -> ScoreAdjustmentEvent:
        event = ScoreAdjustmentEvent(
            event_label=event_label,
            risk_factor=risk_factor,
            score_adjustment=score_adjustment,
            magnitude=magnitude,
        )
        self._adjustments.append(event)
        if len(self._adjustments) > self._max_records:
            self._adjustments = self._adjustments[-self._max_records :]
        logger.info(
            "dynamic_risk_scorer.adjustment_added",
            event_label=event_label,
            risk_factor=risk_factor.value,
            score_adjustment=score_adjustment.value,
        )
        return event

    # -- domain operations -----------------------------------------------

    def analyze_risk_trajectory(self, service_name: str) -> dict[str, Any]:
        """Analyze risk trajectory for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        high_risk = sum(1 for r in records if r.risk_score >= self._high_threshold)
        high_risk_rate = round(high_risk / len(records) * 100, 2)
        avg_score = round(sum(r.risk_score for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total_scores": len(records),
            "high_risk_count": high_risk,
            "high_risk_rate_pct": high_risk_rate,
            "avg_risk_score": avg_score,
            "meets_threshold": avg_score >= self._high_threshold,
        }

    def identify_high_risk_services(self) -> list[dict[str, Any]]:
        """Find services with repeated high-risk scores."""
        high_counts: dict[str, int] = {}
        for r in self._records:
            if r.score_adjustment in (
                ScoreAdjustment.INCREASE,
                ScoreAdjustment.SPIKE,
            ):
                high_counts[r.service_name] = high_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in high_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "high_risk_count": count,
                    }
                )
        results.sort(key=lambda x: x["high_risk_count"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Rank services by score record count descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.service_name] = freq.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in freq.items():
            results.append(
                {
                    "service_name": svc,
                    "score_count": count,
                }
            )
        results.sort(key=lambda x: x["score_count"], reverse=True)
        return results

    def detect_risk_spikes(self) -> list[dict[str, Any]]:
        """Detect services with risk spikes (>3 non-stable adjustments)."""
        svc_non_stable: dict[str, int] = {}
        for r in self._records:
            if r.score_adjustment != ScoreAdjustment.STABLE:
                svc_non_stable[r.service_name] = svc_non_stable.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non_stable.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_stable_count": count,
                        "spike_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_stable_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DynamicRiskReport:
        by_factor: dict[str, int] = {}
        by_adjustment: dict[str, int] = {}
        for r in self._records:
            by_factor[r.risk_factor.value] = by_factor.get(r.risk_factor.value, 0) + 1
            by_adjustment[r.score_adjustment.value] = (
                by_adjustment.get(r.score_adjustment.value, 0) + 1
            )
        high_count = sum(1 for r in self._records if r.risk_score >= self._high_threshold)
        high_risk_rate = round(high_count / len(self._records) * 100, 2) if self._records else 0.0
        high_risk_svcs = sum(1 for d in self.identify_high_risk_services())
        recs: list[str] = []
        if high_risk_rate > 0:
            recs.append(f"High risk rate {high_risk_rate}% exceeds 0% baseline")
        if high_risk_svcs > 0:
            recs.append(f"{high_risk_svcs} service(s) with high risk scores")
        spikes = len(self.detect_risk_spikes())
        if spikes > 0:
            recs.append(f"{spikes} service(s) detected with risk spikes")
        if not recs:
            recs.append("Dynamic risk scoring meets targets")
        return DynamicRiskReport(
            total_scores=len(self._records),
            total_adjustments=len(self._adjustments),
            high_risk_rate_pct=high_risk_rate,
            by_factor=by_factor,
            by_adjustment=by_adjustment,
            spike_count=spikes,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._adjustments.clear()
        logger.info("dynamic_risk_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_factor.value
            factor_dist[key] = factor_dist.get(key, 0) + 1
        return {
            "total_scores": len(self._records),
            "total_adjustments": len(self._adjustments),
            "high_threshold": self._high_threshold,
            "factor_distribution": factor_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
