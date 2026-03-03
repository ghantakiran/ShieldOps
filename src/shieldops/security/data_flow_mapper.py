"""Data Flow Mapper — map data flows across environments and assess compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlowType(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    CROSS_REGION = "cross_region"
    CROSS_CLOUD = "cross_cloud"
    HYBRID = "hybrid"


class DataSensitivity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    PUBLIC = "public"


class FlowCompliance(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    EXEMPT = "exempt"
    UNKNOWN = "unknown"
    PENDING = "pending"


# --- Models ---


class DataFlowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flow_id: str = ""
    flow_type: FlowType = FlowType.INTERNAL
    data_sensitivity: DataSensitivity = DataSensitivity.MEDIUM
    flow_compliance: FlowCompliance = FlowCompliance.COMPLIANT
    flow_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DataFlowAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flow_id: str = ""
    flow_type: FlowType = FlowType.INTERNAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataFlowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_flow_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_sensitivity: dict[str, int] = Field(default_factory=dict)
    by_compliance: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataFlowMapper:
    """Map data flows across environments and assess compliance posture."""

    def __init__(
        self,
        max_records: int = 200000,
        flow_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._flow_threshold = flow_threshold
        self._records: list[DataFlowRecord] = []
        self._analyses: list[DataFlowAnalysis] = []
        logger.info(
            "data_flow_mapper.initialized",
            max_records=max_records,
            flow_threshold=flow_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_flow(
        self,
        flow_id: str,
        flow_type: FlowType = FlowType.INTERNAL,
        data_sensitivity: DataSensitivity = DataSensitivity.MEDIUM,
        flow_compliance: FlowCompliance = FlowCompliance.COMPLIANT,
        flow_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DataFlowRecord:
        record = DataFlowRecord(
            flow_id=flow_id,
            flow_type=flow_type,
            data_sensitivity=data_sensitivity,
            flow_compliance=flow_compliance,
            flow_score=flow_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_flow_mapper.flow_recorded",
            record_id=record.id,
            flow_id=flow_id,
            flow_type=flow_type.value,
            data_sensitivity=data_sensitivity.value,
        )
        return record

    def get_flow(self, record_id: str) -> DataFlowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_flows(
        self,
        flow_type: FlowType | None = None,
        data_sensitivity: DataSensitivity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DataFlowRecord]:
        results = list(self._records)
        if flow_type is not None:
            results = [r for r in results if r.flow_type == flow_type]
        if data_sensitivity is not None:
            results = [r for r in results if r.data_sensitivity == data_sensitivity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        flow_id: str,
        flow_type: FlowType = FlowType.INTERNAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DataFlowAnalysis:
        analysis = DataFlowAnalysis(
            flow_id=flow_id,
            flow_type=flow_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_flow_mapper.analysis_added",
            flow_id=flow_id,
            flow_type=flow_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.flow_type.value
            type_data.setdefault(key, []).append(r.flow_score)
        result: dict[str, Any] = {}
        for ftype, scores in type_data.items():
            result[ftype] = {
                "count": len(scores),
                "avg_flow_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_flow_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.flow_score < self._flow_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "flow_id": r.flow_id,
                        "flow_type": r.flow_type.value,
                        "flow_score": r.flow_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["flow_score"])

    def rank_by_flow(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.flow_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_flow_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_flow_score"])
        return results

    def detect_flow_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DataFlowReport:
        by_type: dict[str, int] = {}
        by_sensitivity: dict[str, int] = {}
        by_compliance: dict[str, int] = {}
        for r in self._records:
            by_type[r.flow_type.value] = by_type.get(r.flow_type.value, 0) + 1
            by_sensitivity[r.data_sensitivity.value] = (
                by_sensitivity.get(r.data_sensitivity.value, 0) + 1
            )
            by_compliance[r.flow_compliance.value] = (
                by_compliance.get(r.flow_compliance.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.flow_score < self._flow_threshold)
        scores = [r.flow_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_flow_gaps()
        top_gaps = [o["flow_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} flow(s) below threshold ({self._flow_threshold})")
        if self._records and avg_score < self._flow_threshold:
            recs.append(f"Avg flow score {avg_score} below threshold ({self._flow_threshold})")
        if not recs:
            recs.append("Data flow mapping is healthy")
        return DataFlowReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_flow_score=avg_score,
            by_type=by_type,
            by_sensitivity=by_sensitivity,
            by_compliance=by_compliance,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_flow_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.flow_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "flow_threshold": self._flow_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
