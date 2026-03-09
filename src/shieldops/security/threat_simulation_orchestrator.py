"""Threat Simulation Orchestrator — orchestrate purple team threat simulations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackTechnique(StrEnum):
    PHISHING = "phishing"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    COMMAND_AND_CONTROL = "command_and_control"
    CREDENTIAL_THEFT = "credential_theft"


class SimulationPhase(StrEnum):
    PLANNING = "planning"
    RECONNAISSANCE = "reconnaissance"
    EXECUTION = "execution"
    POST_EXPLOITATION = "post_exploitation"
    REPORTING = "reporting"


class DefenseResult(StrEnum):
    DETECTED = "detected"
    BLOCKED = "blocked"
    MISSED = "missed"
    PARTIALLY_DETECTED = "partially_detected"


# --- Models ---


class Simulation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    technique: AttackTechnique = AttackTechnique.PHISHING
    phase: SimulationPhase = SimulationPhase.PLANNING
    target_service: str = ""
    team: str = ""
    mitre_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DefenseEvaluation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_id: str = ""
    result: DefenseResult = DefenseResult.MISSED
    detection_time_ms: float = 0.0
    defense_score: float = 0.0
    control_tested: str = ""
    gaps: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class SimulationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_simulations: int = 0
    total_evaluations: int = 0
    detection_rate: float = 0.0
    avg_defense_score: float = 0.0
    by_technique: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatSimulationOrchestrator:
    """Orchestrate purple team threat simulations."""

    def __init__(
        self,
        max_records: int = 200000,
        defense_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._defense_threshold = defense_threshold
        self._simulations: list[Simulation] = []
        self._evaluations: list[DefenseEvaluation] = []
        logger.info(
            "threat_simulation_orchestrator.initialized",
            max_records=max_records,
            defense_threshold=defense_threshold,
        )

    def plan_simulation(
        self,
        name: str,
        technique: AttackTechnique = AttackTechnique.PHISHING,
        target_service: str = "",
        team: str = "",
        mitre_id: str = "",
        description: str = "",
    ) -> Simulation:
        """Plan a new threat simulation."""
        sim = Simulation(
            name=name,
            technique=technique,
            target_service=target_service,
            team=team,
            mitre_id=mitre_id,
            description=description,
        )
        self._simulations.append(sim)
        if len(self._simulations) > self._max_records:
            self._simulations = self._simulations[-self._max_records :]
        logger.info(
            "threat_simulation_orchestrator.simulation_planned",
            simulation_id=sim.id,
            name=name,
            technique=technique.value,
        )
        return sim

    def execute_attack_scenario(self, simulation_id: str) -> dict[str, Any]:
        """Execute an attack scenario for a simulation."""
        for s in self._simulations:
            if s.id == simulation_id:
                s.phase = SimulationPhase.EXECUTION
                logger.info(
                    "threat_simulation_orchestrator.scenario_executed",
                    simulation_id=simulation_id,
                )
                return {
                    "simulation_id": simulation_id,
                    "phase": SimulationPhase.EXECUTION.value,
                    "technique": s.technique.value,
                }
        return {"simulation_id": simulation_id, "error": "not_found"}

    def evaluate_defenses(
        self,
        simulation_id: str,
        result: DefenseResult = DefenseResult.MISSED,
        detection_time_ms: float = 0.0,
        defense_score: float = 0.0,
        control_tested: str = "",
        gaps: list[str] | None = None,
    ) -> DefenseEvaluation:
        """Evaluate how defenses responded to the simulation."""
        for s in self._simulations:
            if s.id == simulation_id:
                s.phase = SimulationPhase.POST_EXPLOITATION
                break
        evaluation = DefenseEvaluation(
            simulation_id=simulation_id,
            result=result,
            detection_time_ms=detection_time_ms,
            defense_score=defense_score,
            control_tested=control_tested,
            gaps=gaps or [],
        )
        self._evaluations.append(evaluation)
        if len(self._evaluations) > self._max_records:
            self._evaluations = self._evaluations[-self._max_records :]
        logger.info(
            "threat_simulation_orchestrator.defenses_evaluated",
            simulation_id=simulation_id,
            result=result.value,
            defense_score=defense_score,
        )
        return evaluation

    def generate_report(self) -> SimulationReport:
        """Generate a comprehensive simulation report."""
        by_tech: dict[str, int] = {}
        for s in self._simulations:
            by_tech[s.technique.value] = by_tech.get(s.technique.value, 0) + 1
        by_result: dict[str, int] = {}
        for e in self._evaluations:
            by_result[e.result.value] = by_result.get(e.result.value, 0) + 1
        scores = [e.defense_score for e in self._evaluations]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        detected = sum(
            1
            for e in self._evaluations
            if e.result in (DefenseResult.DETECTED, DefenseResult.BLOCKED)
        )
        det_rate = round(detected / len(self._evaluations) * 100, 2) if self._evaluations else 0.0
        all_gaps: list[str] = []
        for e in self._evaluations:
            all_gaps.extend(e.gaps)
        recs: list[str] = []
        if avg < self._defense_threshold:
            recs.append(f"Avg defense score {avg} below threshold ({self._defense_threshold})")
        if det_rate < 80:
            recs.append(f"Detection rate {det_rate}% needs improvement")
        if not recs:
            recs.append("Threat simulation metrics within healthy range")
        return SimulationReport(
            total_simulations=len(self._simulations),
            total_evaluations=len(self._evaluations),
            detection_rate=det_rate,
            avg_defense_score=avg,
            by_technique=by_tech,
            by_result=by_result,
            top_gaps=all_gaps[:5],
            recommendations=recs,
        )

    def track_improvements(self) -> dict[str, Any]:
        """Track improvements over time by comparing evaluation halves."""
        if len(self._evaluations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [e.defense_score for e in self._evaluations]
        mid = len(scores) // 2
        first = scores[:mid]
        second = scores[mid:]
        avg_first = sum(first) / len(first)
        avg_second = sum(second) / len(second)
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

    def list_simulations(
        self,
        technique: AttackTechnique | None = None,
        phase: SimulationPhase | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[Simulation]:
        """List simulations with optional filters."""
        results = list(self._simulations)
        if technique is not None:
            results = [r for r in results if r.technique == technique]
        if phase is not None:
            results = [r for r in results if r.phase == phase]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for s in self._simulations:
            key = s.technique.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_simulations": len(self._simulations),
            "total_evaluations": len(self._evaluations),
            "defense_threshold": self._defense_threshold,
            "technique_distribution": dist,
            "unique_teams": len({s.team for s in self._simulations}),
            "unique_services": len({s.target_service for s in self._simulations}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._simulations.clear()
        self._evaluations.clear()
        logger.info("threat_simulation_orchestrator.cleared")
        return {"status": "cleared"}
