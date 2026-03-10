"""Adversary Emulation Engine
generate emulation plans, evaluate detection coverage,
score defense readiness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EmulationFramework(StrEnum):
    MITRE_ATTACK = "mitre_attack"
    CYBER_KILL_CHAIN = "cyber_kill_chain"
    DIAMOND_MODEL = "diamond_model"
    CUSTOM = "custom"


class EmulationPhase(StrEnum):
    RECON = "recon"
    WEAPONIZE = "weaponize"
    DELIVER = "deliver"
    EXPLOIT = "exploit"
    INSTALL = "install"
    COMMAND = "command"
    ACTIONS = "actions"


class EmulationOutcome(StrEnum):
    DETECTED = "detected"
    BLOCKED = "blocked"
    EVADED = "evaded"
    PARTIAL = "partial"


# --- Models ---


class EmulationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    emulation_id: str = ""
    framework: EmulationFramework = EmulationFramework.MITRE_ATTACK
    phase: EmulationPhase = EmulationPhase.RECON
    outcome: EmulationOutcome = EmulationOutcome.DETECTED
    detection_rate: float = 0.0
    readiness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EmulationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    emulation_id: str = ""
    framework: EmulationFramework = EmulationFramework.MITRE_ATTACK
    analysis_score: float = 0.0
    coverage_pct: float = 0.0
    gaps_found: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EmulationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_detection_rate: float = 0.0
    avg_readiness: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    coverage_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdversaryEmulationEngine:
    """Generate emulation plans, evaluate detection
    coverage, and score defense readiness."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 0.8,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[EmulationRecord] = []
        self._analyses: list[EmulationAnalysis] = []
        logger.info(
            "adversary_emulation_engine.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    def add_record(
        self,
        emulation_id: str,
        framework: EmulationFramework = (EmulationFramework.MITRE_ATTACK),
        phase: EmulationPhase = EmulationPhase.RECON,
        outcome: EmulationOutcome = (EmulationOutcome.DETECTED),
        detection_rate: float = 0.0,
        readiness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EmulationRecord:
        record = EmulationRecord(
            emulation_id=emulation_id,
            framework=framework,
            phase=phase,
            outcome=outcome,
            detection_rate=detection_rate,
            readiness_score=readiness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "adversary_emulation_engine.record_added",
            record_id=record.id,
            emulation_id=emulation_id,
        )
        return record

    def process(self, key: str) -> EmulationAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        score = rec.detection_rate * 100.0
        gaps = 1 if rec.outcome == EmulationOutcome.EVADED else 0
        analysis = EmulationAnalysis(
            emulation_id=rec.emulation_id,
            framework=rec.framework,
            analysis_score=round(score, 2),
            coverage_pct=round(rec.detection_rate * 100, 2),
            gaps_found=gaps,
            description=(f"Emulation {rec.emulation_id} scored {score:.1f}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> EmulationReport:
        by_fw: dict[str, int] = {}
        by_ph: dict[str, int] = {}
        by_oc: dict[str, int] = {}
        det_rates: list[float] = []
        readiness: list[float] = []
        for r in self._records:
            f = r.framework.value
            by_fw[f] = by_fw.get(f, 0) + 1
            p = r.phase.value
            by_ph[p] = by_ph.get(p, 0) + 1
            o = r.outcome.value
            by_oc[o] = by_oc.get(o, 0) + 1
            det_rates.append(r.detection_rate)
            readiness.append(r.readiness_score)
        avg_det = round(sum(det_rates) / len(det_rates), 4) if det_rates else 0.0
        avg_rdy = round(sum(readiness) / len(readiness), 2) if readiness else 0.0
        gaps = [
            r.emulation_id for r in self._records if r.detection_rate < self._detection_threshold
        ][:5]
        recs: list[str] = []
        if gaps:
            recs.append(f"{len(gaps)} emulations below detection threshold")
        if not recs:
            recs.append("Detection coverage is adequate")
        return EmulationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_detection_rate=avg_det,
            avg_readiness=avg_rdy,
            by_framework=by_fw,
            by_phase=by_ph,
            by_outcome=by_oc,
            coverage_gaps=gaps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fw_dist: dict[str, int] = {}
        for r in self._records:
            k = r.framework.value
            fw_dist[k] = fw_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": (self._detection_threshold),
            "framework_distribution": fw_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("adversary_emulation_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def generate_emulation_plan(
        self,
    ) -> list[dict[str, Any]]:
        """Generate emulation plan grouped by phase."""
        phase_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            k = r.phase.value
            phase_data.setdefault(k, []).append(
                {
                    "emulation_id": r.emulation_id,
                    "framework": r.framework.value,
                    "outcome": r.outcome.value,
                    "detection_rate": r.detection_rate,
                }
            )
        results: list[dict[str, Any]] = []
        for phase, items in phase_data.items():
            results.append(
                {
                    "phase": phase,
                    "technique_count": len(items),
                    "techniques": items[:10],
                }
            )
        return results

    def evaluate_detection_coverage(
        self,
    ) -> dict[str, Any]:
        """Evaluate detection coverage by framework."""
        if not self._records:
            return {
                "overall_coverage": 0.0,
                "by_framework": {},
            }
        fw_rates: dict[str, list[float]] = {}
        for r in self._records:
            k = r.framework.value
            fw_rates.setdefault(k, []).append(r.detection_rate)
        by_fw: dict[str, float] = {}
        for fw, rates in fw_rates.items():
            by_fw[fw] = round(sum(rates) / len(rates), 4)
        all_rates = [r.detection_rate for r in self._records]
        overall = round(sum(all_rates) / len(all_rates), 4)
        return {
            "overall_coverage": overall,
            "by_framework": by_fw,
        }

    def score_defense_readiness(
        self,
    ) -> dict[str, Any]:
        """Score defense readiness across phases."""
        if not self._records:
            return {
                "overall_readiness": 0.0,
                "by_phase": {},
            }
        phase_scores: dict[str, list[float]] = {}
        for r in self._records:
            k = r.phase.value
            phase_scores.setdefault(k, []).append(r.readiness_score)
        by_phase: dict[str, float] = {}
        for ph, scores in phase_scores.items():
            by_phase[ph] = round(sum(scores) / len(scores), 2)
        all_scores = [r.readiness_score for r in self._records]
        overall = round(sum(all_scores) / len(all_scores), 2)
        return {
            "overall_readiness": overall,
            "by_phase": by_phase,
        }
