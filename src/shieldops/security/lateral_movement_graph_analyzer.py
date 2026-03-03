"""Lateral Movement Graph Analyzer — analyze lateral movement paths and graph metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MovementType(StrEnum):
    RDP = "rdp"
    SSH = "ssh"
    SMB = "smb"
    WMI = "wmi"
    PSEXEC = "psexec"


class PathRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BENIGN = "benign"


class GraphMetric(StrEnum):
    CENTRALITY = "centrality"
    BETWEENNESS = "betweenness"
    PATH_LENGTH = "path_length"
    CLUSTERING = "clustering"
    CONNECTIVITY = "connectivity"


# --- Models ---


class MovementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_host: str = ""
    movement_type: MovementType = MovementType.RDP
    path_risk: PathRisk = PathRisk.BENIGN
    graph_metric: GraphMetric = GraphMetric.CENTRALITY
    movement_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MovementAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_host: str = ""
    movement_type: MovementType = MovementType.RDP
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
    avg_movement_score: float = 0.0
    by_movement_type: dict[str, int] = Field(default_factory=dict)
    by_path_risk: dict[str, int] = Field(default_factory=dict)
    by_graph_metric: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class LateralMovementGraphAnalyzer:
    """Analyze lateral movement paths, graph metrics, and detect suspicious traversals."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[MovementRecord] = []
        self._analyses: list[MovementAnalysis] = []
        logger.info(
            "lateral_movement_graph_analyzer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_movement(
        self,
        source_host: str,
        movement_type: MovementType = MovementType.RDP,
        path_risk: PathRisk = PathRisk.BENIGN,
        graph_metric: GraphMetric = GraphMetric.CENTRALITY,
        movement_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MovementRecord:
        record = MovementRecord(
            source_host=source_host,
            movement_type=movement_type,
            path_risk=path_risk,
            graph_metric=graph_metric,
            movement_score=movement_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "lateral_movement_graph_analyzer.movement_recorded",
            record_id=record.id,
            source_host=source_host,
            movement_type=movement_type.value,
            path_risk=path_risk.value,
        )
        return record

    def get_record(self, record_id: str) -> MovementRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        movement_type: MovementType | None = None,
        path_risk: PathRisk | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MovementRecord]:
        results = list(self._records)
        if movement_type is not None:
            results = [r for r in results if r.movement_type == movement_type]
        if path_risk is not None:
            results = [r for r in results if r.path_risk == path_risk]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        source_host: str,
        movement_type: MovementType = MovementType.RDP,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MovementAnalysis:
        analysis = MovementAnalysis(
            source_host=source_host,
            movement_type=movement_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "lateral_movement_graph_analyzer.analysis_added",
            source_host=source_host,
            movement_type=movement_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by movement_type; return count and avg movement_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.movement_type.value
            type_data.setdefault(key, []).append(r.movement_score)
        result: dict[str, Any] = {}
        for mtype, scores in type_data.items():
            result[mtype] = {
                "count": len(scores),
                "avg_movement_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where movement_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.movement_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "source_host": r.source_host,
                        "movement_type": r.movement_type.value,
                        "movement_score": r.movement_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["movement_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg movement_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.movement_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_movement_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_movement_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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
        by_movement_type: dict[str, int] = {}
        by_path_risk: dict[str, int] = {}
        by_graph_metric: dict[str, int] = {}
        for r in self._records:
            by_movement_type[r.movement_type.value] = (
                by_movement_type.get(r.movement_type.value, 0) + 1
            )
            by_path_risk[r.path_risk.value] = by_path_risk.get(r.path_risk.value, 0) + 1
            by_graph_metric[r.graph_metric.value] = by_graph_metric.get(r.graph_metric.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.movement_score < self._threshold)
        scores = [r.movement_score for r in self._records]
        avg_movement_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["source_host"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} path(s) below movement threshold ({self._threshold})")
        if self._records and avg_movement_score < self._threshold:
            recs.append(
                f"Avg movement score {avg_movement_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Lateral movement graph analysis is healthy")
        return LateralMovementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_movement_score=avg_movement_score,
            by_movement_type=by_movement_type,
            by_path_risk=by_path_risk,
            by_graph_metric=by_graph_metric,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("lateral_movement_graph_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        movement_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.movement_type.value
            movement_type_dist[key] = movement_type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "movement_type_distribution": movement_type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
