"""Watering Hole Detector — detect watering hole attacks via compromise and indicator analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CompromiseType(StrEnum):
    SCRIPT_INJECTION = "script_injection"
    IFRAME_REDIRECT = "iframe_redirect"
    DRIVE_BY_DOWNLOAD = "drive_by_download"
    SUPPLY_CHAIN = "supply_chain"
    DNS_HIJACK = "dns_hijack"


class TargetProfile(StrEnum):
    INDUSTRY_SPECIFIC = "industry_specific"
    GEOGRAPHIC = "geographic"
    ROLE_BASED = "role_based"
    TECHNOLOGY = "technology"
    GENERAL = "general"


class IndicatorType(StrEnum):
    URL_PATTERN = "url_pattern"
    PAYLOAD_HASH = "payload_hash"
    NETWORK_SIGNATURE = "network_signature"
    BEHAVIORAL = "behavioral"
    INFRASTRUCTURE = "infrastructure"


# --- Models ---


class WateringHoleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    waterhole_id: str = ""
    compromise_type: CompromiseType = CompromiseType.SCRIPT_INJECTION
    target_profile: TargetProfile = TargetProfile.INDUSTRY_SPECIFIC
    indicator_type: IndicatorType = IndicatorType.URL_PATTERN
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WateringHoleAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    waterhole_id: str = ""
    compromise_type: CompromiseType = CompromiseType.SCRIPT_INJECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WateringHoleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_compromise: dict[str, int] = Field(default_factory=dict)
    by_profile: dict[str, int] = Field(default_factory=dict)
    by_indicator: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class WateringHoleDetector:
    """Detect watering hole attacks via compromise analysis and indicator matching."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[WateringHoleRecord] = []
        self._analyses: list[WateringHoleAnalysis] = []
        logger.info(
            "watering_hole_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_waterhole(
        self,
        waterhole_id: str,
        compromise_type: CompromiseType = CompromiseType.SCRIPT_INJECTION,
        target_profile: TargetProfile = TargetProfile.INDUSTRY_SPECIFIC,
        indicator_type: IndicatorType = IndicatorType.URL_PATTERN,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WateringHoleRecord:
        record = WateringHoleRecord(
            waterhole_id=waterhole_id,
            compromise_type=compromise_type,
            target_profile=target_profile,
            indicator_type=indicator_type,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "watering_hole_detector.waterhole_recorded",
            record_id=record.id,
            waterhole_id=waterhole_id,
            compromise_type=compromise_type.value,
            target_profile=target_profile.value,
        )
        return record

    def get_waterhole(self, record_id: str) -> WateringHoleRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_waterholes(
        self,
        compromise_type: CompromiseType | None = None,
        target_profile: TargetProfile | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WateringHoleRecord]:
        results = list(self._records)
        if compromise_type is not None:
            results = [r for r in results if r.compromise_type == compromise_type]
        if target_profile is not None:
            results = [r for r in results if r.target_profile == target_profile]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        waterhole_id: str,
        compromise_type: CompromiseType = CompromiseType.SCRIPT_INJECTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WateringHoleAnalysis:
        analysis = WateringHoleAnalysis(
            waterhole_id=waterhole_id,
            compromise_type=compromise_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "watering_hole_detector.analysis_added",
            waterhole_id=waterhole_id,
            compromise_type=compromise_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_compromise_distribution(self) -> dict[str, Any]:
        """Group by compromise_type; return count and avg detection_score."""
        compromise_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compromise_type.value
            compromise_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for compromise, scores in compromise_data.items():
            result[compromise] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "waterhole_id": r.waterhole_id,
                        "compromise_type": r.compromise_type.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        """Group by service, avg detection_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_detection_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> WateringHoleReport:
        by_compromise: dict[str, int] = {}
        by_profile: dict[str, int] = {}
        by_indicator: dict[str, int] = {}
        for r in self._records:
            by_compromise[r.compromise_type.value] = (
                by_compromise.get(r.compromise_type.value, 0) + 1
            )
            by_profile[r.target_profile.value] = by_profile.get(r.target_profile.value, 0) + 1
            by_indicator[r.indicator_type.value] = by_indicator.get(r.indicator_type.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["waterhole_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} waterhole record(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Watering hole detection is healthy")
        return WateringHoleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_compromise=by_compromise,
            by_profile=by_profile,
            by_indicator=by_indicator,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("watering_hole_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        compromise_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compromise_type.value
            compromise_dist[key] = compromise_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "compromise_distribution": compromise_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
