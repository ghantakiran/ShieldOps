"""Evidence Chain Integrity Engine
compute chain integrity score, detect broken evidence
chains, rank evidence by integrity risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IntegrityStatus(StrEnum):
    VERIFIED = "verified"
    SUSPECT = "suspect"
    BROKEN = "broken"
    UNKNOWN = "unknown"


class ChainType(StrEnum):
    COLLECTION = "collection"
    REVIEW = "review"
    APPROVAL = "approval"
    ARCHIVAL = "archival"


class IntegrityRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class EvidenceChainRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    integrity_status: IntegrityStatus = IntegrityStatus.VERIFIED
    chain_type: ChainType = ChainType.COLLECTION
    integrity_risk: IntegrityRisk = IntegrityRisk.LOW
    integrity_score: float = 100.0
    evidence_id: str = ""
    chain_length: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceChainAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    integrity_status: IntegrityStatus = IntegrityStatus.VERIFIED
    computed_score: float = 0.0
    is_broken: bool = False
    risk_level: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceChainReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_integrity_score: float = 0.0
    by_integrity_status: dict[str, int] = Field(default_factory=dict)
    by_chain_type: dict[str, int] = Field(default_factory=dict)
    by_integrity_risk: dict[str, int] = Field(default_factory=dict)
    broken_chains: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EvidenceChainIntegrityEngine:
    """Compute chain integrity score, detect broken
    evidence chains, rank evidence by integrity risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EvidenceChainRecord] = []
        self._analyses: dict[str, EvidenceChainAnalysis] = {}
        logger.info(
            "evidence_chain_integrity_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        chain_id: str = "",
        integrity_status: IntegrityStatus = IntegrityStatus.VERIFIED,
        chain_type: ChainType = ChainType.COLLECTION,
        integrity_risk: IntegrityRisk = IntegrityRisk.LOW,
        integrity_score: float = 100.0,
        evidence_id: str = "",
        chain_length: int = 0,
        description: str = "",
    ) -> EvidenceChainRecord:
        record = EvidenceChainRecord(
            chain_id=chain_id,
            integrity_status=integrity_status,
            chain_type=chain_type,
            integrity_risk=integrity_risk,
            integrity_score=integrity_score,
            evidence_id=evidence_id,
            chain_length=chain_length,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evidence_chain_integrity.record_added",
            record_id=record.id,
            chain_id=chain_id,
        )
        return record

    def process(self, key: str) -> EvidenceChainAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_broken = rec.integrity_status in (
            IntegrityStatus.BROKEN,
            IntegrityStatus.SUSPECT,
        )
        analysis = EvidenceChainAnalysis(
            chain_id=rec.chain_id,
            integrity_status=rec.integrity_status,
            computed_score=round(rec.integrity_score, 2),
            is_broken=is_broken,
            risk_level=rec.integrity_risk.value,
            description=f"Chain {rec.chain_id} integrity {rec.integrity_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EvidenceChainReport:
        by_is: dict[str, int] = {}
        by_ct: dict[str, int] = {}
        by_ir: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.integrity_status.value
            by_is[k] = by_is.get(k, 0) + 1
            k2 = r.chain_type.value
            by_ct[k2] = by_ct.get(k2, 0) + 1
            k3 = r.integrity_risk.value
            by_ir[k3] = by_ir.get(k3, 0) + 1
            scores.append(r.integrity_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        broken = list(
            {
                r.chain_id
                for r in self._records
                if r.integrity_status in (IntegrityStatus.BROKEN, IntegrityStatus.SUSPECT)
            }
        )[:10]
        recs: list[str] = []
        if broken:
            recs.append(f"{len(broken)} broken evidence chains detected")
        if not recs:
            recs.append("All evidence chains verified")
        return EvidenceChainReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_integrity_score=avg,
            by_integrity_status=by_is,
            by_chain_type=by_ct,
            by_integrity_risk=by_ir,
            broken_chains=broken,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        is_dist: dict[str, int] = {}
        for r in self._records:
            k = r.integrity_status.value
            is_dist[k] = is_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "integrity_status_distribution": is_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("evidence_chain_integrity_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_chain_integrity_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute integrity score per chain."""
        chain_scores: dict[str, list[float]] = {}
        chain_types: dict[str, str] = {}
        for r in self._records:
            chain_scores.setdefault(r.chain_id, []).append(r.integrity_score)
            chain_types[r.chain_id] = r.chain_type.value
        results: list[dict[str, Any]] = []
        for cid, scores in chain_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "chain_id": cid,
                    "chain_type": chain_types[cid],
                    "avg_integrity_score": avg,
                    "link_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_integrity_score"])
        return results

    def detect_broken_evidence_chains(
        self,
    ) -> list[dict[str, Any]]:
        """Detect chains with broken or suspect integrity."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.integrity_status in (IntegrityStatus.BROKEN, IntegrityStatus.SUSPECT)
                and r.chain_id not in seen
            ):
                seen.add(r.chain_id)
                results.append(
                    {
                        "chain_id": r.chain_id,
                        "integrity_status": r.integrity_status.value,
                        "integrity_score": r.integrity_score,
                        "evidence_id": r.evidence_id,
                    }
                )
        results.sort(key=lambda x: x["integrity_score"])
        return results

    def rank_evidence_by_integrity_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank evidence by integrity risk level."""
        evidence_risk: dict[str, float] = {}
        evidence_chains: dict[str, str] = {}
        for r in self._records:
            risk_val = 100.0 - r.integrity_score
            evidence_risk[r.evidence_id] = evidence_risk.get(r.evidence_id, 0.0) + risk_val
            evidence_chains[r.evidence_id] = r.chain_id
        results: list[dict[str, Any]] = []
        for eid, risk in evidence_risk.items():
            results.append(
                {
                    "evidence_id": eid,
                    "chain_id": evidence_chains[eid],
                    "integrity_risk_score": round(risk, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["integrity_risk_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
