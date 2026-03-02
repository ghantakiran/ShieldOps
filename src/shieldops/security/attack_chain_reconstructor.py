"""Attack Chain Reconstructor — build kill-chain narratives from correlated events."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class KillChainPhase(StrEnum):
    RECONNAISSANCE = "reconnaissance"
    WEAPONIZATION = "weaponization"
    DELIVERY = "delivery"
    EXPLOITATION = "exploitation"
    INSTALLATION = "installation"


class ChainConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"


class AttackVector(StrEnum):
    NETWORK = "network"
    EMAIL = "email"
    WEB = "web"
    PHYSICAL = "physical"
    INSIDER = "insider"


# --- Models ---


class ChainRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_name: str = ""
    kill_chain_phase: KillChainPhase = KillChainPhase.RECONNAISSANCE
    chain_confidence: ChainConfidence = ChainConfidence.CONFIRMED
    attack_vector: AttackVector = AttackVector.NETWORK
    completeness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ChainAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_name: str = ""
    kill_chain_phase: KillChainPhase = KillChainPhase.RECONNAISSANCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AttackChainReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    incomplete_chain_count: int = 0
    avg_completeness_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_vector: dict[str, int] = Field(default_factory=dict)
    top_incomplete: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AttackChainReconstructor:
    """Build kill-chain narratives from correlated events."""

    def __init__(
        self,
        max_records: int = 200000,
        completeness_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._completeness_threshold = completeness_threshold
        self._records: list[ChainRecord] = []
        self._analyses: list[ChainAnalysis] = []
        logger.info(
            "attack_chain_reconstructor.initialized",
            max_records=max_records,
            completeness_threshold=completeness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_chain(
        self,
        chain_name: str,
        kill_chain_phase: KillChainPhase = KillChainPhase.RECONNAISSANCE,
        chain_confidence: ChainConfidence = ChainConfidence.CONFIRMED,
        attack_vector: AttackVector = AttackVector.NETWORK,
        completeness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ChainRecord:
        record = ChainRecord(
            chain_name=chain_name,
            kill_chain_phase=kill_chain_phase,
            chain_confidence=chain_confidence,
            attack_vector=attack_vector,
            completeness_score=completeness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "attack_chain_reconstructor.chain_recorded",
            record_id=record.id,
            chain_name=chain_name,
            kill_chain_phase=kill_chain_phase.value,
            chain_confidence=chain_confidence.value,
        )
        return record

    def get_chain(self, record_id: str) -> ChainRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_chains(
        self,
        kill_chain_phase: KillChainPhase | None = None,
        chain_confidence: ChainConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ChainRecord]:
        results = list(self._records)
        if kill_chain_phase is not None:
            results = [r for r in results if r.kill_chain_phase == kill_chain_phase]
        if chain_confidence is not None:
            results = [r for r in results if r.chain_confidence == chain_confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        chain_name: str,
        kill_chain_phase: KillChainPhase = KillChainPhase.RECONNAISSANCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ChainAnalysis:
        analysis = ChainAnalysis(
            chain_name=chain_name,
            kill_chain_phase=kill_chain_phase,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "attack_chain_reconstructor.analysis_added",
            chain_name=chain_name,
            kill_chain_phase=kill_chain_phase.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_phase_distribution(self) -> dict[str, Any]:
        """Group by kill_chain_phase; return count and avg completeness_score."""
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.kill_chain_phase.value
            phase_data.setdefault(key, []).append(r.completeness_score)
        result: dict[str, Any] = {}
        for phase, scores in phase_data.items():
            result[phase] = {
                "count": len(scores),
                "avg_completeness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_incomplete_chains(self) -> list[dict[str, Any]]:
        """Return records where completeness_score < completeness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.completeness_score < self._completeness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "chain_name": r.chain_name,
                        "kill_chain_phase": r.kill_chain_phase.value,
                        "completeness_score": r.completeness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["completeness_score"])

    def rank_by_completeness(self) -> list[dict[str, Any]]:
        """Group by service, avg completeness_score, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.completeness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_completeness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_completeness_score"])
        return results

    def detect_chain_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AttackChainReport:
        by_phase: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_vector: dict[str, int] = {}
        for r in self._records:
            by_phase[r.kill_chain_phase.value] = by_phase.get(r.kill_chain_phase.value, 0) + 1
            by_confidence[r.chain_confidence.value] = (
                by_confidence.get(r.chain_confidence.value, 0) + 1
            )
            by_vector[r.attack_vector.value] = by_vector.get(r.attack_vector.value, 0) + 1
        incomplete_chain_count = sum(
            1 for r in self._records if r.completeness_score < self._completeness_threshold
        )
        scores = [r.completeness_score for r in self._records]
        avg_completeness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        incomplete_list = self.identify_incomplete_chains()
        top_incomplete = [o["chain_name"] for o in incomplete_list[:5]]
        recs: list[str] = []
        if self._records and incomplete_chain_count > 0:
            recs.append(
                f"{incomplete_chain_count} chain(s) below completeness threshold "
                f"({self._completeness_threshold})"
            )
        if self._records and avg_completeness_score < self._completeness_threshold:
            recs.append(
                f"Avg completeness score {avg_completeness_score} below threshold "
                f"({self._completeness_threshold})"
            )
        if not recs:
            recs.append("Attack chain reconstruction completeness is healthy")
        return AttackChainReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            incomplete_chain_count=incomplete_chain_count,
            avg_completeness_score=avg_completeness_score,
            by_phase=by_phase,
            by_confidence=by_confidence,
            by_vector=by_vector,
            top_incomplete=top_incomplete,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("attack_chain_reconstructor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.kill_chain_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "completeness_threshold": self._completeness_threshold,
            "phase_distribution": phase_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
