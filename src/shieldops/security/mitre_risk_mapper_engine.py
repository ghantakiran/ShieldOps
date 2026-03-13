"""MITRE Risk Mapper Engine
map detections to MITRE ATT&CK techniques,
compute tactic coverage, identify detection gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackPhase(StrEnum):
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    EXFILTRATION = "exfiltration"


class TacticCoverage(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class MappingConfidence(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


# --- Models ---


class MitreRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_id: str = ""
    technique_id: str = ""
    attack_phase: AttackPhase = AttackPhase.INITIAL_ACCESS
    coverage: TacticCoverage = TacticCoverage.PARTIAL
    confidence: MappingConfidence = MappingConfidence.PROBABLE
    risk_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MitreRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_id: str = ""
    technique_id: str = ""
    attack_phase: AttackPhase = AttackPhase.INITIAL_ACCESS
    coverage_score: float = 0.0
    gap_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MitreRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_coverage: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    uncovered_phases: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MitreRiskMapperEngine:
    """Map detections to MITRE ATT&CK, compute
    tactic coverage, identify detection gaps."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MitreRiskRecord] = []
        self._analyses: dict[str, MitreRiskAnalysis] = {}
        logger.info(
            "mitre_risk_mapper_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        detection_id: str = "",
        technique_id: str = "",
        attack_phase: AttackPhase = (AttackPhase.INITIAL_ACCESS),
        coverage: TacticCoverage = (TacticCoverage.PARTIAL),
        confidence: MappingConfidence = (MappingConfidence.PROBABLE),
        risk_score: float = 0.0,
        description: str = "",
    ) -> MitreRiskRecord:
        record = MitreRiskRecord(
            detection_id=detection_id,
            technique_id=technique_id,
            attack_phase=attack_phase,
            coverage=coverage,
            confidence=confidence,
            risk_score=risk_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mitre_risk_mapper.record_added",
            record_id=record.id,
            detection_id=detection_id,
        )
        return record

    def process(self, key: str) -> MitreRiskAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        cov_map = {
            "full": 1.0,
            "partial": 0.6,
            "minimal": 0.3,
            "none": 0.0,
        }
        cov_score = cov_map.get(rec.coverage.value, 0.0)
        gaps = sum(
            1 for r in self._records if r.coverage in (TacticCoverage.NONE, TacticCoverage.MINIMAL)
        )
        analysis = MitreRiskAnalysis(
            detection_id=rec.detection_id,
            technique_id=rec.technique_id,
            attack_phase=rec.attack_phase,
            coverage_score=round(cov_score, 2),
            gap_count=gaps,
            description=(f"Detection {rec.detection_id} maps to {rec.technique_id}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MitreRiskReport:
        by_ph: dict[str, int] = {}
        by_cv: dict[str, int] = {}
        by_cf: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.attack_phase.value
            by_ph[k] = by_ph.get(k, 0) + 1
            k2 = r.coverage.value
            by_cv[k2] = by_cv.get(k2, 0) + 1
            k3 = r.confidence.value
            by_cf[k3] = by_cf.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        all_phases = {p.value for p in AttackPhase}
        covered = {r.attack_phase.value for r in self._records}
        uncovered = sorted(all_phases - covered)
        recs: list[str] = []
        if uncovered:
            recs.append(f"{len(uncovered)} attack phases have no coverage")
        if not recs:
            recs.append("MITRE coverage is adequate")
        return MitreRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_phase=by_ph,
            by_coverage=by_cv,
            by_confidence=by_cf,
            uncovered_phases=uncovered,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ph_dist: dict[str, int] = {}
        for r in self._records:
            k = r.attack_phase.value
            ph_dist[k] = ph_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "phase_distribution": ph_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("mitre_risk_mapper_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def map_detection_to_technique(
        self,
    ) -> list[dict[str, Any]]:
        """Map each detection to its techniques."""
        det_techs: dict[str, list[str]] = {}
        for r in self._records:
            det_techs.setdefault(r.detection_id, []).append(r.technique_id)
        results: list[dict[str, Any]] = []
        for did, techs in det_techs.items():
            results.append(
                {
                    "detection_id": did,
                    "techniques": sorted(set(techs)),
                    "technique_count": len(set(techs)),
                }
            )
        return results

    def compute_tactic_coverage(
        self,
    ) -> dict[str, Any]:
        """Coverage percentage per attack phase."""
        if not self._records:
            return {
                "overall_coverage": 0.0,
                "by_phase": {},
            }
        cov_map = {
            "full": 1.0,
            "partial": 0.6,
            "minimal": 0.3,
            "none": 0.0,
        }
        phase_scores: dict[str, list[float]] = {}
        for r in self._records:
            k = r.attack_phase.value
            s = cov_map.get(r.coverage.value, 0.0)
            phase_scores.setdefault(k, []).append(s)
        by_phase: dict[str, float] = {}
        all_scores: list[float] = []
        for ph, scores in phase_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            by_phase[ph] = avg
            all_scores.extend(scores)
        overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
        return {
            "overall_coverage": overall,
            "by_phase": by_phase,
        }

    def identify_detection_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Find phases with no or minimal coverage."""
        all_phases = {p.value for p in AttackPhase}
        covered = {r.attack_phase.value for r in self._records}
        results: list[dict[str, Any]] = []
        for ph in sorted(all_phases - covered):
            results.append(
                {
                    "phase": ph,
                    "coverage": "none",
                    "detection_count": 0,
                }
            )
        for r in self._records:
            if r.coverage in (
                TacticCoverage.NONE,
                TacticCoverage.MINIMAL,
            ):
                results.append(
                    {
                        "phase": r.attack_phase.value,
                        "coverage": r.coverage.value,
                        "detection_count": 1,
                    }
                )
        return results
