"""API Rate Limit Intelligence.

Predict throttling events, analyze quota utilization,
and recommend quota adjustments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QuotaStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    NEAR_LIMIT = "near_limit"
    EXCEEDED = "exceeded"


class ThrottleRisk(StrEnum):
    IMMINENT = "imminent"
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"


class AdjustmentDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"
    RESTRUCTURE = "restructure"


# --- Models ---


class RateLimitRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    consumer_id: str = ""
    quota_status: QuotaStatus = QuotaStatus.HEALTHY
    throttle_risk: ThrottleRisk = ThrottleRisk.UNLIKELY
    adjustment_direction: AdjustmentDirection = AdjustmentDirection.MAINTAIN
    current_usage: float = 0.0
    quota_limit: float = 1000.0
    utilization_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RateLimitAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_name: str = ""
    consumer_id: str = ""
    at_risk: bool = False
    utilization_pct: float = 0.0
    headroom_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RateLimitReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_utilization: float = 0.0
    by_quota_status: dict[str, int] = Field(default_factory=dict)
    by_throttle_risk: dict[str, int] = Field(default_factory=dict)
    by_adjustment_direction: dict[str, int] = Field(default_factory=dict)
    at_risk_consumers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ApiRateLimitIntelligence:
    """Predict throttling, analyze quota utilization,
    recommend quota adjustments."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RateLimitRecord] = []
        self._analyses: dict[str, RateLimitAnalysis] = {}
        logger.info(
            "api_rate_limit_intelligence.init",
            max_records=max_records,
        )

    def record_item(
        self,
        api_name: str = "",
        consumer_id: str = "",
        quota_status: QuotaStatus = (QuotaStatus.HEALTHY),
        throttle_risk: ThrottleRisk = (ThrottleRisk.UNLIKELY),
        adjustment_direction: AdjustmentDirection = (AdjustmentDirection.MAINTAIN),
        current_usage: float = 0.0,
        quota_limit: float = 1000.0,
        utilization_pct: float = 0.0,
    ) -> RateLimitRecord:
        record = RateLimitRecord(
            api_name=api_name,
            consumer_id=consumer_id,
            quota_status=quota_status,
            throttle_risk=throttle_risk,
            adjustment_direction=adjustment_direction,
            current_usage=current_usage,
            quota_limit=quota_limit,
            utilization_pct=utilization_pct,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "rate_limit.record_added",
            record_id=record.id,
            api_name=api_name,
        )
        return record

    def process(self, key: str) -> RateLimitAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        at_risk = rec.throttle_risk in (
            ThrottleRisk.IMMINENT,
            ThrottleRisk.LIKELY,
        )
        headroom = round(100.0 - rec.utilization_pct, 2)
        analysis = RateLimitAnalysis(
            api_name=rec.api_name,
            consumer_id=rec.consumer_id,
            at_risk=at_risk,
            utilization_pct=round(rec.utilization_pct, 2),
            headroom_pct=headroom,
            description=(f"Consumer {rec.consumer_id} util {rec.utilization_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RateLimitReport:
        by_qs: dict[str, int] = {}
        by_tr: dict[str, int] = {}
        by_ad: dict[str, int] = {}
        utils: list[float] = []
        for r in self._records:
            k = r.quota_status.value
            by_qs[k] = by_qs.get(k, 0) + 1
            k2 = r.throttle_risk.value
            by_tr[k2] = by_tr.get(k2, 0) + 1
            k3 = r.adjustment_direction.value
            by_ad[k3] = by_ad.get(k3, 0) + 1
            utils.append(r.utilization_pct)
        avg = round(sum(utils) / len(utils), 2) if utils else 0.0
        at_risk = list(
            {
                r.consumer_id
                for r in self._records
                if r.throttle_risk
                in (
                    ThrottleRisk.IMMINENT,
                    ThrottleRisk.LIKELY,
                )
            }
        )[:10]
        recs: list[str] = []
        if at_risk:
            recs.append(f"{len(at_risk)} at-risk consumers")
        if not recs:
            recs.append("All quotas healthy")
        return RateLimitReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_utilization=avg,
            by_quota_status=by_qs,
            by_throttle_risk=by_tr,
            by_adjustment_direction=by_ad,
            at_risk_consumers=at_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.quota_status.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quota_status_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("api_rate_limit_intelligence.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def predict_throttling_events(
        self,
    ) -> list[dict[str, Any]]:
        """Predict consumers likely to be throttled."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.throttle_risk
                in (
                    ThrottleRisk.IMMINENT,
                    ThrottleRisk.LIKELY,
                )
                and r.consumer_id not in seen
            ):
                seen.add(r.consumer_id)
                results.append(
                    {
                        "consumer_id": (r.consumer_id),
                        "api_name": r.api_name,
                        "risk": (r.throttle_risk.value),
                        "utilization_pct": (r.utilization_pct),
                        "quota_limit": r.quota_limit,
                    }
                )
        results.sort(
            key=lambda x: x["utilization_pct"],
            reverse=True,
        )
        return results

    def analyze_quota_utilization(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze quota utilization per consumer."""
        consumer_util: dict[str, list[float]] = {}
        consumer_api: dict[str, str] = {}
        for r in self._records:
            consumer_util.setdefault(r.consumer_id, []).append(r.utilization_pct)
            consumer_api[r.consumer_id] = r.api_name
        results: list[dict[str, Any]] = []
        for cid, utils in consumer_util.items():
            avg = round(sum(utils) / len(utils), 2)
            results.append(
                {
                    "consumer_id": cid,
                    "api_name": consumer_api[cid],
                    "avg_utilization": avg,
                    "max_utilization": round(max(utils), 2),
                    "sample_count": len(utils),
                }
            )
        results.sort(
            key=lambda x: x["avg_utilization"],
            reverse=True,
        )
        return results

    def recommend_quota_adjustments(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend quota adjustments."""
        consumer_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.consumer_id not in consumer_data:
                rec = "Maintain"
                if r.utilization_pct > 90:
                    rec = "Increase quota"
                elif r.utilization_pct < 20:
                    rec = "Decrease quota"
                consumer_data[r.consumer_id] = {
                    "consumer_id": r.consumer_id,
                    "api_name": r.api_name,
                    "current_util": (r.utilization_pct),
                    "quota_limit": r.quota_limit,
                    "recommendation": rec,
                }
        results = list(consumer_data.values())
        results.sort(
            key=lambda x: x["current_util"],
            reverse=True,
        )
        return results
