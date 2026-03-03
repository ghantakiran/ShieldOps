"""Credential Abuse Detector — detect credential abuse patterns and brute force attacks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AbuseType(StrEnum):
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"  # noqa: S105
    PASSWORD_SPRAY = "password_spray"  # noqa: S105
    TOKEN_THEFT = "token_theft"  # noqa: S105
    SESSION_HIJACK = "session_hijack"


class DetectionSource(StrEnum):
    AUTHENTICATION_LOG = "authentication_log"
    NETWORK_TRAFFIC = "network_traffic"
    ENDPOINT_TELEMETRY = "endpoint_telemetry"
    CLOUD_AUDIT = "cloud_audit"
    IDENTITY_PROVIDER = "identity_provider"


class AbuseConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SUSPECTED = "suspected"


# --- Models ---


class AbuseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_name: str = ""
    abuse_type: AbuseType = AbuseType.BRUTE_FORCE
    detection_source: DetectionSource = DetectionSource.AUTHENTICATION_LOG
    abuse_confidence: AbuseConfidence = AbuseConfidence.SUSPECTED
    abuse_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AbuseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_name: str = ""
    abuse_type: AbuseType = AbuseType.BRUTE_FORCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CredentialAbuseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_abuse_score: float = 0.0
    by_abuse_type: dict[str, int] = Field(default_factory=dict)
    by_detection_source: dict[str, int] = Field(default_factory=dict)
    by_abuse_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CredentialAbuseDetector:
    """Detect credential abuse patterns including brute force, stuffing, and token theft."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AbuseRecord] = []
        self._analyses: list[AbuseAnalysis] = []
        logger.info(
            "credential_abuse_detector.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_abuse(
        self,
        credential_name: str,
        abuse_type: AbuseType = AbuseType.BRUTE_FORCE,
        detection_source: DetectionSource = DetectionSource.AUTHENTICATION_LOG,
        abuse_confidence: AbuseConfidence = AbuseConfidence.SUSPECTED,
        abuse_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AbuseRecord:
        record = AbuseRecord(
            credential_name=credential_name,
            abuse_type=abuse_type,
            detection_source=detection_source,
            abuse_confidence=abuse_confidence,
            abuse_score=abuse_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "credential_abuse_detector.abuse_recorded",
            record_id=record.id,
            credential_name=credential_name,
            abuse_type=abuse_type.value,
            detection_source=detection_source.value,
        )
        return record

    def get_record(self, record_id: str) -> AbuseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        abuse_type: AbuseType | None = None,
        detection_source: DetectionSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AbuseRecord]:
        results = list(self._records)
        if abuse_type is not None:
            results = [r for r in results if r.abuse_type == abuse_type]
        if detection_source is not None:
            results = [r for r in results if r.detection_source == detection_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        credential_name: str,
        abuse_type: AbuseType = AbuseType.BRUTE_FORCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AbuseAnalysis:
        analysis = AbuseAnalysis(
            credential_name=credential_name,
            abuse_type=abuse_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "credential_abuse_detector.analysis_added",
            credential_name=credential_name,
            abuse_type=abuse_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by abuse_type; return count and avg abuse_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.abuse_type.value
            type_data.setdefault(key, []).append(r.abuse_score)
        result: dict[str, Any] = {}
        for atype, scores in type_data.items():
            result[atype] = {
                "count": len(scores),
                "avg_abuse_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where abuse_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.abuse_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "credential_name": r.credential_name,
                        "abuse_type": r.abuse_type.value,
                        "abuse_score": r.abuse_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["abuse_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg abuse_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.abuse_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_abuse_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_abuse_score"])
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

    def generate_report(self) -> CredentialAbuseReport:
        by_abuse_type: dict[str, int] = {}
        by_detection_source: dict[str, int] = {}
        by_abuse_confidence: dict[str, int] = {}
        for r in self._records:
            by_abuse_type[r.abuse_type.value] = by_abuse_type.get(r.abuse_type.value, 0) + 1
            by_detection_source[r.detection_source.value] = (
                by_detection_source.get(r.detection_source.value, 0) + 1
            )
            by_abuse_confidence[r.abuse_confidence.value] = (
                by_abuse_confidence.get(r.abuse_confidence.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.abuse_score < self._threshold)
        scores = [r.abuse_score for r in self._records]
        avg_abuse_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["credential_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} credential(s) below abuse threshold ({self._threshold})")
        if self._records and avg_abuse_score < self._threshold:
            recs.append(f"Avg abuse score {avg_abuse_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Credential abuse detection is healthy")
        return CredentialAbuseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_abuse_score=avg_abuse_score,
            by_abuse_type=by_abuse_type,
            by_detection_source=by_detection_source,
            by_abuse_confidence=by_abuse_confidence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("credential_abuse_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        abuse_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.abuse_type.value
            abuse_type_dist[key] = abuse_type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "abuse_type_distribution": abuse_type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
