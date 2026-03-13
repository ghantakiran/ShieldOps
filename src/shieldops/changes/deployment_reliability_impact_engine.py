"""Deployment Reliability Impact Engine
compute deployment reliability delta, detect reliability
degrading deploys, rank deployments by reliability impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReliabilityImpact(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    SEVERE = "severe"


class DeploymentType(StrEnum):
    STANDARD = "standard"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"


class ImpactWindow(StrEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


# --- Models ---


class DeploymentReliabilityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    reliability_impact: ReliabilityImpact = ReliabilityImpact.NEUTRAL
    deployment_type: DeploymentType = DeploymentType.STANDARD
    impact_window: ImpactWindow = ImpactWindow.IMMEDIATE
    pre_deploy_score: float = 0.0
    post_deploy_score: float = 0.0
    delta: float = 0.0
    service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentReliabilityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    reliability_delta: float = 0.0
    reliability_impact: ReliabilityImpact = ReliabilityImpact.NEUTRAL
    degrading: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentReliabilityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_delta: float = 0.0
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_deployment_type: dict[str, int] = Field(default_factory=dict)
    by_impact_window: dict[str, int] = Field(default_factory=dict)
    degrading_deployments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentReliabilityImpactEngine:
    """Compute deployment reliability delta, detect
    reliability degrading deploys, rank by impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DeploymentReliabilityRecord] = []
        self._analyses: dict[str, DeploymentReliabilityAnalysis] = {}
        logger.info(
            "deployment_reliability_impact_engine.init",
            max_records=max_records,
        )

    def record_item(
        self,
        deployment_id: str = "",
        reliability_impact: ReliabilityImpact = ReliabilityImpact.NEUTRAL,
        deployment_type: DeploymentType = DeploymentType.STANDARD,
        impact_window: ImpactWindow = ImpactWindow.IMMEDIATE,
        pre_deploy_score: float = 0.0,
        post_deploy_score: float = 0.0,
        delta: float = 0.0,
        service: str = "",
        description: str = "",
    ) -> DeploymentReliabilityRecord:
        record = DeploymentReliabilityRecord(
            deployment_id=deployment_id,
            reliability_impact=reliability_impact,
            deployment_type=deployment_type,
            impact_window=impact_window,
            pre_deploy_score=pre_deploy_score,
            post_deploy_score=post_deploy_score,
            delta=delta,
            service=service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deployment_reliability_impact_engine.record_added",
            record_id=record.id,
            deployment_id=deployment_id,
        )
        return record

    def process(self, key: str) -> DeploymentReliabilityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.deployment_id == rec.deployment_id)
        degrading = rec.reliability_impact in (
            ReliabilityImpact.NEGATIVE,
            ReliabilityImpact.SEVERE,
        )
        analysis = DeploymentReliabilityAnalysis(
            deployment_id=rec.deployment_id,
            reliability_delta=round(rec.delta, 2),
            reliability_impact=rec.reliability_impact,
            degrading=degrading,
            data_points=points,
            description=f"Deployment {rec.deployment_id} delta {rec.delta}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> DeploymentReliabilityReport:
        by_i: dict[str, int] = {}
        by_dt: dict[str, int] = {}
        by_iw: dict[str, int] = {}
        deltas: list[float] = []
        for r in self._records:
            k = r.reliability_impact.value
            by_i[k] = by_i.get(k, 0) + 1
            k2 = r.deployment_type.value
            by_dt[k2] = by_dt.get(k2, 0) + 1
            k3 = r.impact_window.value
            by_iw[k3] = by_iw.get(k3, 0) + 1
            deltas.append(r.delta)
        avg = round(sum(deltas) / len(deltas), 2) if deltas else 0.0
        degrading = list(
            {
                r.deployment_id
                for r in self._records
                if r.reliability_impact in (ReliabilityImpact.NEGATIVE, ReliabilityImpact.SEVERE)
            }
        )[:10]
        recs: list[str] = []
        if degrading:
            recs.append(f"{len(degrading)} deployments degraded reliability")
        if not recs:
            recs.append("No reliability-degrading deployments detected")
        return DeploymentReliabilityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_delta=avg,
            by_impact=by_i,
            by_deployment_type=by_dt,
            by_impact_window=by_iw,
            degrading_deployments=degrading,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        impact_dist: dict[str, int] = {}
        for r in self._records:
            k = r.reliability_impact.value
            impact_dist[k] = impact_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "impact_distribution": impact_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("deployment_reliability_impact_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_deployment_reliability_delta(
        self,
    ) -> list[dict[str, Any]]:
        """Compute reliability delta per deployment."""
        dep_data: dict[str, list[float]] = {}
        dep_types: dict[str, str] = {}
        for r in self._records:
            dep_data.setdefault(r.deployment_id, []).append(r.delta)
            dep_types[r.deployment_id] = r.deployment_type.value
        results: list[dict[str, Any]] = []
        for did, deltas in dep_data.items():
            avg = round(sum(deltas) / len(deltas), 2)
            results.append(
                {
                    "deployment_id": did,
                    "deployment_type": dep_types[did],
                    "avg_delta": avg,
                    "data_points": len(deltas),
                }
            )
        results.sort(key=lambda x: x["avg_delta"])
        return results

    def detect_reliability_degrading_deploys(
        self,
    ) -> list[dict[str, Any]]:
        """Detect deployments that degraded reliability."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.reliability_impact in (ReliabilityImpact.NEGATIVE, ReliabilityImpact.SEVERE)
                and r.deployment_id not in seen
            ):
                seen.add(r.deployment_id)
                results.append(
                    {
                        "deployment_id": r.deployment_id,
                        "deployment_type": r.deployment_type.value,
                        "delta": r.delta,
                        "impact": r.reliability_impact.value,
                    }
                )
        results.sort(key=lambda x: x["delta"])
        return results

    def rank_deployments_by_reliability_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all deployments by reliability impact."""
        dep_data: dict[str, float] = {}
        dep_types: dict[str, str] = {}
        for r in self._records:
            dep_data[r.deployment_id] = dep_data.get(r.deployment_id, 0.0) + r.delta
            dep_types[r.deployment_id] = r.deployment_type.value
        results: list[dict[str, Any]] = []
        for did, total in dep_data.items():
            results.append(
                {
                    "deployment_id": did,
                    "deployment_type": dep_types[did],
                    "aggregate_delta": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["aggregate_delta"])
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
