"""Data Lineage Mapper — map data lineage across sources, transforms, and outputs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LineageNode(StrEnum):
    SOURCE = "source"
    TRANSFORM = "transform"
    STORAGE = "storage"
    OUTPUT = "output"
    ARCHIVE = "archive"


class DataFlow(StrEnum):
    INGESTION = "ingestion"
    PROCESSING = "processing"
    SHARING = "sharing"
    DELETION = "deletion"
    BACKUP = "backup"


class TraceStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BROKEN = "broken"
    PENDING = "pending"
    UNKNOWN = "unknown"


# --- Models ---


class LineageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    lineage_node: LineageNode = LineageNode.SOURCE
    data_flow: DataFlow = DataFlow.INGESTION
    trace_status: TraceStatus = TraceStatus.COMPLETE
    completeness_score: float = 0.0
    pipeline: str = ""
    data_owner: str = ""
    created_at: float = Field(default_factory=time.time)


class LineageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    lineage_node: LineageNode = LineageNode.SOURCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LineageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_completeness_score: float = 0.0
    by_node: dict[str, int] = Field(default_factory=dict)
    by_flow: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataLineageMapper:
    """Map data lineage; detect broken traces and coverage gaps across pipelines."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[LineageRecord] = []
        self._analyses: list[LineageAnalysis] = []
        logger.info(
            "data_lineage_mapper.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_lineage(
        self,
        data_asset: str,
        lineage_node: LineageNode = LineageNode.SOURCE,
        data_flow: DataFlow = DataFlow.INGESTION,
        trace_status: TraceStatus = TraceStatus.COMPLETE,
        completeness_score: float = 0.0,
        pipeline: str = "",
        data_owner: str = "",
    ) -> LineageRecord:
        record = LineageRecord(
            data_asset=data_asset,
            lineage_node=lineage_node,
            data_flow=data_flow,
            trace_status=trace_status,
            completeness_score=completeness_score,
            pipeline=pipeline,
            data_owner=data_owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_lineage_mapper.lineage_recorded",
            record_id=record.id,
            data_asset=data_asset,
            lineage_node=lineage_node.value,
            data_flow=data_flow.value,
        )
        return record

    def get_lineage(self, record_id: str) -> LineageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lineages(
        self,
        lineage_node: LineageNode | None = None,
        data_flow: DataFlow | None = None,
        data_owner: str | None = None,
        limit: int = 50,
    ) -> list[LineageRecord]:
        results = list(self._records)
        if lineage_node is not None:
            results = [r for r in results if r.lineage_node == lineage_node]
        if data_flow is not None:
            results = [r for r in results if r.data_flow == data_flow]
        if data_owner is not None:
            results = [r for r in results if r.data_owner == data_owner]
        return results[-limit:]

    def add_analysis(
        self,
        data_asset: str,
        lineage_node: LineageNode = LineageNode.SOURCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LineageAnalysis:
        analysis = LineageAnalysis(
            data_asset=data_asset,
            lineage_node=lineage_node,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_lineage_mapper.analysis_added",
            data_asset=data_asset,
            lineage_node=lineage_node.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_node_distribution(self) -> dict[str, Any]:
        """Group by lineage_node; return count and avg completeness_score."""
        node_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.lineage_node.value
            node_data.setdefault(key, []).append(r.completeness_score)
        result: dict[str, Any] = {}
        for node, scores in node_data.items():
            result[node] = {
                "count": len(scores),
                "avg_completeness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_lineage_gaps(self) -> list[dict[str, Any]]:
        """Return records where completeness_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.completeness_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "data_asset": r.data_asset,
                        "lineage_node": r.lineage_node.value,
                        "completeness_score": r.completeness_score,
                        "pipeline": r.pipeline,
                        "data_owner": r.data_owner,
                    }
                )
        return sorted(results, key=lambda x: x["completeness_score"])

    def rank_by_completeness(self) -> list[dict[str, Any]]:
        """Group by pipeline, avg completeness_score, sort ascending."""
        pipeline_scores: dict[str, list[float]] = {}
        for r in self._records:
            pipeline_scores.setdefault(r.pipeline, []).append(r.completeness_score)
        results: list[dict[str, Any]] = []
        for pipeline, scores in pipeline_scores.items():
            results.append(
                {
                    "pipeline": pipeline,
                    "avg_completeness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_completeness_score"])
        return results

    def detect_lineage_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> LineageReport:
        by_node: dict[str, int] = {}
        by_flow: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_node[r.lineage_node.value] = by_node.get(r.lineage_node.value, 0) + 1
            by_flow[r.data_flow.value] = by_flow.get(r.data_flow.value, 0) + 1
            by_status[r.trace_status.value] = by_status.get(r.trace_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.completeness_score < self._threshold)
        scores = [r.completeness_score for r in self._records]
        avg_completeness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_lineage_gaps()
        top_gaps = [o["data_asset"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} asset(s) below lineage completeness threshold ({self._threshold})"
            )
        if self._records and avg_completeness_score < self._threshold:
            recs.append(
                f"Avg completeness score {avg_completeness_score} below threshold "
                f"({self._threshold})"
            )
        if not recs:
            recs.append("Data lineage coverage is healthy")
        return LineageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_completeness_score=avg_completeness_score,
            by_node=by_node,
            by_flow=by_flow,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_lineage_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        node_dist: dict[str, int] = {}
        for r in self._records:
            key = r.lineage_node.value
            node_dist[key] = node_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "node_distribution": node_dist,
            "unique_pipelines": len({r.pipeline for r in self._records}),
            "unique_owners": len({r.data_owner for r in self._records}),
        }
