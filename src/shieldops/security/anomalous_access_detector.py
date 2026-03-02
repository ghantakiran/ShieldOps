"""Anomalous Access Detector — impossible travel, lateral movement indicators."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AccessType(StrEnum):
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    UNUSUAL_HOURS = "unusual_hours"
    NEW_LOCATION = "new_location"
    PRIVILEGE_ABUSE = "privilege_abuse"
    LATERAL_MOVEMENT = "lateral_movement"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class DetectionMethod(StrEnum):
    RULE_BASED = "rule_based"
    ML_BASED = "ml_based"
    BEHAVIORAL = "behavioral"
    STATISTICAL = "statistical"
    HYBRID = "hybrid"


# --- Models ---


class AccessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    access_name: str = ""
    access_type: AccessType = AccessType.IMPOSSIBLE_TRAVEL
    risk_level: RiskLevel = RiskLevel.CRITICAL
    detection_method: DetectionMethod = DetectionMethod.RULE_BASED
    anomaly_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    access_name: str = ""
    access_type: AccessType = AccessType.IMPOSSIBLE_TRAVEL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_anomaly_count: int = 0
    avg_anomaly_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_high_anomaly: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AnomalousAccessDetector:
    """Detect impossible travel, lateral movement, and anomalous access patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        anomaly_score_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._anomaly_score_threshold = anomaly_score_threshold
        self._records: list[AccessRecord] = []
        self._analyses: list[AccessAnalysis] = []
        logger.info(
            "anomalous_access_detector.initialized",
            max_records=max_records,
            anomaly_score_threshold=anomaly_score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_access(
        self,
        access_name: str,
        access_type: AccessType = AccessType.IMPOSSIBLE_TRAVEL,
        risk_level: RiskLevel = RiskLevel.CRITICAL,
        detection_method: DetectionMethod = DetectionMethod.RULE_BASED,
        anomaly_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AccessRecord:
        record = AccessRecord(
            access_name=access_name,
            access_type=access_type,
            risk_level=risk_level,
            detection_method=detection_method,
            anomaly_score=anomaly_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "anomalous_access_detector.access_recorded",
            record_id=record.id,
            access_name=access_name,
            access_type=access_type.value,
            risk_level=risk_level.value,
        )
        return record

    def get_access(self, record_id: str) -> AccessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_accesses(
        self,
        access_type: AccessType | None = None,
        risk_level: RiskLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AccessRecord]:
        results = list(self._records)
        if access_type is not None:
            results = [r for r in results if r.access_type == access_type]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        access_name: str,
        access_type: AccessType = AccessType.IMPOSSIBLE_TRAVEL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AccessAnalysis:
        analysis = AccessAnalysis(
            access_name=access_name,
            access_type=access_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "anomalous_access_detector.analysis_added",
            access_name=access_name,
            access_type=access_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_access_distribution(self) -> dict[str, Any]:
        """Group by access_type; return count and avg anomaly_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.access_type.value
            src_data.setdefault(key, []).append(r.anomaly_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_anomaly_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_anomaly_accesses(self) -> list[dict[str, Any]]:
        """Return records where anomaly_score > anomaly_score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.anomaly_score > self._anomaly_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "access_name": r.access_name,
                        "access_type": r.access_type.value,
                        "anomaly_score": r.anomaly_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["anomaly_score"], reverse=True)

    def rank_by_anomaly(self) -> list[dict[str, Any]]:
        """Group by service, avg anomaly_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.anomaly_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_anomaly_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_anomaly_score"], reverse=True)
        return results

    def detect_access_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AccessReport:
        by_type: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_type[r.access_type.value] = by_type.get(r.access_type.value, 0) + 1
            by_risk[r.risk_level.value] = by_risk.get(r.risk_level.value, 0) + 1
            by_method[r.detection_method.value] = by_method.get(r.detection_method.value, 0) + 1
        high_anomaly_count = sum(
            1 for r in self._records if r.anomaly_score > self._anomaly_score_threshold
        )
        scores = [r.anomaly_score for r in self._records]
        avg_anomaly_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_anomaly_accesses()
        top_high_anomaly = [o["access_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_anomaly_count > 0:
            recs.append(
                f"{high_anomaly_count} access(es) above anomaly score threshold "
                f"({self._anomaly_score_threshold})"
            )
        if self._records and avg_anomaly_score > self._anomaly_score_threshold:
            recs.append(
                f"Avg anomaly score {avg_anomaly_score} above threshold "
                f"({self._anomaly_score_threshold})"
            )
        if not recs:
            recs.append("Anomalous access detection is healthy")
        return AccessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_anomaly_count=high_anomaly_count,
            avg_anomaly_score=avg_anomaly_score,
            by_type=by_type,
            by_risk=by_risk,
            by_method=by_method,
            top_high_anomaly=top_high_anomaly,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("anomalous_access_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.access_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "anomaly_score_threshold": self._anomaly_score_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
