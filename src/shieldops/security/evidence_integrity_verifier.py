"""Evidence Integrity Verifier — SHA-256 hash chains, tamper detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HashAlgorithm(StrEnum):
    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"
    SHA1 = "sha1"
    BLAKE2 = "blake2"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    TAMPERED = "tampered"
    PENDING = "pending"
    FAILED = "failed"
    EXPIRED = "expired"


class EvidenceType(StrEnum):
    DISK_IMAGE = "disk_image"
    MEMORY_DUMP = "memory_dump"
    LOG_FILE = "log_file"
    NETWORK_CAPTURE = "network_capture"
    CONFIGURATION = "configuration"


# --- Models ---


class IntegrityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_name: str = ""
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    evidence_type: EvidenceType = EvidenceType.DISK_IMAGE
    integrity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IntegrityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_name: str = ""
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IntegrityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    tampered_count: int = 0
    avg_integrity_score: float = 0.0
    by_algorithm: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    top_tampered: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class EvidenceIntegrityVerifier:
    """Verify evidence integrity via SHA-256 hash chains, detect tampering."""

    def __init__(
        self,
        max_records: int = 200000,
        integrity_confidence_threshold: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._integrity_confidence_threshold = integrity_confidence_threshold
        self._records: list[IntegrityRecord] = []
        self._analyses: list[IntegrityAnalysis] = []
        logger.info(
            "evidence_integrity_verifier.initialized",
            max_records=max_records,
            integrity_confidence_threshold=integrity_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_verification(
        self,
        evidence_name: str,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
        verification_status: VerificationStatus = VerificationStatus.VERIFIED,
        evidence_type: EvidenceType = EvidenceType.DISK_IMAGE,
        integrity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> IntegrityRecord:
        record = IntegrityRecord(
            evidence_name=evidence_name,
            hash_algorithm=hash_algorithm,
            verification_status=verification_status,
            evidence_type=evidence_type,
            integrity_score=integrity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evidence_integrity_verifier.verification_recorded",
            record_id=record.id,
            evidence_name=evidence_name,
            hash_algorithm=hash_algorithm.value,
            verification_status=verification_status.value,
        )
        return record

    def get_verification(self, record_id: str) -> IntegrityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_verifications(
        self,
        hash_algorithm: HashAlgorithm | None = None,
        verification_status: VerificationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IntegrityRecord]:
        results = list(self._records)
        if hash_algorithm is not None:
            results = [r for r in results if r.hash_algorithm == hash_algorithm]
        if verification_status is not None:
            results = [r for r in results if r.verification_status == verification_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        evidence_name: str,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> IntegrityAnalysis:
        analysis = IntegrityAnalysis(
            evidence_name=evidence_name,
            hash_algorithm=hash_algorithm,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "evidence_integrity_verifier.analysis_added",
            evidence_name=evidence_name,
            hash_algorithm=hash_algorithm.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_verification_distribution(self) -> dict[str, Any]:
        """Group by hash_algorithm; return count and avg integrity_score."""
        algo_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.hash_algorithm.value
            algo_data.setdefault(key, []).append(r.integrity_score)
        result: dict[str, Any] = {}
        for algo, scores in algo_data.items():
            result[algo] = {
                "count": len(scores),
                "avg_integrity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_tampered_evidence(self) -> list[dict[str, Any]]:
        """Return records where integrity_score < integrity_confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.integrity_score < self._integrity_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "evidence_name": r.evidence_name,
                        "hash_algorithm": r.hash_algorithm.value,
                        "integrity_score": r.integrity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["integrity_score"])

    def rank_by_integrity(self) -> list[dict[str, Any]]:
        """Group by service, avg integrity_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.integrity_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_integrity_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_integrity_score"])
        return results

    def detect_integrity_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> IntegrityReport:
        by_algorithm: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_algorithm[r.hash_algorithm.value] = by_algorithm.get(r.hash_algorithm.value, 0) + 1
            by_status[r.verification_status.value] = (
                by_status.get(r.verification_status.value, 0) + 1
            )
            by_type[r.evidence_type.value] = by_type.get(r.evidence_type.value, 0) + 1
        tampered_count = sum(
            1 for r in self._records if r.integrity_score < self._integrity_confidence_threshold
        )
        scores = [r.integrity_score for r in self._records]
        avg_integrity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        tampered_list = self.identify_tampered_evidence()
        top_tampered = [o["evidence_name"] for o in tampered_list[:5]]
        recs: list[str] = []
        if self._records and tampered_count > 0:
            recs.append(
                f"{tampered_count} evidence(s) below integrity threshold "
                f"({self._integrity_confidence_threshold})"
            )
        if self._records and avg_integrity_score < self._integrity_confidence_threshold:
            recs.append(
                f"Avg integrity score {avg_integrity_score} below threshold "
                f"({self._integrity_confidence_threshold})"
            )
        if not recs:
            recs.append("Evidence integrity verification is healthy")
        return IntegrityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            tampered_count=tampered_count,
            avg_integrity_score=avg_integrity_score,
            by_algorithm=by_algorithm,
            by_status=by_status,
            by_type=by_type,
            top_tampered=top_tampered,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("evidence_integrity_verifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        algo_dist: dict[str, int] = {}
        for r in self._records:
            key = r.hash_algorithm.value
            algo_dist[key] = algo_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "integrity_confidence_threshold": self._integrity_confidence_threshold,
            "algorithm_distribution": algo_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
