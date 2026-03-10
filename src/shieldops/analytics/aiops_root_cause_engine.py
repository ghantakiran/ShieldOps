"""AIOps Root Cause Engine

ML-driven root cause analysis correlating signals across
infrastructure, application, and network layers.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RootCauseType(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    NETWORK = "network"
    DATABASE = "database"
    EXTERNAL = "external"
    CONFIGURATION = "configuration"
    CAPACITY = "capacity"


class CorrelationMethod(StrEnum):
    TEMPORAL = "temporal"
    TOPOLOGICAL = "topological"
    STATISTICAL = "statistical"
    CAUSAL = "causal"
    ML_BASED = "ml_based"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


# --- Models ---


class RootCauseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    service: str = ""
    signal_type: str = ""
    root_cause_type: RootCauseType = RootCauseType.INFRASTRUCTURE
    correlation_method: CorrelationMethod = CorrelationMethod.TEMPORAL
    confidence_score: float = 0.0
    contributing_signals: int = 0
    resolution_time_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RootCauseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    probable_cause: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RootCauseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_confidence: float = 0.0
    avg_resolution_minutes: float = 0.0
    by_cause_type: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AIOpsRootCauseEngine:
    """AIOps Root Cause Engine

    ML-driven root cause analysis correlating signals
    across infrastructure, application, and network layers.
    """

    def __init__(
        self,
        max_records: int = 200000,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._confidence_threshold = confidence_threshold
        self._records: list[RootCauseRecord] = []
        self._analyses: list[RootCauseAnalysis] = []
        logger.info(
            "aiops_root_cause_engine.initialized",
            max_records=max_records,
            confidence_threshold=confidence_threshold,
        )

    def add_record(
        self,
        incident_id: str,
        service: str,
        signal_type: str = "",
        root_cause_type: RootCauseType = (RootCauseType.INFRASTRUCTURE),
        correlation_method: CorrelationMethod = (CorrelationMethod.TEMPORAL),
        confidence_score: float = 0.0,
        contributing_signals: int = 0,
        resolution_time_minutes: float = 0.0,
    ) -> RootCauseRecord:
        record = RootCauseRecord(
            incident_id=incident_id,
            service=service,
            signal_type=signal_type,
            root_cause_type=root_cause_type,
            correlation_method=correlation_method,
            confidence_score=confidence_score,
            contributing_signals=contributing_signals,
            resolution_time_minutes=resolution_time_minutes,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "aiops_root_cause_engine.record_added",
            record_id=record.id,
            incident_id=incident_id,
            service=service,
        )
        return record

    def identify_probable_causes(self, incident_id: str) -> list[dict[str, Any]]:
        matching = [r for r in self._records if r.incident_id == incident_id]
        if not matching:
            return []
        causes: dict[str, list[float]] = {}
        for r in matching:
            key = r.root_cause_type.value
            if key not in causes:
                causes[key] = []
            causes[key].append(r.confidence_score)
        result = []
        for cause, scores in causes.items():
            avg = round(sum(scores) / len(scores), 4)
            result.append(
                {
                    "cause_type": cause,
                    "avg_confidence": avg,
                    "signal_count": len(scores),
                }
            )
        return sorted(
            result,
            key=lambda x: x["avg_confidence"],
            reverse=True,
        )

    def build_causal_graph(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        edges: dict[str, set[str]] = {}
        for r in matching:
            src = r.signal_type or "unknown"
            tgt = r.root_cause_type.value
            if src not in edges:
                edges[src] = set()
            edges[src].add(tgt)
        graph = {k: list(v) for k, v in edges.items()}
        return {
            "service": service,
            "nodes": len(edges),
            "edges": graph,
        }

    def rank_hypotheses(self, incident_id: str, top_n: int = 5) -> list[dict[str, Any]]:
        matching = [r for r in self._records if r.incident_id == incident_id]
        if not matching:
            return []
        ranked = sorted(
            matching,
            key=lambda r: r.confidence_score,
            reverse=True,
        )
        return [
            {
                "root_cause_type": r.root_cause_type.value,
                "service": r.service,
                "confidence_score": r.confidence_score,
                "signals": r.contributing_signals,
            }
            for r in ranked[:top_n]
        ]

    def process(self, incident_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.incident_id == incident_id]
        if not matching:
            return {
                "incident_id": incident_id,
                "status": "no_data",
            }
        scores = [r.confidence_score for r in matching]
        avg_conf = round(sum(scores) / len(scores), 4) if scores else 0.0
        res_times = [r.resolution_time_minutes for r in matching if r.resolution_time_minutes > 0]
        avg_res = round(sum(res_times) / len(res_times), 2) if res_times else 0.0
        return {
            "incident_id": incident_id,
            "record_count": len(matching),
            "avg_confidence": avg_conf,
            "avg_resolution_minutes": avg_res,
            "top_cause": matching[0].root_cause_type.value if matching else "",
        }

    def generate_report(self) -> RootCauseReport:
        by_cause: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        for r in self._records:
            ct = r.root_cause_type.value
            by_cause[ct] = by_cause.get(ct, 0) + 1
            cm = r.correlation_method.value
            by_method[cm] = by_method.get(cm, 0) + 1
            cl = (
                "high"
                if r.confidence_score >= 0.7
                else "medium"
                if r.confidence_score >= 0.4
                else "low"
            )
            by_conf[cl] = by_conf.get(cl, 0) + 1
        scores = [r.confidence_score for r in self._records]
        avg_conf = round(sum(scores) / len(scores), 4) if scores else 0.0
        res_times = [
            r.resolution_time_minutes for r in self._records if r.resolution_time_minutes > 0
        ]
        avg_res = round(sum(res_times) / len(res_times), 2) if res_times else 0.0
        recs: list[str] = []
        low_conf = by_conf.get("low", 0)
        total = len(self._records)
        if total > 0 and low_conf / total > 0.3:
            recs.append("Over 30% of analyses have low confidence — improve signal quality")
        if avg_res > 60:
            recs.append(f"Avg resolution {avg_res:.0f}min — automate common root causes")
        if not recs:
            recs.append("Root cause analysis performance is nominal")
        return RootCauseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_confidence=avg_conf,
            avg_resolution_minutes=avg_res,
            by_cause_type=by_cause,
            by_method=by_method,
            by_confidence=by_conf,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cause_dist: dict[str, int] = {}
        for r in self._records:
            k = r.root_cause_type.value
            cause_dist[k] = cause_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "confidence_threshold": (self._confidence_threshold),
            "cause_distribution": cause_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("aiops_root_cause_engine.cleared")
        return {"status": "cleared"}
