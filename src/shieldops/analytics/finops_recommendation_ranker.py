"""FinOps Recommendation Ranker
rank by ROI-adjusted effort, assess recommendation
risk, track recommendation adoption."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecommendationType(StrEnum):
    RIGHTSIZING = "rightsizing"
    RESERVATION = "reservation"
    ELIMINATION = "elimination"
    OPTIMIZATION = "optimization"


class RiskLevel(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class AdoptionStatus(StrEnum):
    IMPLEMENTED = "implemented"
    IN_PROGRESS = "in_progress"
    DEFERRED = "deferred"
    REJECTED = "rejected"


# --- Models ---


class RecommendationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_id: str = ""
    recommendation_type: RecommendationType = RecommendationType.RIGHTSIZING
    risk_level: RiskLevel = RiskLevel.LOW
    adoption_status: AdoptionStatus = AdoptionStatus.DEFERRED
    estimated_savings: float = 0.0
    effort_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecommendationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_id: str = ""
    recommendation_type: RecommendationType = RecommendationType.RIGHTSIZING
    roi_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    priority_rank: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecommendationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_estimated_savings: float = 0.0
    by_recommendation_type: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_adoption_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class FinopsRecommendationRanker:
    """Rank by ROI-adjusted effort, assess risk,
    track adoption."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RecommendationRecord] = []
        self._analyses: dict[str, RecommendationAnalysis] = {}
        logger.info(
            "finops_recommendation_ranker.init",
            max_records=max_records,
        )

    def add_record(
        self,
        recommendation_id: str = "",
        recommendation_type: RecommendationType = (RecommendationType.RIGHTSIZING),
        risk_level: RiskLevel = RiskLevel.LOW,
        adoption_status: AdoptionStatus = (AdoptionStatus.DEFERRED),
        estimated_savings: float = 0.0,
        effort_hours: float = 0.0,
        description: str = "",
    ) -> RecommendationRecord:
        record = RecommendationRecord(
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type,
            risk_level=risk_level,
            adoption_status=adoption_status,
            estimated_savings=estimated_savings,
            effort_hours=effort_hours,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "finops_recommendation.record_added",
            record_id=record.id,
            recommendation_id=recommendation_id,
        )
        return record

    def process(self, key: str) -> RecommendationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        roi = 0.0
        if rec.effort_hours > 0:
            roi = round(
                rec.estimated_savings / rec.effort_hours,
                2,
            )
        analysis = RecommendationAnalysis(
            recommendation_id=rec.recommendation_id,
            recommendation_type=(rec.recommendation_type),
            roi_score=roi,
            risk_level=rec.risk_level,
            description=(f"Rec {rec.recommendation_id} ROI {roi}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> RecommendationReport:
        by_rt: dict[str, int] = {}
        by_rl: dict[str, int] = {}
        by_as: dict[str, int] = {}
        total_sav = 0.0
        for r in self._records:
            k = r.recommendation_type.value
            by_rt[k] = by_rt.get(k, 0) + 1
            k2 = r.risk_level.value
            by_rl[k2] = by_rl.get(k2, 0) + 1
            k3 = r.adoption_status.value
            by_as[k3] = by_as.get(k3, 0) + 1
            total_sav += r.estimated_savings
        recs: list[str] = []
        deferred = [r for r in self._records if r.adoption_status == AdoptionStatus.DEFERRED]
        if deferred:
            recs.append(f"{len(deferred)} deferred recommendations pending")
        if not recs:
            recs.append("All recommendations addressed")
        return RecommendationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_estimated_savings=round(total_sav, 2),
            by_recommendation_type=by_rt,
            by_risk_level=by_rl,
            by_adoption_status=by_as,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.recommendation_type.value
            rt_dist[k] = rt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "recommendation_type_dist": rt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("finops_recommendation_ranker.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def rank_by_roi_adjusted_effort(
        self,
    ) -> list[dict[str, Any]]:
        """Rank recommendations by ROI/effort."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.recommendation_id not in seen:
                seen.add(r.recommendation_id)
                roi = 0.0
                if r.effort_hours > 0:
                    roi = round(
                        r.estimated_savings / r.effort_hours,
                        2,
                    )
                results.append(
                    {
                        "recommendation_id": (r.recommendation_id),
                        "type": (r.recommendation_type.value),
                        "savings": (r.estimated_savings),
                        "effort_hours": (r.effort_hours),
                        "roi_score": roi,
                        "rank": 0,
                    }
                )
        results.sort(
            key=lambda x: x["roi_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results

    def assess_recommendation_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Assess risk per recommendation."""
        risk_map: dict[str, list[float]] = {}
        for r in self._records:
            k = r.risk_level.value
            risk_map.setdefault(k, []).append(r.estimated_savings)
        results: list[dict[str, Any]] = []
        for level, savings in risk_map.items():
            total = round(sum(savings), 2)
            results.append(
                {
                    "risk_level": level,
                    "count": len(savings),
                    "total_savings": total,
                    "avg_savings": round(total / len(savings), 2),
                }
            )
        return results

    def track_recommendation_adoption(
        self,
    ) -> list[dict[str, Any]]:
        """Track adoption status."""
        status_map: dict[str, int] = {}
        status_sav: dict[str, float] = {}
        for r in self._records:
            k = r.adoption_status.value
            status_map[k] = status_map.get(k, 0) + 1
            status_sav[k] = status_sav.get(k, 0.0) + r.estimated_savings
        results: list[dict[str, Any]] = []
        for status, count in status_map.items():
            results.append(
                {
                    "status": status,
                    "count": count,
                    "total_savings": round(status_sav[status], 2),
                }
            )
        return results
