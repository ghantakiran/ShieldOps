"""Encryption Key Rotation Monitor — monitor encryption key rotation status and compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class KeyType(StrEnum):
    AES_256 = "aes_256"
    RSA_4096 = "rsa_4096"
    ECDSA = "ecdsa"
    HMAC = "hmac"
    KMS_MANAGED = "kms_managed"


class RotationState(StrEnum):
    CURRENT = "current"
    DUE = "due"
    OVERDUE = "overdue"
    ROTATING = "rotating"
    COMPROMISED = "compromised"


class KeyUsage(StrEnum):
    ENCRYPTION = "encryption"
    SIGNING = "signing"
    AUTHENTICATION = "authentication"
    KEY_WRAPPING = "key_wrapping"
    TLS = "tls"


# --- Models ---


class KeyRotationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rotation_id: str = ""
    key_type: KeyType = KeyType.AES_256
    rotation_state: RotationState = RotationState.CURRENT
    key_usage: KeyUsage = KeyUsage.ENCRYPTION
    rotation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class KeyRotationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rotation_id: str = ""
    key_type: KeyType = KeyType.AES_256
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KeyRotationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_rotation_score: float = 0.0
    by_key_type: dict[str, int] = Field(default_factory=dict)
    by_state: dict[str, int] = Field(default_factory=dict)
    by_usage: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class EncryptionKeyRotationMonitor:
    """Monitor encryption key rotation status and ensure compliance with rotation policies."""

    def __init__(
        self,
        max_records: int = 200000,
        rotation_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._rotation_threshold = rotation_threshold
        self._records: list[KeyRotationRecord] = []
        self._analyses: list[KeyRotationAnalysis] = []
        logger.info(
            "encryption_key_rotation_monitor.initialized",
            max_records=max_records,
            rotation_threshold=rotation_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_rotation(
        self,
        rotation_id: str,
        key_type: KeyType = KeyType.AES_256,
        rotation_state: RotationState = RotationState.CURRENT,
        key_usage: KeyUsage = KeyUsage.ENCRYPTION,
        rotation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> KeyRotationRecord:
        record = KeyRotationRecord(
            rotation_id=rotation_id,
            key_type=key_type,
            rotation_state=rotation_state,
            key_usage=key_usage,
            rotation_score=rotation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "encryption_key_rotation_monitor.rotation_recorded",
            record_id=record.id,
            rotation_id=rotation_id,
            key_type=key_type.value,
            rotation_state=rotation_state.value,
        )
        return record

    def get_rotation(self, record_id: str) -> KeyRotationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rotations(
        self,
        key_type: KeyType | None = None,
        rotation_state: RotationState | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[KeyRotationRecord]:
        results = list(self._records)
        if key_type is not None:
            results = [r for r in results if r.key_type == key_type]
        if rotation_state is not None:
            results = [r for r in results if r.rotation_state == rotation_state]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        rotation_id: str,
        key_type: KeyType = KeyType.AES_256,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> KeyRotationAnalysis:
        analysis = KeyRotationAnalysis(
            rotation_id=rotation_id,
            key_type=key_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "encryption_key_rotation_monitor.analysis_added",
            rotation_id=rotation_id,
            key_type=key_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_key_type_distribution(self) -> dict[str, Any]:
        key_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.key_type.value
            key_data.setdefault(key, []).append(r.rotation_score)
        result: dict[str, Any] = {}
        for ktype, scores in key_data.items():
            result[ktype] = {
                "count": len(scores),
                "avg_rotation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_rotation_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.rotation_score < self._rotation_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "rotation_id": r.rotation_id,
                        "key_type": r.key_type.value,
                        "rotation_score": r.rotation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["rotation_score"])

    def rank_by_rotation(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.rotation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_rotation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_rotation_score"])
        return results

    def detect_rotation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> KeyRotationReport:
        by_key_type: dict[str, int] = {}
        by_state: dict[str, int] = {}
        by_usage: dict[str, int] = {}
        for r in self._records:
            by_key_type[r.key_type.value] = by_key_type.get(r.key_type.value, 0) + 1
            by_state[r.rotation_state.value] = by_state.get(r.rotation_state.value, 0) + 1
            by_usage[r.key_usage.value] = by_usage.get(r.key_usage.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.rotation_score < self._rotation_threshold)
        scores = [r.rotation_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_rotation_gaps()
        top_gaps = [o["rotation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} key(s) below rotation threshold ({self._rotation_threshold})")
        if self._records and avg_score < self._rotation_threshold:
            recs.append(
                f"Avg rotation score {avg_score} below threshold ({self._rotation_threshold})"
            )
        if not recs:
            recs.append("Encryption key rotation is healthy")
        return KeyRotationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_rotation_score=avg_score,
            by_key_type=by_key_type,
            by_state=by_state,
            by_usage=by_usage,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("encryption_key_rotation_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        key_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.key_type.value
            key_type_dist[key] = key_type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "rotation_threshold": self._rotation_threshold,
            "key_type_distribution": key_type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
