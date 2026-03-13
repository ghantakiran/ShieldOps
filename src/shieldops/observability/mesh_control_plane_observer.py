"""Mesh Control Plane Observer.

Monitor config propagation, assess control plane health,
and detect sync divergence in service meshes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PropagationStatus(StrEnum):
    CONVERGED = "converged"
    PROPAGATING = "propagating"
    STALE = "stale"
    FAILED = "failed"


class ControlPlaneHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class SyncState(StrEnum):
    IN_SYNC = "in_sync"
    LAGGING = "lagging"
    DIVERGED = "diverged"
    DISCONNECTED = "disconnected"


# --- Models ---


class ControlPlaneRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mesh_name: str = ""
    component: str = ""
    propagation_status: PropagationStatus = PropagationStatus.CONVERGED
    control_plane_health: ControlPlaneHealth = ControlPlaneHealth.HEALTHY
    sync_state: SyncState = SyncState.IN_SYNC
    config_version: str = ""
    latency_ms: float = 0.0
    node_count: int = 0
    created_at: float = Field(default_factory=time.time)


class ControlPlaneAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mesh_name: str = ""
    component: str = ""
    is_healthy: bool = True
    is_diverged: bool = False
    propagation_lag_ms: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlPlaneReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_latency_ms: float = 0.0
    by_propagation_status: dict[str, int] = Field(default_factory=dict)
    by_control_plane_health: dict[str, int] = Field(default_factory=dict)
    by_sync_state: dict[str, int] = Field(default_factory=dict)
    unhealthy_components: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MeshControlPlaneObserver:
    """Monitor config propagation, assess control plane
    health, detect sync divergence."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ControlPlaneRecord] = []
        self._analyses: dict[str, ControlPlaneAnalysis] = {}
        logger.info(
            "mesh_control_plane_observer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        mesh_name: str = "",
        component: str = "",
        propagation_status: PropagationStatus = (PropagationStatus.CONVERGED),
        control_plane_health: ControlPlaneHealth = (ControlPlaneHealth.HEALTHY),
        sync_state: SyncState = SyncState.IN_SYNC,
        config_version: str = "",
        latency_ms: float = 0.0,
        node_count: int = 0,
    ) -> ControlPlaneRecord:
        record = ControlPlaneRecord(
            mesh_name=mesh_name,
            component=component,
            propagation_status=propagation_status,
            control_plane_health=control_plane_health,
            sync_state=sync_state,
            config_version=config_version,
            latency_ms=latency_ms,
            node_count=node_count,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "control_plane.record_added",
            record_id=record.id,
            mesh_name=mesh_name,
        )
        return record

    def process(self, key: str) -> ControlPlaneAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        healthy = rec.control_plane_health == ControlPlaneHealth.HEALTHY
        diverged = rec.sync_state in (
            SyncState.DIVERGED,
            SyncState.DISCONNECTED,
        )
        analysis = ControlPlaneAnalysis(
            mesh_name=rec.mesh_name,
            component=rec.component,
            is_healthy=healthy,
            is_diverged=diverged,
            propagation_lag_ms=round(rec.latency_ms, 2),
            description=(f"Mesh {rec.mesh_name} component {rec.component} lag {rec.latency_ms}ms"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ControlPlaneReport:
        by_ps: dict[str, int] = {}
        by_ch: dict[str, int] = {}
        by_ss: dict[str, int] = {}
        lats: list[float] = []
        for r in self._records:
            k = r.propagation_status.value
            by_ps[k] = by_ps.get(k, 0) + 1
            k2 = r.control_plane_health.value
            by_ch[k2] = by_ch.get(k2, 0) + 1
            k3 = r.sync_state.value
            by_ss[k3] = by_ss.get(k3, 0) + 1
            lats.append(r.latency_ms)
        avg = round(sum(lats) / len(lats), 2) if lats else 0.0
        unhealthy = list(
            {
                r.component
                for r in self._records
                if r.control_plane_health
                in (
                    ControlPlaneHealth.DEGRADED,
                    ControlPlaneHealth.CRITICAL,
                )
            }
        )[:10]
        recs: list[str] = []
        if unhealthy:
            recs.append(f"{len(unhealthy)} unhealthy components")
        if not recs:
            recs.append("Control plane healthy")
        return ControlPlaneReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_latency_ms=avg,
            by_propagation_status=by_ps,
            by_control_plane_health=by_ch,
            by_sync_state=by_ss,
            unhealthy_components=unhealthy,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.control_plane_health.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "health_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("mesh_control_plane_observer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def monitor_config_propagation(
        self,
    ) -> list[dict[str, Any]]:
        """Monitor config propagation status."""
        comp_data: dict[str, list[float]] = {}
        comp_status: dict[str, str] = {}
        for r in self._records:
            comp_data.setdefault(r.component, []).append(r.latency_ms)
            comp_status[r.component] = r.propagation_status.value
        results: list[dict[str, Any]] = []
        for comp, lats in comp_data.items():
            avg = round(sum(lats) / len(lats), 2)
            results.append(
                {
                    "component": comp,
                    "status": comp_status[comp],
                    "avg_latency_ms": avg,
                    "sample_count": len(lats),
                }
            )
        results.sort(
            key=lambda x: x["avg_latency_ms"],
            reverse=True,
        )
        return results

    def assess_control_plane_health(
        self,
    ) -> list[dict[str, Any]]:
        """Assess health per mesh."""
        mesh_health: dict[str, dict[str, int]] = {}
        for r in self._records:
            mesh_health.setdefault(r.mesh_name, {})
            h = r.control_plane_health.value
            mesh_health[r.mesh_name][h] = mesh_health[r.mesh_name].get(h, 0) + 1
        results: list[dict[str, Any]] = []
        for mesh, health in mesh_health.items():
            total = sum(health.values())
            healthy_pct = round(
                health.get("healthy", 0) / max(total, 1) * 100,
                2,
            )
            results.append(
                {
                    "mesh_name": mesh,
                    "healthy_pct": healthy_pct,
                    "health_counts": health,
                }
            )
        results.sort(
            key=lambda x: x["healthy_pct"],
            reverse=True,
        )
        return results

    def detect_sync_divergence(
        self,
    ) -> list[dict[str, Any]]:
        """Detect components with sync divergence."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.sync_state
                in (
                    SyncState.DIVERGED,
                    SyncState.DISCONNECTED,
                )
                and r.component not in seen
            ):
                seen.add(r.component)
                results.append(
                    {
                        "component": r.component,
                        "mesh_name": r.mesh_name,
                        "sync_state": (r.sync_state.value),
                        "latency_ms": r.latency_ms,
                    }
                )
        results.sort(
            key=lambda x: x["latency_ms"],
            reverse=True,
        )
        return results
