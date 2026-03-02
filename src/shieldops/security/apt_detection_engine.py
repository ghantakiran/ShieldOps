"""APT Detection Engine — long dwell time, slow exfiltration, living-off-the-land."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class APTIndicator(StrEnum):
    LONG_DWELL = "long_dwell"
    SLOW_EXFILTRATION = "slow_exfiltration"
    LIVING_OFF_LAND = "living_off_land"
    CREDENTIAL_THEFT = "credential_theft"
    PERSISTENCE_MECHANISM = "persistence_mechanism"


class APTStage(StrEnum):
    INITIAL_COMPROMISE = "initial_compromise"
    ESTABLISH_FOOTHOLD = "establish_foothold"
    ESCALATE_PRIVILEGE = "escalate_privilege"
    INTERNAL_RECON = "internal_recon"
    MISSION_COMPLETE = "mission_complete"


class DetectionSource(StrEnum):
    EDR = "edr"
    NETWORK = "network"
    SIEM = "siem"
    THREAT_INTEL = "threat_intel"
    BEHAVIORAL_ANALYTICS = "behavioral_analytics"


# --- Models ---


class APTRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    apt_indicator: APTIndicator = APTIndicator.LONG_DWELL
    apt_stage: APTStage = APTStage.INITIAL_COMPROMISE
    detection_source: DetectionSource = DetectionSource.EDR
    threat_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class APTAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    apt_indicator: APTIndicator = APTIndicator.LONG_DWELL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class APTReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_threat_count: int = 0
    avg_threat_score: float = 0.0
    by_indicator: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_high_threat: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class APTDetectionEngine:
    """Detect advanced persistent threats via long dwell time and behavioral analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        apt_threat_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._apt_threat_threshold = apt_threat_threshold
        self._records: list[APTRecord] = []
        self._analyses: list[APTAnalysis] = []
        logger.info(
            "apt_detection_engine.initialized",
            max_records=max_records,
            apt_threat_threshold=apt_threat_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_detection(
        self,
        campaign_name: str,
        apt_indicator: APTIndicator = APTIndicator.LONG_DWELL,
        apt_stage: APTStage = APTStage.INITIAL_COMPROMISE,
        detection_source: DetectionSource = DetectionSource.EDR,
        threat_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> APTRecord:
        record = APTRecord(
            campaign_name=campaign_name,
            apt_indicator=apt_indicator,
            apt_stage=apt_stage,
            detection_source=detection_source,
            threat_score=threat_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "apt_detection_engine.detection_recorded",
            record_id=record.id,
            campaign_name=campaign_name,
            apt_indicator=apt_indicator.value,
            apt_stage=apt_stage.value,
        )
        return record

    def get_detection(self, record_id: str) -> APTRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_detections(
        self,
        apt_indicator: APTIndicator | None = None,
        apt_stage: APTStage | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[APTRecord]:
        results = list(self._records)
        if apt_indicator is not None:
            results = [r for r in results if r.apt_indicator == apt_indicator]
        if apt_stage is not None:
            results = [r for r in results if r.apt_stage == apt_stage]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        campaign_name: str,
        apt_indicator: APTIndicator = APTIndicator.LONG_DWELL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> APTAnalysis:
        analysis = APTAnalysis(
            campaign_name=campaign_name,
            apt_indicator=apt_indicator,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "apt_detection_engine.analysis_added",
            campaign_name=campaign_name,
            apt_indicator=apt_indicator.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_threat_distribution(self) -> dict[str, Any]:
        """Group by apt_indicator; return count and avg threat_score."""
        ind_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.apt_indicator.value
            ind_data.setdefault(key, []).append(r.threat_score)
        result: dict[str, Any] = {}
        for ind, scores in ind_data.items():
            result[ind] = {
                "count": len(scores),
                "avg_threat_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_threat_detections(self) -> list[dict[str, Any]]:
        """Return records where threat_score > apt_threat_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.threat_score > self._apt_threat_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "campaign_name": r.campaign_name,
                        "apt_indicator": r.apt_indicator.value,
                        "threat_score": r.threat_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["threat_score"], reverse=True)

    def rank_by_threat_score(self) -> list[dict[str, Any]]:
        """Group by service, avg threat_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.threat_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_threat_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_threat_score"], reverse=True)
        return results

    def detect_threat_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> APTReport:
        by_indicator: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_indicator[r.apt_indicator.value] = by_indicator.get(r.apt_indicator.value, 0) + 1
            by_stage[r.apt_stage.value] = by_stage.get(r.apt_stage.value, 0) + 1
            by_source[r.detection_source.value] = by_source.get(r.detection_source.value, 0) + 1
        high_threat_count = sum(
            1 for r in self._records if r.threat_score > self._apt_threat_threshold
        )
        scores = [r.threat_score for r in self._records]
        avg_threat_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_threat_detections()
        top_high_threat = [o["campaign_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_threat_count > 0:
            recs.append(
                f"{high_threat_count} detection(s) above threat threshold "
                f"({self._apt_threat_threshold})"
            )
        if self._records and avg_threat_score > self._apt_threat_threshold:
            recs.append(
                f"Avg threat score {avg_threat_score} above threshold "
                f"({self._apt_threat_threshold})"
            )
        if not recs:
            recs.append("APT detection posture is healthy")
        return APTReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_threat_count=high_threat_count,
            avg_threat_score=avg_threat_score,
            by_indicator=by_indicator,
            by_stage=by_stage,
            by_source=by_source,
            top_high_threat=top_high_threat,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("apt_detection_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        indicator_dist: dict[str, int] = {}
        for r in self._records:
            key = r.apt_indicator.value
            indicator_dist[key] = indicator_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "apt_threat_threshold": self._apt_threat_threshold,
            "indicator_distribution": indicator_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
