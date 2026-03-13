"""Event Processing Latency Profiler —
profile end-to-end latency, detect outliers,
rank pipelines by latency risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProcessingStage(StrEnum):
    INGESTION = "ingestion"
    PROCESSING = "processing"
    ENRICHMENT = "enrichment"
    DELIVERY = "delivery"


class LatencyProfile(StrEnum):
    REALTIME = "realtime"
    NEAR_REALTIME = "near_realtime"
    BATCH = "batch"
    DELAYED = "delayed"


class OutlierType(StrEnum):
    SPIKE = "spike"
    SUSTAINED = "sustained"
    PERIODIC = "periodic"
    RANDOM = "random"


# --- Models ---


class LatencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    processing_stage: ProcessingStage = ProcessingStage.PROCESSING
    latency_profile: LatencyProfile = LatencyProfile.NEAR_REALTIME
    outlier_type: OutlierType = OutlierType.RANDOM
    latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    throughput: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LatencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    processing_stage: ProcessingStage = ProcessingStage.PROCESSING
    avg_latency_ms: float = 0.0
    outlier_detected: bool = False
    latency_risk: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LatencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_latency: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_profile: dict[str, int] = Field(default_factory=dict)
    by_outlier: dict[str, int] = Field(default_factory=dict)
    high_latency_pipelines: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventProcessingLatencyProfiler:
    """Profile end-to-end latency, detect outliers,
    rank pipelines by latency risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[LatencyRecord] = []
        self._analyses: dict[str, LatencyAnalysis] = {}
        logger.info(
            "event_processing_latency_profiler.init",
            max_records=max_records,
        )

    def add_record(
        self,
        pipeline_id: str = "",
        processing_stage: ProcessingStage = (ProcessingStage.PROCESSING),
        latency_profile: LatencyProfile = (LatencyProfile.NEAR_REALTIME),
        outlier_type: OutlierType = OutlierType.RANDOM,
        latency_ms: float = 0.0,
        p99_latency_ms: float = 0.0,
        throughput: float = 0.0,
        description: str = "",
    ) -> LatencyRecord:
        record = LatencyRecord(
            pipeline_id=pipeline_id,
            processing_stage=processing_stage,
            latency_profile=latency_profile,
            outlier_type=outlier_type,
            latency_ms=latency_ms,
            p99_latency_ms=p99_latency_ms,
            throughput=throughput,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "latency_profiler.record_added",
            record_id=record.id,
            pipeline_id=pipeline_id,
        )
        return record

    def process(self, key: str) -> LatencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        outlier = rec.p99_latency_ms > rec.latency_ms * 3
        risk = round(
            rec.latency_ms * 0.01 + rec.p99_latency_ms * 0.005,
            2,
        )
        analysis = LatencyAnalysis(
            pipeline_id=rec.pipeline_id,
            processing_stage=rec.processing_stage,
            avg_latency_ms=round(rec.latency_ms, 2),
            outlier_detected=outlier,
            latency_risk=risk,
            description=(f"Pipeline {rec.pipeline_id} latency {rec.latency_ms}ms"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> LatencyReport:
        by_s: dict[str, int] = {}
        by_p: dict[str, int] = {}
        by_o: dict[str, int] = {}
        lats: list[float] = []
        for r in self._records:
            k = r.processing_stage.value
            by_s[k] = by_s.get(k, 0) + 1
            k2 = r.latency_profile.value
            by_p[k2] = by_p.get(k2, 0) + 1
            k3 = r.outlier_type.value
            by_o[k3] = by_o.get(k3, 0) + 1
            lats.append(r.latency_ms)
        avg = round(sum(lats) / len(lats), 2) if lats else 0.0
        high_lat = list(
            {
                r.pipeline_id
                for r in self._records
                if r.latency_profile
                in (
                    LatencyProfile.BATCH,
                    LatencyProfile.DELAYED,
                )
            }
        )[:10]
        recs: list[str] = []
        if high_lat:
            recs.append(f"{len(high_lat)} high-latency pipelines")
        if not recs:
            recs.append("Latency within thresholds")
        return LatencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_latency=avg,
            by_stage=by_s,
            by_profile=by_p,
            by_outlier=by_o,
            high_latency_pipelines=high_lat,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        s_dist: dict[str, int] = {}
        for r in self._records:
            k = r.processing_stage.value
            s_dist[k] = s_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "stage_distribution": s_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("event_processing_latency_profiler.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def profile_end_to_end_latency(
        self,
    ) -> list[dict[str, Any]]:
        """Profile end-to-end latency per pipeline."""
        pipe_data: dict[str, list[float]] = {}
        pipe_p99: dict[str, list[float]] = {}
        for r in self._records:
            pipe_data.setdefault(r.pipeline_id, []).append(r.latency_ms)
            pipe_p99.setdefault(r.pipeline_id, []).append(r.p99_latency_ms)
        results: list[dict[str, Any]] = []
        for pid, lats in pipe_data.items():
            avg = round(sum(lats) / len(lats), 2)
            p99_avg = round(
                sum(pipe_p99[pid]) / len(pipe_p99[pid]),
                2,
            )
            results.append(
                {
                    "pipeline_id": pid,
                    "avg_latency_ms": avg,
                    "avg_p99_ms": p99_avg,
                    "max_latency_ms": round(max(lats), 2),
                    "samples": len(lats),
                }
            )
        results.sort(
            key=lambda x: x["avg_latency_ms"],
            reverse=True,
        )
        return results

    def detect_latency_outliers(
        self,
    ) -> list[dict[str, Any]]:
        """Detect latency outliers."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.p99_latency_ms > r.latency_ms * 3 and r.pipeline_id not in seen:
                seen.add(r.pipeline_id)
                results.append(
                    {
                        "pipeline_id": (r.pipeline_id),
                        "outlier_type": (r.outlier_type.value),
                        "latency_ms": r.latency_ms,
                        "p99_latency_ms": (r.p99_latency_ms),
                        "ratio": round(
                            r.p99_latency_ms / max(r.latency_ms, 0.01),
                            2,
                        ),
                    }
                )
        results.sort(
            key=lambda x: x["p99_latency_ms"],
            reverse=True,
        )
        return results

    def rank_pipelines_by_latency_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank pipelines by latency risk."""
        pipe_risk: dict[str, float] = {}
        for r in self._records:
            risk = r.latency_ms * 0.01 + r.p99_latency_ms * 0.005
            pipe_risk[r.pipeline_id] = pipe_risk.get(r.pipeline_id, 0.0) + risk
        results: list[dict[str, Any]] = []
        for pid, risk in pipe_risk.items():
            results.append(
                {
                    "pipeline_id": pid,
                    "risk_score": round(risk, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
