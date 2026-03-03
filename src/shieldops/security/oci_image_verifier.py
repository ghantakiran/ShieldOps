"""OCI Image Verifier — verify OCI container image signatures and provenance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VerificationMethod(StrEnum):
    COSIGN = "cosign"
    NOTARY = "notary"
    SIGSTORE = "sigstore"
    DCT = "dct"
    CUSTOM = "custom"


class ImageSource(StrEnum):
    PUBLIC_REGISTRY = "public_registry"
    PRIVATE_REGISTRY = "private_registry"
    BUILD_PIPELINE = "build_pipeline"
    MIRROR = "mirror"
    UNKNOWN = "unknown"


class VerificationResult(StrEnum):
    VERIFIED = "verified"
    UNSIGNED = "unsigned"
    TAMPERED = "tampered"
    EXPIRED = "expired"
    PENDING = "pending"


# --- Models ---


class ImageVerificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    verification_id: str = ""
    verification_method: VerificationMethod = VerificationMethod.COSIGN
    image_source: ImageSource = ImageSource.PUBLIC_REGISTRY
    verification_result: VerificationResult = VerificationResult.VERIFIED
    verification_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImageVerificationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    verification_id: str = ""
    verification_method: VerificationMethod = VerificationMethod.COSIGN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OCIImageVerificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_verification_score: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OCIImageVerifier:
    """Verify OCI container image signatures, provenance, and integrity."""

    def __init__(
        self,
        max_records: int = 200000,
        verification_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._verification_gap_threshold = verification_gap_threshold
        self._records: list[ImageVerificationRecord] = []
        self._analyses: list[ImageVerificationAnalysis] = []
        logger.info(
            "oci_image_verifier.initialized",
            max_records=max_records,
            verification_gap_threshold=verification_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_verification(
        self,
        verification_id: str,
        verification_method: VerificationMethod = VerificationMethod.COSIGN,
        image_source: ImageSource = ImageSource.PUBLIC_REGISTRY,
        verification_result: VerificationResult = VerificationResult.VERIFIED,
        verification_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ImageVerificationRecord:
        record = ImageVerificationRecord(
            verification_id=verification_id,
            verification_method=verification_method,
            image_source=image_source,
            verification_result=verification_result,
            verification_score=verification_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "oci_image_verifier.verification_recorded",
            record_id=record.id,
            verification_id=verification_id,
            verification_method=verification_method.value,
            image_source=image_source.value,
        )
        return record

    def get_verification(self, record_id: str) -> ImageVerificationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_verifications(
        self,
        verification_method: VerificationMethod | None = None,
        image_source: ImageSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ImageVerificationRecord]:
        results = list(self._records)
        if verification_method is not None:
            results = [r for r in results if r.verification_method == verification_method]
        if image_source is not None:
            results = [r for r in results if r.image_source == image_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        verification_id: str,
        verification_method: VerificationMethod = VerificationMethod.COSIGN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ImageVerificationAnalysis:
        analysis = ImageVerificationAnalysis(
            verification_id=verification_id,
            verification_method=verification_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "oci_image_verifier.analysis_added",
            verification_id=verification_id,
            verification_method=verification_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_method_distribution(self) -> dict[str, Any]:
        """Group by verification_method; return count and avg verification_score."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.verification_method.value
            method_data.setdefault(key, []).append(r.verification_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
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
                        "verification_id": r.verification_id,
                        "verification_method": r.verification_method.value,
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

    def generate_report(self) -> OCIImageVerificationReport:
        by_method: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_method[r.verification_method.value] = (
                by_method.get(r.verification_method.value, 0) + 1
            )
            by_source[r.image_source.value] = by_source.get(r.image_source.value, 0) + 1
            by_result[r.verification_result.value] = (
                by_result.get(r.verification_result.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.verification_score < self._verification_gap_threshold
        )
        scores = [r.verification_score for r in self._records]
        avg_verification_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_verification_gaps()
        top_gaps = [o["verification_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} verification(s) below threshold ({self._verification_gap_threshold})"
            )
        if self._records and avg_verification_score < self._verification_gap_threshold:
            recs.append(
                f"Avg verification score {avg_verification_score} below threshold "
                f"({self._verification_gap_threshold})"
            )
        if not recs:
            recs.append("OCI image verification is healthy")
        return OCIImageVerificationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_verification_score=avg_verification_score,
            by_method=by_method,
            by_source=by_source,
            by_result=by_result,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("oci_image_verifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.verification_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "verification_gap_threshold": self._verification_gap_threshold,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
