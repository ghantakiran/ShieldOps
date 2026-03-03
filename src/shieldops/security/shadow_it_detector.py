"""Shadow IT Detector — detect unauthorized cloud services, SaaS apps, and rogue servers."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ShadowCategory(StrEnum):
    CLOUD_SERVICE = "cloud_service"
    SAAS_APP = "saas_app"
    PERSONAL_DEVICE = "personal_device"
    UNAUTHORIZED_API = "unauthorized_api"
    ROGUE_SERVER = "rogue_server"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ACCEPTABLE = "acceptable"


class DetectionMethod(StrEnum):
    NETWORK_ANALYSIS = "network_analysis"
    DNS_MONITORING = "dns_monitoring"
    CLOUD_AUDIT = "cloud_audit"
    ENDPOINT_SCAN = "endpoint_scan"
    LOG_ANALYSIS = "log_analysis"


# --- Models ---


class ShadowITRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_name: str = ""
    shadow_category: ShadowCategory = ShadowCategory.CLOUD_SERVICE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    detection_method: DetectionMethod = DetectionMethod.NETWORK_ANALYSIS
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ShadowITAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_name: str = ""
    shadow_category: ShadowCategory = ShadowCategory.CLOUD_SERVICE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ShadowITReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ShadowITDetector:
    """Detect unauthorized cloud services, SaaS apps, and rogue servers."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[ShadowITRecord] = []
        self._analyses: list[ShadowITAnalysis] = []
        logger.info(
            "shadow_it_detector.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_detection(
        self,
        resource_name: str,
        shadow_category: ShadowCategory = ShadowCategory.CLOUD_SERVICE,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        detection_method: DetectionMethod = DetectionMethod.NETWORK_ANALYSIS,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ShadowITRecord:
        record = ShadowITRecord(
            resource_name=resource_name,
            shadow_category=shadow_category,
            risk_level=risk_level,
            detection_method=detection_method,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "shadow_it_detector.detection_recorded",
            record_id=record.id,
            resource_name=resource_name,
            shadow_category=shadow_category.value,
            risk_level=risk_level.value,
        )
        return record

    def get_detection(self, record_id: str) -> ShadowITRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_detections(
        self,
        shadow_category: ShadowCategory | None = None,
        risk_level: RiskLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ShadowITRecord]:
        results = list(self._records)
        if shadow_category is not None:
            results = [r for r in results if r.shadow_category == shadow_category]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        resource_name: str,
        shadow_category: ShadowCategory = ShadowCategory.CLOUD_SERVICE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ShadowITAnalysis:
        analysis = ShadowITAnalysis(
            resource_name=resource_name,
            shadow_category=shadow_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "shadow_it_detector.analysis_added",
            resource_name=resource_name,
            shadow_category=shadow_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by shadow_category; return count and avg risk_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.shadow_category.value
            cat_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for category, scores in cat_data.items():
            result[category] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "resource_name": r.resource_name,
                        "shadow_category": r.shadow_category.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ShadowITReport:
        by_category: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}
        by_detection_method: dict[str, int] = {}
        for r in self._records:
            by_category[r.shadow_category.value] = by_category.get(r.shadow_category.value, 0) + 1
            by_risk_level[r.risk_level.value] = by_risk_level.get(r.risk_level.value, 0) + 1
            by_detection_method[r.detection_method.value] = (
                by_detection_method.get(r.detection_method.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["resource_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} shadow IT resource(s) below risk threshold ({self._risk_threshold})"
            )
        if self._records and avg_risk_score < self._risk_threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._risk_threshold})")
        if not recs:
            recs.append("Shadow IT detection coverage is healthy")
        return ShadowITReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_category=by_category,
            by_risk_level=by_risk_level,
            by_detection_method=by_detection_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("shadow_it_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.shadow_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
