"""Credential Abuse Risk Scorer Engine —
score credential abuse risk,
detect abuse patterns, rank credentials by risk."""

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
    CREDENTIAL_STUFFING = "credential_stuffing"
    TOKEN_THEFT = "token_theft"  # noqa: S105
    SESSION_HIJACK = "session_hijack"


class DetectionSource(StrEnum):
    AUTH_LOG = "auth_log"
    NETWORK = "network"
    ENDPOINT = "endpoint"
    IDENTITY = "identity"


class AbuseConfidence(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"


# --- Models ---


class CredentialAbuseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_id: str = ""
    user_id: str = ""
    abuse_type: AbuseType = AbuseType.BRUTE_FORCE
    detection_source: DetectionSource = DetectionSource.AUTH_LOG
    confidence: AbuseConfidence = AbuseConfidence.POSSIBLE
    risk_score: float = 0.0
    attempt_count: int = 0
    source_ip: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CredentialAbuseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_id: str = ""
    abuse_type: AbuseType = AbuseType.BRUTE_FORCE
    composite_risk: float = 0.0
    abuse_confirmed: bool = False
    confidence: AbuseConfidence = AbuseConfidence.POSSIBLE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CredentialAbuseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_abuse_type: dict[str, int] = Field(default_factory=dict)
    by_detection_source: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    compromised_credentials: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CredentialAbuseRiskScorerEngine:
    """Score credential abuse risk, detect abuse patterns,
    and rank credentials by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CredentialAbuseRecord] = []
        self._analyses: dict[str, CredentialAbuseAnalysis] = {}
        logger.info(
            "credential_abuse_risk_scorer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        credential_id: str = "",
        user_id: str = "",
        abuse_type: AbuseType = AbuseType.BRUTE_FORCE,
        detection_source: DetectionSource = DetectionSource.AUTH_LOG,
        confidence: AbuseConfidence = AbuseConfidence.POSSIBLE,
        risk_score: float = 0.0,
        attempt_count: int = 0,
        source_ip: str = "",
        description: str = "",
    ) -> CredentialAbuseRecord:
        record = CredentialAbuseRecord(
            credential_id=credential_id,
            user_id=user_id,
            abuse_type=abuse_type,
            detection_source=detection_source,
            confidence=confidence,
            risk_score=risk_score,
            attempt_count=attempt_count,
            source_ip=source_ip,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "credential_abuse_risk.record_added",
            record_id=record.id,
            credential_id=credential_id,
        )
        return record

    def process(self, key: str) -> CredentialAbuseAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        conf_weights = {"confirmed": 4, "probable": 3, "possible": 2, "unlikely": 1}
        w = conf_weights.get(rec.confidence.value, 1)
        composite = round(w * rec.risk_score * (1 + rec.attempt_count * 0.01), 2)
        confirmed = rec.confidence == AbuseConfidence.CONFIRMED
        analysis = CredentialAbuseAnalysis(
            credential_id=rec.credential_id,
            abuse_type=rec.abuse_type,
            composite_risk=composite,
            abuse_confirmed=confirmed,
            confidence=rec.confidence,
            description=(
                f"Credential {rec.credential_id} {rec.abuse_type.value} "
                f"attempts={rec.attempt_count}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CredentialAbuseReport:
        by_at: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        by_cf: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.abuse_type.value
            by_at[k] = by_at.get(k, 0) + 1
            k2 = r.detection_source.value
            by_ds[k2] = by_ds.get(k2, 0) + 1
            k3 = r.confidence.value
            by_cf[k3] = by_cf.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        compromised = list(
            {
                r.credential_id
                for r in self._records
                if r.confidence in (AbuseConfidence.CONFIRMED, AbuseConfidence.PROBABLE)
            }
        )[:10]
        recs: list[str] = []
        if compromised:
            recs.append(f"{len(compromised)} credentials with confirmed/probable abuse")
        if not recs:
            recs.append("No confirmed credential abuse detected")
        return CredentialAbuseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_abuse_type=by_at,
            by_detection_source=by_ds,
            by_confidence=by_cf,
            compromised_credentials=compromised,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        at_dist: dict[str, int] = {}
        for r in self._records:
            k = r.abuse_type.value
            at_dist[k] = at_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "abuse_type_distribution": at_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("credential_abuse_risk_scorer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_credential_abuse_risk(self) -> list[dict[str, Any]]:
        """Score aggregated abuse risk per credential."""
        cred_data: dict[str, list[CredentialAbuseRecord]] = {}
        for r in self._records:
            cred_data.setdefault(r.credential_id, []).append(r)
        conf_weights = {"confirmed": 4, "probable": 3, "possible": 2, "unlikely": 1}
        results: list[dict[str, Any]] = []
        for cid, recs in cred_data.items():
            total_risk = sum(
                conf_weights.get(rec.confidence.value, 1) * rec.risk_score for rec in recs
            )
            total_attempts = sum(rec.attempt_count for rec in recs)
            abuse_types = list({rec.abuse_type.value for rec in recs})
            results.append(
                {
                    "credential_id": cid,
                    "composite_risk": round(total_risk, 2),
                    "total_attempts": total_attempts,
                    "abuse_types": abuse_types,
                    "event_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        return results

    def detect_abuse_patterns(self) -> list[dict[str, Any]]:
        """Detect confirmed credential abuse patterns."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            pat_key = f"{r.abuse_type.value}:{r.source_ip}"
            if (
                r.confidence in (AbuseConfidence.CONFIRMED, AbuseConfidence.PROBABLE)
                and pat_key not in seen
            ):
                seen.add(pat_key)
                results.append(
                    {
                        "abuse_type": r.abuse_type.value,
                        "source_ip": r.source_ip,
                        "credential_id": r.credential_id,
                        "confidence": r.confidence.value,
                        "risk_score": r.risk_score,
                        "attempt_count": r.attempt_count,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_credentials_by_risk(self) -> list[dict[str, Any]]:
        """Rank credentials by total abuse risk score."""
        conf_weights = {"confirmed": 4, "probable": 3, "possible": 2, "unlikely": 1}
        cred_scores: dict[str, float] = {}
        for r in self._records:
            w = conf_weights.get(r.confidence.value, 1)
            cred_scores[r.credential_id] = cred_scores.get(r.credential_id, 0.0) + (
                w * r.risk_score
            )
        results: list[dict[str, Any]] = []
        for cid, score in cred_scores.items():
            results.append(
                {
                    "credential_id": cid,
                    "total_risk_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_risk_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
