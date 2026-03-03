"""Supply Chain Integrity Verifier — verify end-to-end supply chain integrity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IntegrityLevel(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    COMPROMISED = "compromised"
    UNKNOWN = "unknown"


class VerificationStage(StrEnum):
    SOURCE = "source"
    BUILD = "build"
    PACKAGE = "package"
    DEPLOY = "deploy"
    RUNTIME = "runtime"


class TrustModel(StrEnum):
    SLSA = "slsa"
    SIGSTORE = "sigstore"
    NOTARY = "notary"
    CUSTOM = "custom"
    NONE = "none"


# --- Models ---


class IntegrityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_name: str = ""
    integrity_level: IntegrityLevel = IntegrityLevel.VERIFIED
    verification_stage: VerificationStage = VerificationStage.BUILD
    trust_model: TrustModel = TrustModel.SLSA
    integrity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IntegrityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_name: str = ""
    integrity_level: IntegrityLevel = IntegrityLevel.VERIFIED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SupplyChainIntegrityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_integrity_score: float = 0.0
    by_integrity: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_trust_model: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SupplyChainIntegrityVerifier:
    """Verify supply chain integrity across source, build, package, deploy, and runtime."""

    def __init__(
        self,
        max_records: int = 200000,
        integrity_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._integrity_gap_threshold = integrity_gap_threshold
        self._records: list[IntegrityRecord] = []
        self._analyses: list[IntegrityAnalysis] = []
        logger.info(
            "supply_chain_integrity_verifier.initialized",
            max_records=max_records,
            integrity_gap_threshold=integrity_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_integrity(
        self,
        component_name: str,
        integrity_level: IntegrityLevel = IntegrityLevel.VERIFIED,
        verification_stage: VerificationStage = VerificationStage.BUILD,
        trust_model: TrustModel = TrustModel.SLSA,
        integrity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> IntegrityRecord:
        record = IntegrityRecord(
            component_name=component_name,
            integrity_level=integrity_level,
            verification_stage=verification_stage,
            trust_model=trust_model,
            integrity_score=integrity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "supply_chain_integrity_verifier.integrity_recorded",
            record_id=record.id,
            component_name=component_name,
            integrity_level=integrity_level.value,
            verification_stage=verification_stage.value,
        )
        return record

    def get_integrity(self, record_id: str) -> IntegrityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_integrity_records(
        self,
        integrity_level: IntegrityLevel | None = None,
        verification_stage: VerificationStage | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IntegrityRecord]:
        results = list(self._records)
        if integrity_level is not None:
            results = [r for r in results if r.integrity_level == integrity_level]
        if verification_stage is not None:
            results = [r for r in results if r.verification_stage == verification_stage]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        component_name: str,
        integrity_level: IntegrityLevel = IntegrityLevel.VERIFIED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> IntegrityAnalysis:
        analysis = IntegrityAnalysis(
            component_name=component_name,
            integrity_level=integrity_level,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "supply_chain_integrity_verifier.analysis_added",
            component_name=component_name,
            integrity_level=integrity_level.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_integrity_distribution(self) -> dict[str, Any]:
        """Group by integrity_level; return count and avg integrity_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.integrity_level.value
            level_data.setdefault(key, []).append(r.integrity_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_integrity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_integrity_gaps(self) -> list[dict[str, Any]]:
        """Return records where integrity_score < integrity_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.integrity_score < self._integrity_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "component_name": r.component_name,
                        "integrity_level": r.integrity_level.value,
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

    def generate_report(self) -> SupplyChainIntegrityReport:
        by_integrity: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_trust_model: dict[str, int] = {}
        for r in self._records:
            by_integrity[r.integrity_level.value] = by_integrity.get(r.integrity_level.value, 0) + 1
            by_stage[r.verification_stage.value] = by_stage.get(r.verification_stage.value, 0) + 1
            by_trust_model[r.trust_model.value] = by_trust_model.get(r.trust_model.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.integrity_score < self._integrity_gap_threshold
        )
        scores = [r.integrity_score for r in self._records]
        avg_integrity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_integrity_gaps()
        top_gaps = [o["component_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} component(s) below integrity threshold "
                f"({self._integrity_gap_threshold})"
            )
        if self._records and avg_integrity_score < self._integrity_gap_threshold:
            recs.append(
                f"Avg integrity score {avg_integrity_score} below threshold "
                f"({self._integrity_gap_threshold})"
            )
        if not recs:
            recs.append("Supply chain integrity is healthy")
        return SupplyChainIntegrityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_integrity_score=avg_integrity_score,
            by_integrity=by_integrity,
            by_stage=by_stage,
            by_trust_model=by_trust_model,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("supply_chain_integrity_verifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.integrity_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "integrity_gap_threshold": self._integrity_gap_threshold,
            "integrity_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
