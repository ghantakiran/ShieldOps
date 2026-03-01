"""Compliance Evidence Chain Tracker — track evidence chain integrity, detect broken chains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChainStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BROKEN = "broken"
    EXPIRED = "expired"
    PENDING = "pending"


class EvidenceLink(StrEnum):
    CONTROL_TO_EVIDENCE = "control_to_evidence"
    EVIDENCE_TO_ARTIFACT = "evidence_to_artifact"
    ARTIFACT_TO_ATTESTATION = "artifact_to_attestation"
    ATTESTATION_TO_REPORT = "attestation_to_report"
    REPORT_TO_AUDIT = "report_to_audit"


class ChainRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


# --- Models ---


class EvidenceChainRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    chain_status: ChainStatus = ChainStatus.PENDING
    evidence_link: EvidenceLink = EvidenceLink.CONTROL_TO_EVIDENCE
    chain_risk: ChainRisk = ChainRisk.NONE
    integrity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ChainValidation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    chain_status: ChainStatus = ChainStatus.PENDING
    validation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceEvidenceChainReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_validations: int = 0
    broken_chains: int = 0
    avg_integrity_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_link: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_broken: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceEvidenceChainTracker:
    """Track evidence chain integrity, detect broken chains."""

    def __init__(
        self,
        max_records: int = 200000,
        max_broken_chain_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_broken_chain_pct = max_broken_chain_pct
        self._records: list[EvidenceChainRecord] = []
        self._validations: list[ChainValidation] = []
        logger.info(
            "compliance_evidence_chain.initialized",
            max_records=max_records,
            max_broken_chain_pct=max_broken_chain_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_chain(
        self,
        chain_id: str,
        chain_status: ChainStatus = ChainStatus.PENDING,
        evidence_link: EvidenceLink = EvidenceLink.CONTROL_TO_EVIDENCE,
        chain_risk: ChainRisk = ChainRisk.NONE,
        integrity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EvidenceChainRecord:
        record = EvidenceChainRecord(
            chain_id=chain_id,
            chain_status=chain_status,
            evidence_link=evidence_link,
            chain_risk=chain_risk,
            integrity_score=integrity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_evidence_chain.chain_recorded",
            record_id=record.id,
            chain_id=chain_id,
            chain_status=chain_status.value,
            chain_risk=chain_risk.value,
        )
        return record

    def get_chain(self, record_id: str) -> EvidenceChainRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_chains(
        self,
        status: ChainStatus | None = None,
        link: EvidenceLink | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EvidenceChainRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.chain_status == status]
        if link is not None:
            results = [r for r in results if r.evidence_link == link]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_validation(
        self,
        chain_id: str,
        chain_status: ChainStatus = ChainStatus.PENDING,
        validation_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ChainValidation:
        validation = ChainValidation(
            chain_id=chain_id,
            chain_status=chain_status,
            validation_score=validation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._validations.append(validation)
        if len(self._validations) > self._max_records:
            self._validations = self._validations[-self._max_records :]
        logger.info(
            "compliance_evidence_chain.validation_added",
            chain_id=chain_id,
            chain_status=chain_status.value,
            validation_score=validation_score,
        )
        return validation

    # -- domain operations --------------------------------------------------

    def analyze_chain_integrity(self) -> dict[str, Any]:
        """Group by chain_status; return count and avg integrity score."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.chain_status.value
            status_data.setdefault(key, []).append(r.integrity_score)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_integrity": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_broken_chains(self) -> list[dict[str, Any]]:
        """Return records where chain_status is BROKEN."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.chain_status == ChainStatus.BROKEN:
                results.append(
                    {
                        "record_id": r.id,
                        "chain_id": r.chain_id,
                        "evidence_link": r.evidence_link.value,
                        "chain_risk": r.chain_risk.value,
                        "integrity_score": r.integrity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_integrity(self) -> list[dict[str, Any]]:
        """Group by chain_id, avg integrity_score, sort ascending."""
        chain_scores: dict[str, list[float]] = {}
        for r in self._records:
            chain_scores.setdefault(r.chain_id, []).append(r.integrity_score)
        results: list[dict[str, Any]] = []
        for chain_id, scores in chain_scores.items():
            results.append(
                {
                    "chain_id": chain_id,
                    "avg_integrity": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_integrity"])
        return results

    def detect_chain_trends(self) -> dict[str, Any]:
        """Split-half comparison on validation_score; delta threshold 5.0."""
        if len(self._validations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [v.validation_score for v in self._validations]
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

    def generate_report(self) -> ComplianceEvidenceChainReport:
        by_status: dict[str, int] = {}
        by_link: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_status[r.chain_status.value] = by_status.get(r.chain_status.value, 0) + 1
            by_link[r.evidence_link.value] = by_link.get(r.evidence_link.value, 0) + 1
            by_risk[r.chain_risk.value] = by_risk.get(r.chain_risk.value, 0) + 1
        broken_chains = sum(1 for r in self._records if r.chain_status == ChainStatus.BROKEN)
        scores = [r.integrity_score for r in self._records]
        avg_integrity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        broken_list = self.identify_broken_chains()
        top_broken = [b["chain_id"] for b in broken_list[:5]]
        recs: list[str] = []
        if self._records:
            broken_pct = round(broken_chains / len(self._records) * 100, 2)
            if broken_pct > self._max_broken_chain_pct:
                recs.append(
                    f"Broken chain rate {broken_pct}%"
                    f" exceeds threshold ({self._max_broken_chain_pct}%)"
                )
        if broken_chains > 0:
            recs.append(f"{broken_chains} broken chain(s) — repair evidence linkage")
        if not recs:
            recs.append("Evidence chain integrity is healthy")
        return ComplianceEvidenceChainReport(
            total_records=len(self._records),
            total_validations=len(self._validations),
            broken_chains=broken_chains,
            avg_integrity_score=avg_integrity_score,
            by_status=by_status,
            by_link=by_link,
            by_risk=by_risk,
            top_broken=top_broken,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._validations.clear()
        logger.info("compliance_evidence_chain.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.chain_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_validations": len(self._validations),
            "max_broken_chain_pct": self._max_broken_chain_pct,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
