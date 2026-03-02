"""Adversary Simulation Engine — simulate adversary TTPs for purple team exercises."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SimulationType(StrEnum):
    RED_TEAM = "red_team"
    PURPLE_TEAM = "purple_team"
    TABLETOP = "tabletop"
    AUTOMATED = "automated"
    BREACH_SIMULATION = "breach_simulation"


class TTPCategory(StrEnum):
    INITIAL_ACCESS = "initial_access"
    LATERAL_MOVEMENT = "lateral_movement"
    EXFILTRATION = "exfiltration"
    COMMAND_CONTROL = "command_control"
    IMPACT = "impact"


class SimulationOutcome(StrEnum):
    DETECTED = "detected"
    PARTIALLY_DETECTED = "partially_detected"
    MISSED = "missed"
    BLOCKED = "blocked"
    CONTAINED = "contained"


# --- Models ---


class SimulationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_name: str = ""
    simulation_type: SimulationType = SimulationType.RED_TEAM
    ttp_category: TTPCategory = TTPCategory.INITIAL_ACCESS
    simulation_outcome: SimulationOutcome = SimulationOutcome.DETECTED
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_name: str = ""
    simulation_type: SimulationType = SimulationType.RED_TEAM
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdversarySimulationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_detection_count: int = 0
    avg_detection_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_ttp: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_low_detection: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdversarySimulationEngine:
    """Simulate adversary TTPs for purple team exercises."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[SimulationRecord] = []
        self._analyses: list[SimulationAnalysis] = []
        logger.info(
            "adversary_simulation_engine.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    def record_simulation(
        self,
        simulation_name: str,
        simulation_type: SimulationType = SimulationType.RED_TEAM,
        ttp_category: TTPCategory = TTPCategory.INITIAL_ACCESS,
        simulation_outcome: SimulationOutcome = SimulationOutcome.DETECTED,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SimulationRecord:
        record = SimulationRecord(
            simulation_name=simulation_name,
            simulation_type=simulation_type,
            ttp_category=ttp_category,
            simulation_outcome=simulation_outcome,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "adversary_simulation_engine.simulation_recorded",
            record_id=record.id,
            simulation_name=simulation_name,
            simulation_type=simulation_type.value,
            ttp_category=ttp_category.value,
        )
        return record

    def get_simulation(self, record_id: str) -> SimulationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_simulations(
        self,
        simulation_type: SimulationType | None = None,
        ttp_category: TTPCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]:
        results = list(self._records)
        if simulation_type is not None:
            results = [r for r in results if r.simulation_type == simulation_type]
        if ttp_category is not None:
            results = [r for r in results if r.ttp_category == ttp_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        simulation_name: str,
        simulation_type: SimulationType = SimulationType.RED_TEAM,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SimulationAnalysis:
        analysis = SimulationAnalysis(
            simulation_name=simulation_name,
            simulation_type=simulation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "adversary_simulation_engine.analysis_added",
            simulation_name=simulation_name,
            simulation_type=simulation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_simulation_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.simulation_type.value
            type_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for stype, scores in type_data.items():
            result[stype] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_detection_simulations(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "simulation_name": r.simulation_name,
                        "simulation_type": r.simulation_type.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {"service": svc, "avg_detection_score": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_simulation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AdversarySimulationReport:
        by_type: dict[str, int] = {}
        by_ttp: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_type[r.simulation_type.value] = by_type.get(r.simulation_type.value, 0) + 1
            by_ttp[r.ttp_category.value] = by_ttp.get(r.ttp_category.value, 0) + 1
            by_outcome[r.simulation_outcome.value] = (
                by_outcome.get(r.simulation_outcome.value, 0) + 1
            )
        low_detection_count = sum(
            1 for r in self._records if r.detection_score < self._detection_threshold
        )
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_detection_simulations()
        top_low_detection = [o["simulation_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_detection_count > 0:
            recs.append(
                f"{low_detection_count} simulation(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Adversary simulation detection capability is healthy")
        return AdversarySimulationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_detection_count=low_detection_count,
            avg_detection_score=avg_detection_score,
            by_type=by_type,
            by_ttp=by_ttp,
            by_outcome=by_outcome,
            top_low_detection=top_low_detection,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("adversary_simulation_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.simulation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
