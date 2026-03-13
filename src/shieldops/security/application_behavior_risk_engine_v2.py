"""Application Behavior Risk Engine v2 —
analyze advanced application behavior risk,
detect attack patterns, rank applications by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BehaviorType(StrEnum):
    INJECTION_ATTEMPT = "injection_attempt"
    AUTH_BYPASS = "auth_bypass"
    API_ABUSE = "api_abuse"
    RESOURCE_ABUSE = "resource_abuse"


class DetectionLayer(StrEnum):
    WAF = "waf"
    RUNTIME = "runtime"
    CODE = "code"
    NETWORK = "network"


class RiskScore(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class AppBehaviorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str = ""
    behavior_type: BehaviorType = BehaviorType.API_ABUSE
    detection_layer: DetectionLayer = DetectionLayer.WAF
    risk_score_level: RiskScore = RiskScore.LOW
    risk_score: float = 0.0
    request_count: int = 0
    error_rate: float = 0.0
    endpoint: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AppBehaviorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str = ""
    behavior_type: BehaviorType = BehaviorType.API_ABUSE
    composite_risk: float = 0.0
    attack_pattern_detected: bool = False
    risk_level: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AppBehaviorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_behavior_type: dict[str, int] = Field(default_factory=dict)
    by_detection_layer: dict[str, int] = Field(default_factory=dict)
    by_risk_score_level: dict[str, int] = Field(default_factory=dict)
    high_risk_applications: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ApplicationBehaviorRiskEngineV2:
    """Analyze advanced application behavior risk, detect attack patterns,
    and rank applications by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AppBehaviorRecord] = []
        self._analyses: dict[str, AppBehaviorAnalysis] = {}
        logger.info(
            "application_behavior_risk_engine_v2.init",
            max_records=max_records,
        )

    def add_record(
        self,
        application_id: str = "",
        behavior_type: BehaviorType = BehaviorType.API_ABUSE,
        detection_layer: DetectionLayer = DetectionLayer.WAF,
        risk_score_level: RiskScore = RiskScore.LOW,
        risk_score: float = 0.0,
        request_count: int = 0,
        error_rate: float = 0.0,
        endpoint: str = "",
        description: str = "",
    ) -> AppBehaviorRecord:
        record = AppBehaviorRecord(
            application_id=application_id,
            behavior_type=behavior_type,
            detection_layer=detection_layer,
            risk_score_level=risk_score_level,
            risk_score=risk_score,
            request_count=request_count,
            error_rate=error_rate,
            endpoint=endpoint,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "app_behavior_risk.record_added",
            record_id=record.id,
            application_id=application_id,
        )
        return record

    def process(self, key: str) -> AppBehaviorAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        rs_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        w = rs_weights.get(rec.risk_score_level.value, 1)
        composite = round(w * rec.risk_score * (1 + rec.error_rate), 2)
        attack_detected = (
            rec.behavior_type
            in (
                BehaviorType.INJECTION_ATTEMPT,
                BehaviorType.AUTH_BYPASS,
            )
            and rec.risk_score > 0.55
        )
        analysis = AppBehaviorAnalysis(
            application_id=rec.application_id,
            behavior_type=rec.behavior_type,
            composite_risk=composite,
            attack_pattern_detected=attack_detected,
            risk_level=rec.risk_score_level.value,
            description=(
                f"App {rec.application_id} {rec.behavior_type.value} endpoint={rec.endpoint}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AppBehaviorReport:
        by_bt: dict[str, int] = {}
        by_dl: dict[str, int] = {}
        by_rs: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.behavior_type.value
            by_bt[k] = by_bt.get(k, 0) + 1
            k2 = r.detection_layer.value
            by_dl[k2] = by_dl.get(k2, 0) + 1
            k3 = r.risk_score_level.value
            by_rs[k3] = by_rs.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_risk_apps = list(
            {
                r.application_id
                for r in self._records
                if r.risk_score_level in (RiskScore.CRITICAL, RiskScore.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high_risk_apps:
            recs.append(f"{len(high_risk_apps)} applications with critical/high risk behavior")
        if not recs:
            recs.append("Application behavior risk within acceptable thresholds")
        return AppBehaviorReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_behavior_type=by_bt,
            by_detection_layer=by_dl,
            by_risk_score_level=by_rs,
            high_risk_applications=high_risk_apps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        bt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.behavior_type.value
            bt_dist[k] = bt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "behavior_type_distribution": bt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("application_behavior_risk_engine_v2.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def analyze_application_behavior(self) -> list[dict[str, Any]]:
        """Analyze aggregated behavior risk per application."""
        app_data: dict[str, list[AppBehaviorRecord]] = {}
        for r in self._records:
            app_data.setdefault(r.application_id, []).append(r)
        rs_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        results: list[dict[str, Any]] = []
        for aid, recs in app_data.items():
            total_risk = sum(
                rs_weights.get(rec.risk_score_level.value, 1) * rec.risk_score for rec in recs
            )
            avg_error = sum(rec.error_rate for rec in recs) / len(recs)
            behavior_types = list({rec.behavior_type.value for rec in recs})
            endpoints = list({rec.endpoint for rec in recs if rec.endpoint})
            results.append(
                {
                    "application_id": aid,
                    "composite_risk": round(total_risk, 2),
                    "avg_error_rate": round(avg_error, 4),
                    "behavior_types": behavior_types,
                    "endpoints_affected": len(endpoints),
                    "event_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        return results

    def detect_attack_patterns(self) -> list[dict[str, Any]]:
        """Detect confirmed attack patterns in application behavior."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            pat_key = f"{r.application_id}:{r.behavior_type.value}"
            if (
                r.behavior_type in (BehaviorType.INJECTION_ATTEMPT, BehaviorType.AUTH_BYPASS)
                and r.risk_score > 0.55
                and pat_key not in seen
            ):
                seen.add(pat_key)
                results.append(
                    {
                        "application_id": r.application_id,
                        "behavior_type": r.behavior_type.value,
                        "detection_layer": r.detection_layer.value,
                        "risk_score": r.risk_score,
                        "endpoint": r.endpoint,
                        "request_count": r.request_count,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_applications_by_risk(self) -> list[dict[str, Any]]:
        """Rank applications by composite behavior risk score."""
        rs_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        app_scores: dict[str, float] = {}
        for r in self._records:
            w = rs_weights.get(r.risk_score_level.value, 1)
            app_scores[r.application_id] = app_scores.get(r.application_id, 0.0) + (
                w * r.risk_score
            )
        results: list[dict[str, Any]] = []
        for aid, score in app_scores.items():
            results.append(
                {
                    "application_id": aid,
                    "total_risk_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_risk_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
