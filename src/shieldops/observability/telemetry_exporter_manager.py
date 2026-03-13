"""TelemetryExporterManager — telemetry exporter management."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExporterType(StrEnum):
    OTLP_GRPC = "otlp_grpc"
    OTLP_HTTP = "otlp_http"
    SPLUNK_HEC = "splunk_hec"
    PROMETHEUS = "prometheus"


class ExporterStatus(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"


class ExportProtocol(StrEnum):
    GRPC = "grpc"
    HTTP = "http"
    TCP = "tcp"
    UDP = "udp"


# --- Models ---


class TelemetryExporterManagerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    exporter_type: ExporterType = ExporterType.OTLP_GRPC
    exporter_status: ExporterStatus = ExporterStatus.ACTIVE
    export_protocol: ExportProtocol = ExportProtocol.GRPC
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetryExporterManagerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    exporter_type: ExporterType = ExporterType.OTLP_GRPC
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetryExporterManagerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_exporter_type: dict[str, int] = Field(default_factory=dict)
    by_exporter_status: dict[str, int] = Field(default_factory=dict)
    by_export_protocol: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetryExporterManager:
    """Telemetry exporter management engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TelemetryExporterManagerRecord] = []
        self._analyses: list[TelemetryExporterManagerAnalysis] = []
        logger.info(
            "telemetry.exporter.manager.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        exporter_type: ExporterType = (ExporterType.OTLP_GRPC),
        exporter_status: ExporterStatus = (ExporterStatus.ACTIVE),
        export_protocol: ExportProtocol = (ExportProtocol.GRPC),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TelemetryExporterManagerRecord:
        record = TelemetryExporterManagerRecord(
            name=name,
            exporter_type=exporter_type,
            exporter_status=exporter_status,
            export_protocol=export_protocol,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry.exporter.manager.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = TelemetryExporterManagerAnalysis(
                    name=r.name,
                    exporter_type=r.exporter_type,
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def evaluate_exporter_health(
        self,
    ) -> dict[str, Any]:
        """Evaluate health per exporter type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.exporter_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in type_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def compute_export_latency(
        self,
    ) -> list[dict[str, Any]]:
        """Compute export latency per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_latency": avg,
                }
            )
        results.sort(key=lambda x: x["avg_latency"])
        return results

    def detect_data_loss(self) -> list[dict[str, Any]]:
        """Detect exporters with potential data loss."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.exporter_status == ExporterStatus.FAILED:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "exporter_type": (r.exporter_type.value),
                        "service": r.service,
                        "score": r.score,
                    }
                )
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> TelemetryExporterManagerReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.exporter_type.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.exporter_status.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.export_protocol.value
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
            recs.append("Telemetry Exporter Manager is healthy")
        return TelemetryExporterManagerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_exporter_type=by_e1,
            by_exporter_status=by_e2,
            by_export_protocol=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("telemetry.exporter.manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.exporter_type.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "exporter_type_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
