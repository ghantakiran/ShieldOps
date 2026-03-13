"""Reasoning Chain Integrity Engine —
validate logical integrity of investigation reasoning chains,
detect circular reasoning, compute chain confidence."""

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
    VALID = "valid"
    WEAK_LINK = "weak_link"
    BROKEN = "broken"
    CIRCULAR = "circular"


class EvidenceStrength(StrEnum):
    CONCLUSIVE = "conclusive"
    SUPPORTIVE = "supportive"
    CIRCUMSTANTIAL = "circumstantial"
    ABSENT = "absent"


class ViolationType(StrEnum):
    LOGICAL_GAP = "logical_gap"
    UNSUPPORTED_LEAP = "unsupported_leap"
    CIRCULAR_REFERENCE = "circular_reference"
    CONTRADICTION = "contradiction"


# --- Models ---


class ReasoningChainIntegrityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    integrity_status: IntegrityStatus = IntegrityStatus.VALID
    evidence_strength: EvidenceStrength = EvidenceStrength.SUPPORTIVE
    violation_type: ViolationType = ViolationType.LOGICAL_GAP
    confidence_score: float = 0.0
    step_index: int = 0
    premise: str = ""
    conclusion: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReasoningChainIntegrityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str = ""
    integrity_status: IntegrityStatus = IntegrityStatus.VALID
    evidence_strength: EvidenceStrength = EvidenceStrength.SUPPORTIVE
    has_violation: bool = False
    chain_confidence: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReasoningChainIntegrityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_confidence_score: float = 0.0
    by_integrity_status: dict[str, int] = Field(default_factory=dict)
    by_evidence_strength: dict[str, int] = Field(default_factory=dict)
    by_violation_type: dict[str, int] = Field(default_factory=dict)
    invalid_chains: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReasoningChainIntegrityEngine:
    """Validate logical integrity of investigation reasoning chains,
    detect circular reasoning, compute chain confidence."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ReasoningChainIntegrityRecord] = []
        self._analyses: dict[str, ReasoningChainIntegrityAnalysis] = {}
        logger.info("reasoning_chain_integrity_engine.init", max_records=max_records)

    def add_record(
        self,
        chain_id: str = "",
        integrity_status: IntegrityStatus = IntegrityStatus.VALID,
        evidence_strength: EvidenceStrength = EvidenceStrength.SUPPORTIVE,
        violation_type: ViolationType = ViolationType.LOGICAL_GAP,
        confidence_score: float = 0.0,
        step_index: int = 0,
        premise: str = "",
        conclusion: str = "",
        description: str = "",
    ) -> ReasoningChainIntegrityRecord:
        record = ReasoningChainIntegrityRecord(
            chain_id=chain_id,
            integrity_status=integrity_status,
            evidence_strength=evidence_strength,
            violation_type=violation_type,
            confidence_score=confidence_score,
            step_index=step_index,
            premise=premise,
            conclusion=conclusion,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reasoning_chain_integrity.record_added",
            record_id=record.id,
            chain_id=chain_id,
        )
        return record

    def process(self, key: str) -> ReasoningChainIntegrityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        has_viol = rec.integrity_status not in (IntegrityStatus.VALID,)
        ev_weights = {
            "conclusive": 1.0,
            "supportive": 0.75,
            "circumstantial": 0.5,
            "absent": 0.0,
        }
        ev_w = ev_weights.get(rec.evidence_strength.value, 0.5)
        chain_conf = round(rec.confidence_score * ev_w, 4)
        analysis = ReasoningChainIntegrityAnalysis(
            chain_id=rec.chain_id,
            integrity_status=rec.integrity_status,
            evidence_strength=rec.evidence_strength,
            has_violation=has_viol,
            chain_confidence=chain_conf,
            description=(
                f"Chain {rec.chain_id} step={rec.step_index} status={rec.integrity_status.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ReasoningChainIntegrityReport:
        by_is: dict[str, int] = {}
        by_es: dict[str, int] = {}
        by_vt: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.integrity_status.value
            by_is[k] = by_is.get(k, 0) + 1
            k2 = r.evidence_strength.value
            by_es[k2] = by_es.get(k2, 0) + 1
            k3 = r.violation_type.value
            by_vt[k3] = by_vt.get(k3, 0) + 1
            scores.append(r.confidence_score)
        avg_conf = round(sum(scores) / len(scores), 4) if scores else 0.0
        invalid: list[str] = list(
            {
                r.chain_id
                for r in self._records
                if r.integrity_status in (IntegrityStatus.BROKEN, IntegrityStatus.CIRCULAR)
            }
        )[:10]
        recs: list[str] = []
        circular = by_is.get("circular", 0)
        if circular:
            recs.append(f"{circular} circular reasoning steps detected — review logic")
        broken = by_is.get("broken", 0)
        if broken:
            recs.append(f"{broken} broken chain steps need evidence collection")
        if not recs:
            recs.append("Reasoning chain integrity is sound")
        return ReasoningChainIntegrityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_confidence_score=avg_conf,
            by_integrity_status=by_is,
            by_evidence_strength=by_es,
            by_violation_type=by_vt,
            invalid_chains=invalid,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.integrity_status.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "integrity_status_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("reasoning_chain_integrity_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def validate_chain_integrity(self) -> list[dict[str, Any]]:
        """Validate integrity for each reasoning chain."""
        chain_map: dict[str, list[ReasoningChainIntegrityRecord]] = {}
        for r in self._records:
            chain_map.setdefault(r.chain_id, []).append(r)
        results: list[dict[str, Any]] = []
        for cid, chain_recs in chain_map.items():
            violations = [r for r in chain_recs if r.integrity_status != IntegrityStatus.VALID]
            valid = len(violations) == 0
            avg_conf = sum(r.confidence_score for r in chain_recs) / len(chain_recs)
            results.append(
                {
                    "chain_id": cid,
                    "valid": valid,
                    "violation_count": len(violations),
                    "avg_confidence": round(avg_conf, 4),
                    "step_count": len(chain_recs),
                }
            )
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def detect_circular_reasoning(self) -> list[dict[str, Any]]:
        """Detect steps with circular reasoning violations."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.integrity_status == IntegrityStatus.CIRCULAR:
                results.append(
                    {
                        "chain_id": r.chain_id,
                        "step_index": r.step_index,
                        "premise": r.premise,
                        "conclusion": r.conclusion,
                        "violation_type": r.violation_type.value,
                        "confidence_score": r.confidence_score,
                    }
                )
        results.sort(key=lambda x: x["step_index"])
        return results

    def compute_chain_confidence(self) -> list[dict[str, Any]]:
        """Compute weighted confidence for each reasoning chain."""
        ev_weights = {
            "conclusive": 1.0,
            "supportive": 0.75,
            "circumstantial": 0.5,
            "absent": 0.0,
        }
        chain_scores: dict[str, list[float]] = {}
        for r in self._records:
            ev_w = ev_weights.get(r.evidence_strength.value, 0.5)
            weighted = r.confidence_score * ev_w
            chain_scores.setdefault(r.chain_id, []).append(weighted)
        results: list[dict[str, Any]] = []
        for cid, wscores in chain_scores.items():
            avg_conf = sum(wscores) / len(wscores)
            results.append(
                {
                    "chain_id": cid,
                    "weighted_confidence": round(avg_conf, 4),
                    "step_count": len(wscores),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["weighted_confidence"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
