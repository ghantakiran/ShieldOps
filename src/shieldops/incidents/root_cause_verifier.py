"""Root Cause Verifier — verify proposed root causes against evidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceType(StrEnum):
    LOG_PATTERN = "log_pattern"
    METRIC_ANOMALY = "metric_anomaly"
    TRACE_CORRELATION = "trace_correlation"
    CONFIG_CHANGE = "config_change"
    DEPLOYMENT_EVENT = "deployment_event"


class VerificationResult(StrEnum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    INCONCLUSIVE = "inconclusive"
    UNLIKELY = "unlikely"
    DISPROVED = "disproved"


class CausalStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    SPECULATIVE = "speculative"
    NONE = "none"


# --- Models ---


class VerificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG_PATTERN
    result: VerificationResult = VerificationResult.CONFIRMED
    strength: CausalStrength = CausalStrength.STRONG
    confidence_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceChain(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_name: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG_PATTERN
    strength: CausalStrength = CausalStrength.STRONG
    link_count: int = 0
    weight: float = 1.0
    created_at: float = Field(default_factory=time.time)


class RootCauseVerifierReport(BaseModel):
    total_verifications: int = 0
    total_chains: int = 0
    confirmed_rate_pct: float = 0.0
    by_evidence_type: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    disproved_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RootCauseVerificationEngine:
    """Verify proposed root causes against evidence."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[VerificationRecord] = []
        self._chains: list[EvidenceChain] = []
        logger.info(
            "root_cause_verifier.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_verification(
        self,
        hypothesis: str,
        evidence_type: EvidenceType = (EvidenceType.LOG_PATTERN),
        result: VerificationResult = (VerificationResult.CONFIRMED),
        strength: CausalStrength = CausalStrength.STRONG,
        confidence_score: float = 0.0,
        details: str = "",
    ) -> VerificationRecord:
        record = VerificationRecord(
            hypothesis=hypothesis,
            evidence_type=evidence_type,
            result=result,
            strength=strength,
            confidence_score=confidence_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "root_cause_verifier.recorded",
            record_id=record.id,
            hypothesis=hypothesis,
            evidence_type=evidence_type.value,
            result=result.value,
        )
        return record

    def get_verification(self, record_id: str) -> VerificationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_verifications(
        self,
        hypothesis: str | None = None,
        evidence_type: EvidenceType | None = None,
        limit: int = 50,
    ) -> list[VerificationRecord]:
        results = list(self._records)
        if hypothesis is not None:
            results = [r for r in results if r.hypothesis == hypothesis]
        if evidence_type is not None:
            results = [r for r in results if r.evidence_type == evidence_type]
        return results[-limit:]

    def add_evidence_chain(
        self,
        chain_name: str,
        evidence_type: EvidenceType = (EvidenceType.LOG_PATTERN),
        strength: CausalStrength = CausalStrength.STRONG,
        link_count: int = 0,
        weight: float = 1.0,
    ) -> EvidenceChain:
        chain = EvidenceChain(
            chain_name=chain_name,
            evidence_type=evidence_type,
            strength=strength,
            link_count=link_count,
            weight=weight,
        )
        self._chains.append(chain)
        if len(self._chains) > self._max_records:
            self._chains = self._chains[-self._max_records :]
        logger.info(
            "root_cause_verifier.chain_added",
            chain_name=chain_name,
            evidence_type=evidence_type.value,
            strength=strength.value,
        )
        return chain

    # -- domain operations -------------------------------------------

    def analyze_verification_accuracy(self, hypothesis: str) -> dict[str, Any]:
        """Analyze verification accuracy for a hypothesis."""
        records = [r for r in self._records if r.hypothesis == hypothesis]
        if not records:
            return {
                "hypothesis": hypothesis,
                "status": "no_data",
            }
        confirmed = sum(1 for r in records if r.result == VerificationResult.CONFIRMED)
        confirmed_rate = round(confirmed / len(records) * 100, 2)
        avg_conf = round(
            sum(r.confidence_score for r in records) / len(records),
            2,
        )
        return {
            "hypothesis": hypothesis,
            "verification_count": len(records),
            "confirmed_count": confirmed,
            "confirmed_rate": confirmed_rate,
            "avg_confidence": avg_conf,
            "meets_threshold": (confirmed_rate >= self._min_confidence_pct),
        }

    def identify_disproved_hypotheses(
        self,
    ) -> list[dict[str, Any]]:
        """Find hypotheses with disproved/unlikely results."""
        disproved_counts: dict[str, int] = {}
        for r in self._records:
            if r.result in (
                VerificationResult.DISPROVED,
                VerificationResult.UNLIKELY,
            ):
                disproved_counts[r.hypothesis] = disproved_counts.get(r.hypothesis, 0) + 1
        results: list[dict[str, Any]] = []
        for hyp, count in disproved_counts.items():
            if count > 1:
                results.append(
                    {
                        "hypothesis": hyp,
                        "disproved_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["disproved_count"],
            reverse=True,
        )
        return results

    def rank_by_confidence(
        self,
    ) -> list[dict[str, Any]]:
        """Rank hypotheses by avg confidence desc."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.hypothesis, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for hyp, scores in totals.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "hypothesis": hyp,
                    "avg_confidence": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_confidence"],
            reverse=True,
        )
        return results

    def detect_weak_evidence(
        self,
    ) -> list[dict[str, Any]]:
        """Detect hypotheses with weak evidence (>3)."""
        non_confirmed: dict[str, int] = {}
        for r in self._records:
            if r.result != VerificationResult.CONFIRMED:
                non_confirmed[r.hypothesis] = non_confirmed.get(r.hypothesis, 0) + 1
        results: list[dict[str, Any]] = []
        for hyp, count in non_confirmed.items():
            if count > 3:
                results.append(
                    {
                        "hypothesis": hyp,
                        "non_confirmed_count": count,
                        "weak_evidence": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_confirmed_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> RootCauseVerifierReport:
        by_evidence: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_evidence[r.evidence_type.value] = by_evidence.get(r.evidence_type.value, 0) + 1
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
        confirmed = sum(1 for r in self._records if r.result == VerificationResult.CONFIRMED)
        confirmed_rate = (
            round(
                confirmed / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        disproved = sum(1 for d in self.identify_disproved_hypotheses())
        recs: list[str] = []
        if confirmed_rate < self._min_confidence_pct:
            recs.append(
                f"Confirmed rate {confirmed_rate}% is below {self._min_confidence_pct}% threshold"
            )
        if disproved > 0:
            recs.append(f"{disproved} hypothesis(es) with disproved results")
        weak = len(self.detect_weak_evidence())
        if weak > 0:
            recs.append(f"{weak} hypothesis(es) with weak evidence")
        if not recs:
            recs.append("Root cause verification is healthy")
        return RootCauseVerifierReport(
            total_verifications=len(self._records),
            total_chains=len(self._chains),
            confirmed_rate_pct=confirmed_rate,
            by_evidence_type=by_evidence,
            by_result=by_result,
            disproved_count=disproved,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._chains.clear()
        logger.info("root_cause_verifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        evidence_dist: dict[str, int] = {}
        for r in self._records:
            key = r.evidence_type.value
            evidence_dist[key] = evidence_dist.get(key, 0) + 1
        return {
            "total_verifications": len(self._records),
            "total_chains": len(self._chains),
            "min_confidence_pct": (self._min_confidence_pct),
            "evidence_distribution": evidence_dist,
            "unique_hypotheses": len({r.hypothesis for r in self._records}),
        }
