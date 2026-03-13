"""KafkaTelemetryPipeline — Kafka-OTel pipeline integration."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PipelineStage(StrEnum):
    RECEIVER = "receiver"
    PROCESSOR = "processor"
    EXPORTER = "exporter"


class MessageEncoding(StrEnum):
    JSON = "json"
    PROTOBUF = "protobuf"
    AVRO = "avro"
    TEXT = "text"


class PipelineHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BACKPRESSURE = "backpressure"
    FAILED = "failed"


# --- Models ---


class KafkaTelemetryPipelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.RECEIVER
    message_encoding: MessageEncoding = MessageEncoding.JSON
    pipeline_health: PipelineHealth = PipelineHealth.HEALTHY
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class KafkaTelemetryPipelineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.RECEIVER
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KafkaTelemetryPipelineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_pipeline_stage: dict[str, int] = Field(default_factory=dict)
    by_message_encoding: dict[str, int] = Field(default_factory=dict)
    by_pipeline_health: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KafkaTelemetryPipeline:
    """Kafka-OTel pipeline integration engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[KafkaTelemetryPipelineRecord] = []
        self._analyses: list[KafkaTelemetryPipelineAnalysis] = []
        logger.info(
            "kafka.telemetry.pipeline.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        pipeline_stage: PipelineStage = PipelineStage.RECEIVER,
        message_encoding: MessageEncoding = MessageEncoding.JSON,
        pipeline_health: PipelineHealth = PipelineHealth.HEALTHY,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> KafkaTelemetryPipelineRecord:
        record = KafkaTelemetryPipelineRecord(
            name=name,
            pipeline_stage=pipeline_stage,
            message_encoding=message_encoding,
            pipeline_health=pipeline_health,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "kafka.telemetry.pipeline.record_added",
            record_id=record.id,
            name=name,
            pipeline_stage=pipeline_stage.value,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = KafkaTelemetryPipelineAnalysis(
                    name=r.name,
                    pipeline_stage=r.pipeline_stage,
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=r.score < self._threshold,
                    description=f"Processed {r.name}",
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def compute_pipeline_throughput(self) -> dict[str, Any]:
        """Compute throughput per pipeline stage."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.pipeline_stage.value
            stage_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in stage_data.items():
            result[k] = {
                "count": len(scores),
                "avg_throughput": round(sum(scores) / len(scores), 2),
            }
        return result

    def detect_backpressure(self) -> list[dict[str, Any]]:
        """Detect pipelines experiencing backpressure."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pipeline_health == PipelineHealth.BACKPRESSURE:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "pipeline_stage": r.pipeline_stage.value,
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return results

    def optimize_batch_config(self) -> list[dict[str, Any]]:
        """Recommend batch configuration optimizations."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_score": avg,
                    "recommendation": (
                        "increase_batch_size" if avg < self._threshold else "optimal"
                    ),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    # -- report / stats ---

    def generate_report(self) -> KafkaTelemetryPipelineReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.pipeline_stage.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.message_encoding.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.pipeline_health.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Kafka Telemetry Pipeline is healthy")
        return KafkaTelemetryPipelineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_pipeline_stage=by_e1,
            by_message_encoding=by_e2,
            by_pipeline_health=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("kafka.telemetry.pipeline.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pipeline_stage.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "pipeline_stage_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
