"""MITRE ATT&CK Mapper — map events to MITRE ATT&CK tactics/techniques."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackTactic(StrEnum):
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"


class TechniqueCategory(StrEnum):
    PHISHING = "phishing"
    EXPLOIT_PUBLIC = "exploit_public"
    COMMAND_SCRIPTING = "command_scripting"
    VALID_ACCOUNTS = "valid_accounts"
    SUPPLY_CHAIN = "supply_chain"


class CoverageLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"
    UNKNOWN = "unknown"


# --- Models ---


class AttackMapping(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    technique_id: str = ""
    attack_tactic: AttackTactic = AttackTactic.INITIAL_ACCESS
    technique_category: TechniqueCategory = TechniqueCategory.PHISHING
    coverage_level: CoverageLevel = CoverageLevel.FULL
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    technique_id: str = ""
    attack_tactic: AttackTactic = AttackTactic.INITIAL_ACCESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AttackCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_coverage_score: float = 0.0
    by_tactic: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_coverage: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MitreAttackMapper:
    """Map events to MITRE ATT&CK tactics/techniques, coverage heatmaps, detection gap analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        coverage_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._coverage_gap_threshold = coverage_gap_threshold
        self._records: list[AttackMapping] = []
        self._analyses: list[CoverageAnalysis] = []
        logger.info(
            "mitre_attack_mapper.initialized",
            max_records=max_records,
            coverage_gap_threshold=coverage_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mapping(
        self,
        technique_id: str,
        attack_tactic: AttackTactic = AttackTactic.INITIAL_ACCESS,
        technique_category: TechniqueCategory = TechniqueCategory.PHISHING,
        coverage_level: CoverageLevel = CoverageLevel.FULL,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AttackMapping:
        record = AttackMapping(
            technique_id=technique_id,
            attack_tactic=attack_tactic,
            technique_category=technique_category,
            coverage_level=coverage_level,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mitre_attack_mapper.mapping_recorded",
            record_id=record.id,
            technique_id=technique_id,
            attack_tactic=attack_tactic.value,
            technique_category=technique_category.value,
        )
        return record

    def get_mapping(self, record_id: str) -> AttackMapping | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mappings(
        self,
        attack_tactic: AttackTactic | None = None,
        technique_category: TechniqueCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AttackMapping]:
        results = list(self._records)
        if attack_tactic is not None:
            results = [r for r in results if r.attack_tactic == attack_tactic]
        if technique_category is not None:
            results = [r for r in results if r.technique_category == technique_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        technique_id: str,
        attack_tactic: AttackTactic = AttackTactic.INITIAL_ACCESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CoverageAnalysis:
        analysis = CoverageAnalysis(
            technique_id=technique_id,
            attack_tactic=attack_tactic,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "mitre_attack_mapper.analysis_added",
            technique_id=technique_id,
            attack_tactic=attack_tactic.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_tactic_distribution(self) -> dict[str, Any]:
        """Group by attack_tactic; return count and avg coverage_score."""
        tactic_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.attack_tactic.value
            tactic_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for tactic, scores in tactic_data.items():
            result[tactic] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_coverage_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_score < coverage_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_score < self._coverage_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "technique_id": r.technique_id,
                        "attack_tactic": r.attack_tactic.value,
                        "coverage_score": r.coverage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["coverage_score"])

    def rank_by_coverage(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"])
        return results

    def detect_coverage_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AttackCoverageReport:
        by_tactic: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_coverage: dict[str, int] = {}
        for r in self._records:
            by_tactic[r.attack_tactic.value] = by_tactic.get(r.attack_tactic.value, 0) + 1
            by_category[r.technique_category.value] = (
                by_category.get(r.technique_category.value, 0) + 1
            )
            by_coverage[r.coverage_level.value] = by_coverage.get(r.coverage_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.coverage_score < self._coverage_gap_threshold)
        scores = [r.coverage_score for r in self._records]
        avg_coverage_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_coverage_gaps()
        top_gaps = [o["technique_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} technique(s) below coverage threshold "
                f"({self._coverage_gap_threshold})"
            )
        if self._records and avg_coverage_score < self._coverage_gap_threshold:
            recs.append(
                f"Avg coverage score {avg_coverage_score} below threshold "
                f"({self._coverage_gap_threshold})"
            )
        if not recs:
            recs.append("MITRE ATT&CK coverage is healthy")
        return AttackCoverageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_coverage_score=avg_coverage_score,
            by_tactic=by_tactic,
            by_category=by_category,
            by_coverage=by_coverage,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("mitre_attack_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tactic_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attack_tactic.value
            tactic_dist[key] = tactic_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "coverage_gap_threshold": self._coverage_gap_threshold,
            "tactic_distribution": tactic_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
