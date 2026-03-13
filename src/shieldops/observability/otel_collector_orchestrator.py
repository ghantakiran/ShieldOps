"""OtelCollectorOrchestrator — collector deployment management."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CollectorMode(StrEnum):
    DAEMONSET = "daemonset"
    DEPLOYMENT = "deployment"
    SIDECAR = "sidecar"
    GATEWAY = "gateway"


class CollectorHealth(StrEnum):
    RUNNING = "running"
    DEGRADED = "degraded"
    CRASHED = "crashed"
    PENDING = "pending"


class ScalingPolicy(StrEnum):
    FIXED = "fixed"
    HPA = "hpa"
    VPA = "vpa"
    CUSTOM = "custom"


# --- Models ---


class OtelCollectorOrchestratorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    collector_mode: CollectorMode = CollectorMode.DAEMONSET
    collector_health: CollectorHealth = CollectorHealth.RUNNING
    scaling_policy: ScalingPolicy = ScalingPolicy.FIXED
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class OtelCollectorOrchestratorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    collector_mode: CollectorMode = CollectorMode.DAEMONSET
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OtelCollectorOrchestratorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_collector_mode: dict[str, int] = Field(default_factory=dict)
    by_collector_health: dict[str, int] = Field(default_factory=dict)
    by_scaling_policy: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OtelCollectorOrchestrator:
    """OTel collector deployment management engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[OtelCollectorOrchestratorRecord] = []
        self._analyses: list[OtelCollectorOrchestratorAnalysis] = []
        logger.info(
            "otel.collector.orchestrator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        collector_mode: CollectorMode = (CollectorMode.DAEMONSET),
        collector_health: CollectorHealth = (CollectorHealth.RUNNING),
        scaling_policy: ScalingPolicy = ScalingPolicy.FIXED,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> OtelCollectorOrchestratorRecord:
        record = OtelCollectorOrchestratorRecord(
            name=name,
            collector_mode=collector_mode,
            collector_health=collector_health,
            scaling_policy=scaling_policy,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "otel.collector.orchestrator.record_added",
            record_id=record.id,
            name=name,
            collector_mode=collector_mode.value,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = OtelCollectorOrchestratorAnalysis(
                    name=r.name,
                    collector_mode=r.collector_mode,
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

    def assess_collector_fleet(self) -> dict[str, Any]:
        """Assess health of the collector fleet."""
        health_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.collector_health.value
            health_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in health_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def detect_collector_gaps(self) -> list[dict[str, Any]]:
        """Detect collectors with gaps."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "collector_mode": (r.collector_mode.value),
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def recommend_scaling_action(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend scaling actions for collectors."""
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
                    "action": ("scale_up" if avg < self._threshold else "maintain"),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> OtelCollectorOrchestratorReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.collector_mode.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.collector_health.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.scaling_policy.value
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
            recs.append("OTel Collector Orchestrator is healthy")
        return OtelCollectorOrchestratorReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_collector_mode=by_e1,
            by_collector_health=by_e2,
            by_scaling_policy=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("otel.collector.orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.collector_mode.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "collector_mode_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
