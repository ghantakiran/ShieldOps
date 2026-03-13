"""Message Queue Health Analyzer —
compute queue health scores, detect saturation,
rank queues by processing risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QueueType(StrEnum):
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    SQS = "sqs"
    PUBSUB = "pubsub"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class SaturationLevel(StrEnum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    CRITICAL = "critical"


# --- Models ---


class QueueHealthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = ""
    queue_type: QueueType = QueueType.KAFKA
    health_status: HealthStatus = HealthStatus.HEALTHY
    saturation_level: SaturationLevel = SaturationLevel.SAFE
    depth: int = 0
    throughput: float = 0.0
    error_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class QueueHealthAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = ""
    queue_type: QueueType = QueueType.KAFKA
    health_score: float = 0.0
    saturation_pct: float = 0.0
    processing_risk: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class QueueHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_health_score: float = 0.0
    by_queue_type: dict[str, int] = Field(default_factory=dict)
    by_health_status: dict[str, int] = Field(default_factory=dict)
    by_saturation: dict[str, int] = Field(default_factory=dict)
    critical_queues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MessageQueueHealthAnalyzer:
    """Compute queue health scores, detect saturation,
    rank queues by processing risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[QueueHealthRecord] = []
        self._analyses: dict[str, QueueHealthAnalysis] = {}
        logger.info(
            "message_queue_health_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        queue_name: str = "",
        queue_type: QueueType = QueueType.KAFKA,
        health_status: HealthStatus = (HealthStatus.HEALTHY),
        saturation_level: SaturationLevel = (SaturationLevel.SAFE),
        depth: int = 0,
        throughput: float = 0.0,
        error_rate: float = 0.0,
        description: str = "",
    ) -> QueueHealthRecord:
        record = QueueHealthRecord(
            queue_name=queue_name,
            queue_type=queue_type,
            health_status=health_status,
            saturation_level=saturation_level,
            depth=depth,
            throughput=throughput,
            error_rate=error_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "queue_health.record_added",
            record_id=record.id,
            queue_name=queue_name,
        )
        return record

    def process(self, key: str) -> QueueHealthAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        health_score = round(100.0 - rec.error_rate * 100, 2)
        sat_pct = min(round(rec.depth / 10000 * 100, 2), 100.0)
        risk = round(rec.error_rate * 50 + sat_pct, 2)
        analysis = QueueHealthAnalysis(
            queue_name=rec.queue_name,
            queue_type=rec.queue_type,
            health_score=health_score,
            saturation_pct=sat_pct,
            processing_risk=risk,
            description=(f"Queue {rec.queue_name} health {health_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> QueueHealthReport:
        by_qt: dict[str, int] = {}
        by_hs: dict[str, int] = {}
        by_sat: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.queue_type.value
            by_qt[k] = by_qt.get(k, 0) + 1
            k2 = r.health_status.value
            by_hs[k2] = by_hs.get(k2, 0) + 1
            k3 = r.saturation_level.value
            by_sat[k3] = by_sat.get(k3, 0) + 1
            scores.append(100.0 - r.error_rate * 100)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        crit = list(
            {
                r.queue_name
                for r in self._records
                if r.health_status
                in (
                    HealthStatus.CRITICAL,
                    HealthStatus.DEGRADED,
                )
            }
        )[:10]
        recs: list[str] = []
        if crit:
            recs.append(f"{len(crit)} critical queues detected")
        if not recs:
            recs.append("All queues healthy")
        return QueueHealthReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_health_score=avg,
            by_queue_type=by_qt,
            by_health_status=by_hs,
            by_saturation=by_sat,
            critical_queues=crit,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        qt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.queue_type.value
            qt_dist[k] = qt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "queue_type_distribution": qt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("message_queue_health_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_queue_health_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute health score per queue."""
        queue_errs: dict[str, list[float]] = {}
        queue_types: dict[str, str] = {}
        for r in self._records:
            queue_errs.setdefault(r.queue_name, []).append(r.error_rate)
            queue_types[r.queue_name] = r.queue_type.value
        results: list[dict[str, Any]] = []
        for qn, errs in queue_errs.items():
            avg_err = sum(errs) / len(errs)
            score = round(100.0 - avg_err * 100, 2)
            results.append(
                {
                    "queue_name": qn,
                    "queue_type": queue_types[qn],
                    "health_score": score,
                    "avg_error_rate": round(avg_err, 4),
                    "sample_count": len(errs),
                }
            )
        results.sort(
            key=lambda x: x["health_score"],
            reverse=True,
        )
        return results

    def detect_queue_saturation(
        self,
    ) -> list[dict[str, Any]]:
        """Detect queues with saturation issues."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.saturation_level
                in (
                    SaturationLevel.DANGER,
                    SaturationLevel.CRITICAL,
                )
                and r.queue_name not in seen
            ):
                seen.add(r.queue_name)
                results.append(
                    {
                        "queue_name": r.queue_name,
                        "queue_type": (r.queue_type.value),
                        "saturation": (r.saturation_level.value),
                        "depth": r.depth,
                        "throughput": r.throughput,
                    }
                )
        results.sort(
            key=lambda x: x["depth"],
            reverse=True,
        )
        return results

    def rank_queues_by_processing_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank queues by processing risk."""
        queue_risk: dict[str, float] = {}
        queue_types: dict[str, str] = {}
        for r in self._records:
            risk = r.error_rate * 50 + r.depth / 200
            queue_risk[r.queue_name] = queue_risk.get(r.queue_name, 0.0) + risk
            queue_types[r.queue_name] = r.queue_type.value
        results: list[dict[str, Any]] = []
        for qn, risk in queue_risk.items():
            results.append(
                {
                    "queue_name": qn,
                    "queue_type": queue_types[qn],
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
