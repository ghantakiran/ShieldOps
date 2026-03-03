"""Credential Stuffing Detector — detect credential stuffing and brute force attacks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackVector(StrEnum):
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_SPRAY = "credential_spray"  # noqa: S105
    DICTIONARY = "dictionary"
    COMBO_LIST = "combo_list"
    RAINBOW_TABLE = "rainbow_table"


class TargetService(StrEnum):
    WEB_LOGIN = "web_login"
    API_ENDPOINT = "api_endpoint"
    SSH = "ssh"
    RDP = "rdp"
    VPN = "vpn"


class DetectionSignal(StrEnum):
    RATE_ANOMALY = "rate_anomaly"
    GEO_IMPOSSIBLE = "geo_impossible"
    KNOWN_PROXY = "known_proxy"
    FAILED_PATTERN = "failed_pattern"
    BOT_BEHAVIOR = "bot_behavior"


# --- Models ---


class StuffingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stuffing_id: str = ""
    attack_vector: AttackVector = AttackVector.BRUTE_FORCE
    target_service: TargetService = TargetService.WEB_LOGIN
    detection_signal: DetectionSignal = DetectionSignal.RATE_ANOMALY
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class StuffingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stuffing_id: str = ""
    attack_vector: AttackVector = AttackVector.BRUTE_FORCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CredentialStuffingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_vector: dict[str, int] = Field(default_factory=dict)
    by_target: dict[str, int] = Field(default_factory=dict)
    by_signal: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CredentialStuffingDetector:
    """Detect credential stuffing and brute force attacks via rate analysis and signal detection."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[StuffingRecord] = []
        self._analyses: list[StuffingAnalysis] = []
        logger.info(
            "credential_stuffing_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_stuffing(
        self,
        stuffing_id: str,
        attack_vector: AttackVector = AttackVector.BRUTE_FORCE,
        target_service: TargetService = TargetService.WEB_LOGIN,
        detection_signal: DetectionSignal = DetectionSignal.RATE_ANOMALY,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> StuffingRecord:
        record = StuffingRecord(
            stuffing_id=stuffing_id,
            attack_vector=attack_vector,
            target_service=target_service,
            detection_signal=detection_signal,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "credential_stuffing_detector.stuffing_recorded",
            record_id=record.id,
            stuffing_id=stuffing_id,
            attack_vector=attack_vector.value,
            target_service=target_service.value,
        )
        return record

    def get_stuffing(self, record_id: str) -> StuffingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_stuffings(
        self,
        attack_vector: AttackVector | None = None,
        target_service: TargetService | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[StuffingRecord]:
        results = list(self._records)
        if attack_vector is not None:
            results = [r for r in results if r.attack_vector == attack_vector]
        if target_service is not None:
            results = [r for r in results if r.target_service == target_service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        stuffing_id: str,
        attack_vector: AttackVector = AttackVector.BRUTE_FORCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> StuffingAnalysis:
        analysis = StuffingAnalysis(
            stuffing_id=stuffing_id,
            attack_vector=attack_vector,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "credential_stuffing_detector.analysis_added",
            stuffing_id=stuffing_id,
            attack_vector=attack_vector.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_vector_distribution(self) -> dict[str, Any]:
        """Group by attack_vector; return count and avg detection_score."""
        vector_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.attack_vector.value
            vector_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for vector, scores in vector_data.items():
            result[vector] = {
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
                        "stuffing_id": r.stuffing_id,
                        "attack_vector": r.attack_vector.value,
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

    def generate_report(self) -> CredentialStuffingReport:
        by_vector: dict[str, int] = {}
        by_target: dict[str, int] = {}
        by_signal: dict[str, int] = {}
        for r in self._records:
            by_vector[r.attack_vector.value] = by_vector.get(r.attack_vector.value, 0) + 1
            by_target[r.target_service.value] = by_target.get(r.target_service.value, 0) + 1
            by_signal[r.detection_signal.value] = by_signal.get(r.detection_signal.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["stuffing_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} stuffing record(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Credential stuffing detection is healthy")
        return CredentialStuffingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_vector=by_vector,
            by_target=by_target,
            by_signal=by_signal,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("credential_stuffing_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        vector_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attack_vector.value
            vector_dist[key] = vector_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "vector_distribution": vector_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
