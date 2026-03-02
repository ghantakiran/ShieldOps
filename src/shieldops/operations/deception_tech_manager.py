"""Deception Tech Manager — manage honeypots/honeytokens, monitor interactions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeceptionType(StrEnum):
    HONEYPOT = "honeypot"
    HONEYTOKEN = "honeytoken"
    HONEYCRED = "honeycred"
    HONEYFILE = "honeyfile"
    DECOY_SERVICE = "decoy_service"


class DeploymentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIGGERED = "triggered"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class InteractionSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BENIGN = "benign"


# --- Models ---


class DeceptionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    deception_type: DeceptionType = DeceptionType.HONEYPOT
    deployment_status: DeploymentStatus = DeploymentStatus.ACTIVE
    interaction_severity: InteractionSeverity = InteractionSeverity.CRITICAL
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DeceptionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    deception_type: DeceptionType = DeceptionType.HONEYPOT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeceptionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_detection_count: int = 0
    avg_detection_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_low_detection: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeceptionTechManager:
    """Manage honeypots/honeytokens, monitor interactions."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[DeceptionRecord] = []
        self._analyses: list[DeceptionAnalysis] = []
        logger.info(
            "deception_tech_manager.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    def record_asset(
        self,
        asset_name: str,
        deception_type: DeceptionType = DeceptionType.HONEYPOT,
        deployment_status: DeploymentStatus = DeploymentStatus.ACTIVE,
        interaction_severity: InteractionSeverity = InteractionSeverity.CRITICAL,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DeceptionRecord:
        record = DeceptionRecord(
            asset_name=asset_name,
            deception_type=deception_type,
            deployment_status=deployment_status,
            interaction_severity=interaction_severity,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deception_tech_manager.asset_recorded",
            record_id=record.id,
            asset_name=asset_name,
            deception_type=deception_type.value,
            deployment_status=deployment_status.value,
        )
        return record

    def get_asset(self, record_id: str) -> DeceptionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assets(
        self,
        deception_type: DeceptionType | None = None,
        deployment_status: DeploymentStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DeceptionRecord]:
        results = list(self._records)
        if deception_type is not None:
            results = [r for r in results if r.deception_type == deception_type]
        if deployment_status is not None:
            results = [r for r in results if r.deployment_status == deployment_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        asset_name: str,
        deception_type: DeceptionType = DeceptionType.HONEYPOT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DeceptionAnalysis:
        analysis = DeceptionAnalysis(
            asset_name=asset_name,
            deception_type=deception_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "deception_tech_manager.analysis_added",
            asset_name=asset_name,
            deception_type=deception_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_deception_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.deception_type.value
            type_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_detection_assets(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "asset_name": r.asset_name,
                        "deception_type": r.deception_type.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {"service": svc, "avg_detection_score": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_deception_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DeceptionReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.deception_type.value] = by_type.get(r.deception_type.value, 0) + 1
            by_status[r.deployment_status.value] = by_status.get(r.deployment_status.value, 0) + 1
            by_severity[r.interaction_severity.value] = (
                by_severity.get(r.interaction_severity.value, 0) + 1
            )
        low_detection_count = sum(
            1 for r in self._records if r.detection_score < self._detection_threshold
        )
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_detection_assets()
        top_low_detection = [o["asset_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_detection_count > 0:
            recs.append(
                f"{low_detection_count} asset(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Deception technology detection capability is healthy")
        return DeceptionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_detection_count=low_detection_count,
            avg_detection_score=avg_detection_score,
            by_type=by_type,
            by_status=by_status,
            by_severity=by_severity,
            top_low_detection=top_low_detection,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("deception_tech_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.deception_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
