"""Lateral Movement Predictor — predict lateral movement via graph and behavioral analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MovementTechnique(StrEnum):
    PASS_THE_HASH = "pass_the_hash"  # noqa: S105
    PASS_THE_TICKET = "pass_the_ticket"  # noqa: S105
    REMOTE_SERVICE = "remote_service"
    WMI_EXEC = "wmi_exec"
    SSH_HIJACK = "ssh_hijack"


class PredictionSource(StrEnum):
    GRAPH_ANALYSIS = "graph_analysis"
    BEHAVIORAL = "behavioral"
    CREDENTIAL_MONITOR = "credential_monitor"  # noqa: S105
    NETWORK_FLOW = "network_flow"
    ENDPOINT = "endpoint"


class MovementRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CONTAINED = "contained"


# --- Models ---


class MovementPrediction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_id: str = ""
    movement_technique: MovementTechnique = MovementTechnique.PASS_THE_HASH
    prediction_source: PredictionSource = PredictionSource.GRAPH_ANALYSIS
    movement_risk: MovementRisk = MovementRisk.CRITICAL
    prediction_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MovementAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_id: str = ""
    movement_technique: MovementTechnique = MovementTechnique.PASS_THE_HASH
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LateralMovementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_prediction_score: float = 0.0
    by_technique: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class LateralMovementPredictor:
    """Predict lateral movement via graph analysis and credential monitoring."""

    def __init__(
        self,
        max_records: int = 200000,
        prediction_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._prediction_threshold = prediction_threshold
        self._records: list[MovementPrediction] = []
        self._analyses: list[MovementAnalysis] = []
        logger.info(
            "lateral_movement_predictor.initialized",
            max_records=max_records,
            prediction_threshold=prediction_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_movement(
        self,
        prediction_id: str,
        movement_technique: MovementTechnique = MovementTechnique.PASS_THE_HASH,
        prediction_source: PredictionSource = PredictionSource.GRAPH_ANALYSIS,
        movement_risk: MovementRisk = MovementRisk.CRITICAL,
        prediction_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MovementPrediction:
        record = MovementPrediction(
            prediction_id=prediction_id,
            movement_technique=movement_technique,
            prediction_source=prediction_source,
            movement_risk=movement_risk,
            prediction_score=prediction_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "lateral_movement_predictor.movement_recorded",
            record_id=record.id,
            prediction_id=prediction_id,
            movement_technique=movement_technique.value,
            prediction_source=prediction_source.value,
        )
        return record

    def get_movement(self, record_id: str) -> MovementPrediction | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_movements(
        self,
        movement_technique: MovementTechnique | None = None,
        prediction_source: PredictionSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MovementPrediction]:
        results = list(self._records)
        if movement_technique is not None:
            results = [r for r in results if r.movement_technique == movement_technique]
        if prediction_source is not None:
            results = [r for r in results if r.prediction_source == prediction_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        prediction_id: str,
        movement_technique: MovementTechnique = MovementTechnique.PASS_THE_HASH,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MovementAnalysis:
        analysis = MovementAnalysis(
            prediction_id=prediction_id,
            movement_technique=movement_technique,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "lateral_movement_predictor.analysis_added",
            prediction_id=prediction_id,
            movement_technique=movement_technique.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_technique_distribution(self) -> dict[str, Any]:
        """Group by movement_technique; return count and avg prediction_score."""
        technique_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.movement_technique.value
            technique_data.setdefault(key, []).append(r.prediction_score)
        result: dict[str, Any] = {}
        for technique, scores in technique_data.items():
            result[technique] = {
                "count": len(scores),
                "avg_prediction_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_prediction_gaps(self) -> list[dict[str, Any]]:
        """Return records where prediction_score < prediction_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.prediction_score < self._prediction_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "prediction_id": r.prediction_id,
                        "movement_technique": r.movement_technique.value,
                        "prediction_score": r.prediction_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["prediction_score"])

    def rank_by_prediction(self) -> list[dict[str, Any]]:
        """Group by service, avg prediction_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.prediction_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_prediction_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_prediction_score"])
        return results

    def detect_prediction_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> LateralMovementReport:
        by_technique: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_technique[r.movement_technique.value] = (
                by_technique.get(r.movement_technique.value, 0) + 1
            )
            by_source[r.prediction_source.value] = by_source.get(r.prediction_source.value, 0) + 1
            by_risk[r.movement_risk.value] = by_risk.get(r.movement_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.prediction_score < self._prediction_threshold)
        scores = [r.prediction_score for r in self._records]
        avg_prediction_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_prediction_gaps()
        top_gaps = [o["prediction_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} prediction(s) below prediction threshold "
                f"({self._prediction_threshold})"
            )
        if self._records and avg_prediction_score < self._prediction_threshold:
            recs.append(
                f"Avg prediction score {avg_prediction_score} below threshold "
                f"({self._prediction_threshold})"
            )
        if not recs:
            recs.append("Lateral movement prediction is healthy")
        return LateralMovementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_prediction_score=avg_prediction_score,
            by_technique=by_technique,
            by_source=by_source,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("lateral_movement_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        technique_dist: dict[str, int] = {}
        for r in self._records:
            key = r.movement_technique.value
            technique_dist[key] = technique_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "prediction_threshold": self._prediction_threshold,
            "technique_distribution": technique_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
