"""Build Artifact Verifier — verify build artifact integrity and provenance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ArtifactType(StrEnum):
    CONTAINER = "container"
    BINARY = "binary"
    PACKAGE = "package"
    LIBRARY = "library"
    CONFIG = "config"


class VerificationMethod(StrEnum):
    SIGNATURE = "signature"
    CHECKSUM = "checksum"
    PROVENANCE = "provenance"
    ATTESTATION = "attestation"
    POLICY = "policy"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


# --- Models ---


class ArtifactVerification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    artifact_type: ArtifactType = ArtifactType.CONTAINER
    verification_method: VerificationMethod = VerificationMethod.SIGNATURE
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    verification_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VerificationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    artifact_type: ArtifactType = ArtifactType.CONTAINER
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ArtifactVerificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_verification_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BuildArtifactVerifier:
    """Verify build artifacts through signatures, checksums, provenance, and policy."""

    def __init__(
        self,
        max_records: int = 200000,
        verification_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._verification_gap_threshold = verification_gap_threshold
        self._records: list[ArtifactVerification] = []
        self._analyses: list[VerificationAnalysis] = []
        logger.info(
            "build_artifact_verifier.initialized",
            max_records=max_records,
            verification_gap_threshold=verification_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_verification(
        self,
        artifact_name: str,
        artifact_type: ArtifactType = ArtifactType.CONTAINER,
        verification_method: VerificationMethod = VerificationMethod.SIGNATURE,
        verification_status: VerificationStatus = VerificationStatus.VERIFIED,
        verification_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ArtifactVerification:
        record = ArtifactVerification(
            artifact_name=artifact_name,
            artifact_type=artifact_type,
            verification_method=verification_method,
            verification_status=verification_status,
            verification_score=verification_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "build_artifact_verifier.verification_recorded",
            record_id=record.id,
            artifact_name=artifact_name,
            artifact_type=artifact_type.value,
            verification_status=verification_status.value,
        )
        return record

    def get_verification(self, record_id: str) -> ArtifactVerification | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_verifications(
        self,
        artifact_type: ArtifactType | None = None,
        verification_status: VerificationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ArtifactVerification]:
        results = list(self._records)
        if artifact_type is not None:
            results = [r for r in results if r.artifact_type == artifact_type]
        if verification_status is not None:
            results = [r for r in results if r.verification_status == verification_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        artifact_name: str,
        artifact_type: ArtifactType = ArtifactType.CONTAINER,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> VerificationAnalysis:
        analysis = VerificationAnalysis(
            artifact_name=artifact_name,
            artifact_type=artifact_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "build_artifact_verifier.analysis_added",
            artifact_name=artifact_name,
            artifact_type=artifact_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by artifact_type; return count and avg verification_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.artifact_type.value
            type_data.setdefault(key, []).append(r.verification_score)
        result: dict[str, Any] = {}
        for atype, scores in type_data.items():
            result[atype] = {
                "count": len(scores),
                "avg_verification_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_verification_gaps(self) -> list[dict[str, Any]]:
        """Return records where verification_score < verification_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.verification_score < self._verification_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "artifact_name": r.artifact_name,
                        "artifact_type": r.artifact_type.value,
                        "verification_score": r.verification_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["verification_score"])

    def rank_by_verification(self) -> list[dict[str, Any]]:
        """Group by service, avg verification_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.verification_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_verification_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_verification_score"])
        return results

    def detect_verification_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ArtifactVerificationReport:
        by_type: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.artifact_type.value] = by_type.get(r.artifact_type.value, 0) + 1
            by_method[r.verification_method.value] = (
                by_method.get(r.verification_method.value, 0) + 1
            )
            by_status[r.verification_status.value] = (
                by_status.get(r.verification_status.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.verification_score < self._verification_gap_threshold
        )
        scores = [r.verification_score for r in self._records]
        avg_verification_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_verification_gaps()
        top_gaps = [o["artifact_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} artifact(s) below verification threshold "
                f"({self._verification_gap_threshold})"
            )
        if self._records and avg_verification_score < self._verification_gap_threshold:
            recs.append(
                f"Avg verification score {avg_verification_score} below threshold "
                f"({self._verification_gap_threshold})"
            )
        if not recs:
            recs.append("Build artifact verification is healthy")
        return ArtifactVerificationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_verification_score=avg_verification_score,
            by_type=by_type,
            by_method=by_method,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("build_artifact_verifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.artifact_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "verification_gap_threshold": self._verification_gap_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
