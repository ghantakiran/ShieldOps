"""Service Reliability Scorer
compute composite reliability scores, detect reliability
degradation, rank services by reliability."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReliabilityTier(StrEnum):
    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


class MetricType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


class ScoringModel(StrEnum):
    WEIGHTED = "weighted"
    EQUAL = "equal"
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"


# --- Models ---


class ServiceReliabilityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    reliability_tier: ReliabilityTier = ReliabilityTier.SILVER
    metric_type: MetricType = MetricType.AVAILABILITY
    scoring_model: ScoringModel = ScoringModel.WEIGHTED
    score: float = 0.0
    threshold: float = 99.0
    region: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceReliabilityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    composite_score: float = 0.0
    reliability_tier: ReliabilityTier = ReliabilityTier.SILVER
    degradation_detected: bool = False
    metric_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceReliabilityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_metric_type: dict[str, int] = Field(default_factory=dict)
    by_scoring_model: dict[str, int] = Field(default_factory=dict)
    top_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceReliabilityScorer:
    """Compute composite reliability scores, detect
    reliability degradation, rank services by reliability."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ServiceReliabilityRecord] = []
        self._analyses: dict[str, ServiceReliabilityAnalysis] = {}
        logger.info(
            "service_reliability_scorer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service_id: str = "",
        reliability_tier: ReliabilityTier = ReliabilityTier.SILVER,
        metric_type: MetricType = MetricType.AVAILABILITY,
        scoring_model: ScoringModel = ScoringModel.WEIGHTED,
        score: float = 0.0,
        threshold: float = 99.0,
        region: str = "",
        description: str = "",
    ) -> ServiceReliabilityRecord:
        record = ServiceReliabilityRecord(
            service_id=service_id,
            reliability_tier=reliability_tier,
            metric_type=metric_type,
            scoring_model=scoring_model,
            score=score,
            threshold=threshold,
            region=region,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_reliability_scorer.record_added",
            record_id=record.id,
            service_id=service_id,
        )
        return record

    def process(self, key: str) -> ServiceReliabilityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        metrics = sum(1 for r in self._records if r.service_id == rec.service_id)
        degraded = rec.score < rec.threshold
        analysis = ServiceReliabilityAnalysis(
            service_id=rec.service_id,
            composite_score=round(rec.score, 2),
            reliability_tier=rec.reliability_tier,
            degradation_detected=degraded,
            metric_count=metrics,
            description=f"Service {rec.service_id} score {rec.score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ServiceReliabilityReport:
        by_tier: dict[str, int] = {}
        by_mt: dict[str, int] = {}
        by_sm: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.reliability_tier.value
            by_tier[k] = by_tier.get(k, 0) + 1
            k2 = r.metric_type.value
            by_mt[k2] = by_mt.get(k2, 0) + 1
            k3 = r.scoring_model.value
            by_sm[k3] = by_sm.get(k3, 0) + 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        top = list(
            {
                r.service_id
                for r in self._records
                if r.reliability_tier in (ReliabilityTier.PLATINUM, ReliabilityTier.GOLD)
            }
        )[:10]
        recs: list[str] = []
        if top:
            recs.append(f"{len(top)} top-tier services identified")
        if not recs:
            recs.append("No significant reliability issues detected")
        return ServiceReliabilityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg,
            by_tier=by_tier,
            by_metric_type=by_mt,
            by_scoring_model=by_sm,
            top_services=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            k = r.reliability_tier.value
            tier_dist[k] = tier_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "tier_distribution": tier_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("service_reliability_scorer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_composite_reliability_score(
        self,
    ) -> list[dict[str, Any]]:
        """Aggregate reliability score per service."""
        svc_scores: dict[str, list[float]] = {}
        svc_tiers: dict[str, str] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_id, []).append(r.score)
            svc_tiers[r.service_id] = r.reliability_tier.value
        results: list[dict[str, Any]] = []
        for sid, scores in svc_scores.items():
            total = round(sum(scores), 2)
            avg = round(total / len(scores), 2)
            results.append(
                {
                    "service_id": sid,
                    "reliability_tier": svc_tiers[sid],
                    "composite_score": avg,
                    "metric_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results

    def detect_reliability_degradation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with score below threshold."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.score < r.threshold and r.service_id not in seen:
                seen.add(r.service_id)
                results.append(
                    {
                        "service_id": r.service_id,
                        "reliability_tier": r.reliability_tier.value,
                        "score": r.score,
                        "threshold": r.threshold,
                        "gap": round(r.threshold - r.score, 2),
                    }
                )
        results.sort(key=lambda x: x["gap"], reverse=True)
        return results

    def rank_services_by_reliability(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all services by aggregate reliability."""
        svc_data: dict[str, list[float]] = {}
        svc_tiers: dict[str, str] = {}
        for r in self._records:
            svc_data.setdefault(r.service_id, []).append(r.score)
            svc_tiers[r.service_id] = r.reliability_tier.value
        results: list[dict[str, Any]] = []
        for sid, scores in svc_data.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service_id": sid,
                    "reliability_tier": svc_tiers[sid],
                    "avg_score": avg,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
