"""Data Breach Simulator — simulate data breach scenarios and assess readiness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BreachScenario(StrEnum):
    INSIDER_THREAT = "insider_threat"
    EXTERNAL_ATTACK = "external_attack"
    ACCIDENTAL_EXPOSURE = "accidental_exposure"
    THIRD_PARTY = "third_party"
    SYSTEM_FAILURE = "system_failure"


class DataSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"  # noqa: S105


class SimulationMode(StrEnum):
    TABLETOP = "tabletop"
    AUTOMATED = "automated"
    HYBRID = "hybrid"
    TARGETED = "targeted"
    FULL_SCALE = "full_scale"


# --- Models ---


class BreachRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_id: str = ""
    breach_scenario: BreachScenario = BreachScenario.EXTERNAL_ATTACK
    data_sensitivity: DataSensitivity = DataSensitivity.CONFIDENTIAL
    simulation_mode: SimulationMode = SimulationMode.TABLETOP
    readiness_score: float = 0.0
    environment: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BreachAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_id: str = ""
    breach_scenario: BreachScenario = BreachScenario.EXTERNAL_ATTACK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BreachSimulationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_readiness_score: float = 0.0
    by_scenario: dict[str, int] = Field(default_factory=dict)
    by_sensitivity: dict[str, int] = Field(default_factory=dict)
    by_mode: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataBreachSimulator:
    """Simulate data breach scenarios; assess readiness and identify coverage gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[BreachRecord] = []
        self._analyses: list[BreachAnalysis] = []
        logger.info(
            "data_breach_simulator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_simulation(
        self,
        simulation_id: str,
        breach_scenario: BreachScenario = BreachScenario.EXTERNAL_ATTACK,
        data_sensitivity: DataSensitivity = DataSensitivity.CONFIDENTIAL,
        simulation_mode: SimulationMode = SimulationMode.TABLETOP,
        readiness_score: float = 0.0,
        environment: str = "",
        team: str = "",
    ) -> BreachRecord:
        record = BreachRecord(
            simulation_id=simulation_id,
            breach_scenario=breach_scenario,
            data_sensitivity=data_sensitivity,
            simulation_mode=simulation_mode,
            readiness_score=readiness_score,
            environment=environment,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_breach_simulator.simulation_recorded",
            record_id=record.id,
            simulation_id=simulation_id,
            breach_scenario=breach_scenario.value,
            simulation_mode=simulation_mode.value,
        )
        return record

    def get_simulation(self, record_id: str) -> BreachRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_simulations(
        self,
        breach_scenario: BreachScenario | None = None,
        simulation_mode: SimulationMode | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BreachRecord]:
        results = list(self._records)
        if breach_scenario is not None:
            results = [r for r in results if r.breach_scenario == breach_scenario]
        if simulation_mode is not None:
            results = [r for r in results if r.simulation_mode == simulation_mode]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        simulation_id: str,
        breach_scenario: BreachScenario = BreachScenario.EXTERNAL_ATTACK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BreachAnalysis:
        analysis = BreachAnalysis(
            simulation_id=simulation_id,
            breach_scenario=breach_scenario,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_breach_simulator.analysis_added",
            simulation_id=simulation_id,
            breach_scenario=breach_scenario.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_scenario_distribution(self) -> dict[str, Any]:
        """Group by breach_scenario; return count and avg readiness_score."""
        scenario_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.breach_scenario.value
            scenario_data.setdefault(key, []).append(r.readiness_score)
        result: dict[str, Any] = {}
        for scenario, scores in scenario_data.items():
            result[scenario] = {
                "count": len(scores),
                "avg_readiness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_readiness_gaps(self) -> list[dict[str, Any]]:
        """Return records where readiness_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.readiness_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "simulation_id": r.simulation_id,
                        "breach_scenario": r.breach_scenario.value,
                        "readiness_score": r.readiness_score,
                        "environment": r.environment,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["readiness_score"])

    def rank_by_readiness(self) -> list[dict[str, Any]]:
        """Group by environment, avg readiness_score, sort ascending."""
        env_scores: dict[str, list[float]] = {}
        for r in self._records:
            env_scores.setdefault(r.environment, []).append(r.readiness_score)
        results: list[dict[str, Any]] = []
        for env, scores in env_scores.items():
            results.append(
                {
                    "environment": env,
                    "avg_readiness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_readiness_score"])
        return results

    def detect_readiness_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> BreachSimulationReport:
        by_scenario: dict[str, int] = {}
        by_sensitivity: dict[str, int] = {}
        by_mode: dict[str, int] = {}
        for r in self._records:
            by_scenario[r.breach_scenario.value] = by_scenario.get(r.breach_scenario.value, 0) + 1
            by_sensitivity[r.data_sensitivity.value] = (
                by_sensitivity.get(r.data_sensitivity.value, 0) + 1
            )
            by_mode[r.simulation_mode.value] = by_mode.get(r.simulation_mode.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.readiness_score < self._threshold)
        scores = [r.readiness_score for r in self._records]
        avg_readiness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_readiness_gaps()
        top_gaps = [o["simulation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} simulation(s) below readiness threshold ({self._threshold})")
        if self._records and avg_readiness_score < self._threshold:
            recs.append(
                f"Avg readiness score {avg_readiness_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Breach simulation readiness is healthy")
        return BreachSimulationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_readiness_score=avg_readiness_score,
            by_scenario=by_scenario,
            by_sensitivity=by_sensitivity,
            by_mode=by_mode,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_breach_simulator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scenario_dist: dict[str, int] = {}
        for r in self._records:
            key = r.breach_scenario.value
            scenario_dist[key] = scenario_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "scenario_distribution": scenario_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_environments": len({r.environment for r in self._records}),
        }
