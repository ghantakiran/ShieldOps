"""Service Mesh Latency Profiler.

Profile hop latency, identify proxy overhead,
and detect latency regressions in service meshes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LatencySource(StrEnum):
    APPLICATION = "application"
    PROXY = "proxy"
    NETWORK = "network"
    QUEUE = "queue"


class HopType(StrEnum):
    INGRESS = "ingress"
    SERVICE_TO_SERVICE = "service_to_service"
    EGRESS = "egress"
    EXTERNAL = "external"


class RegressionSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


# --- Models ---


class MeshLatencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    hop_name: str = ""
    latency_source: LatencySource = LatencySource.APPLICATION
    hop_type: HopType = HopType.SERVICE_TO_SERVICE
    regression_severity: RegressionSeverity = RegressionSeverity.NEGLIGIBLE
    latency_ms: float = 0.0
    baseline_ms: float = 0.0
    proxy_overhead_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class MeshLatencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    hop_name: str = ""
    has_regression: bool = False
    overhead_pct: float = 0.0
    delta_ms: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MeshLatencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_latency_ms: float = 0.0
    by_latency_source: dict[str, int] = Field(default_factory=dict)
    by_hop_type: dict[str, int] = Field(default_factory=dict)
    by_regression_severity: dict[str, int] = Field(default_factory=dict)
    regression_hops: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceMeshLatencyProfiler:
    """Profile hop latency, identify proxy overhead,
    detect latency regressions."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MeshLatencyRecord] = []
        self._analyses: dict[str, MeshLatencyAnalysis] = {}
        logger.info(
            "service_mesh_latency_profiler.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service: str = "",
        hop_name: str = "",
        latency_source: LatencySource = (LatencySource.APPLICATION),
        hop_type: HopType = (HopType.SERVICE_TO_SERVICE),
        regression_severity: RegressionSeverity = (RegressionSeverity.NEGLIGIBLE),
        latency_ms: float = 0.0,
        baseline_ms: float = 0.0,
        proxy_overhead_ms: float = 0.0,
    ) -> MeshLatencyRecord:
        record = MeshLatencyRecord(
            service=service,
            hop_name=hop_name,
            latency_source=latency_source,
            hop_type=hop_type,
            regression_severity=regression_severity,
            latency_ms=latency_ms,
            baseline_ms=baseline_ms,
            proxy_overhead_ms=proxy_overhead_ms,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mesh_latency.record_added",
            record_id=record.id,
            service=service,
        )
        return record

    def process(self, key: str) -> MeshLatencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        has_reg = rec.regression_severity in (
            RegressionSeverity.CRITICAL,
            RegressionSeverity.MAJOR,
        )
        delta = round(rec.latency_ms - rec.baseline_ms, 2)
        overhead_pct = (
            round(
                rec.proxy_overhead_ms / max(rec.latency_ms, 0.01) * 100,
                2,
            )
            if rec.latency_ms > 0
            else 0.0
        )
        analysis = MeshLatencyAnalysis(
            service=rec.service,
            hop_name=rec.hop_name,
            has_regression=has_reg,
            overhead_pct=overhead_pct,
            delta_ms=delta,
            description=(f"Hop {rec.hop_name} latency {rec.latency_ms}ms"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MeshLatencyReport:
        by_ls: dict[str, int] = {}
        by_ht: dict[str, int] = {}
        by_rs: dict[str, int] = {}
        lats: list[float] = []
        for r in self._records:
            k = r.latency_source.value
            by_ls[k] = by_ls.get(k, 0) + 1
            k2 = r.hop_type.value
            by_ht[k2] = by_ht.get(k2, 0) + 1
            k3 = r.regression_severity.value
            by_rs[k3] = by_rs.get(k3, 0) + 1
            lats.append(r.latency_ms)
        avg = round(sum(lats) / len(lats), 2) if lats else 0.0
        reg_hops = list(
            {
                r.hop_name
                for r in self._records
                if r.regression_severity
                in (
                    RegressionSeverity.CRITICAL,
                    RegressionSeverity.MAJOR,
                )
            }
        )[:10]
        recs: list[str] = []
        if reg_hops:
            recs.append(f"{len(reg_hops)} hops with regressions")
        if not recs:
            recs.append("No latency regressions")
        return MeshLatencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_latency_ms=avg,
            by_latency_source=by_ls,
            by_hop_type=by_ht,
            by_regression_severity=by_rs,
            regression_hops=reg_hops,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.latency_source.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "latency_source_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("service_mesh_latency_profiler.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def profile_hop_latency(
        self,
    ) -> list[dict[str, Any]]:
        """Profile latency per hop."""
        hop_lats: dict[str, list[float]] = {}
        hop_svc: dict[str, str] = {}
        for r in self._records:
            hop_lats.setdefault(r.hop_name, []).append(r.latency_ms)
            hop_svc[r.hop_name] = r.service
        results: list[dict[str, Any]] = []
        for hop, lats in hop_lats.items():
            avg = round(sum(lats) / len(lats), 2)
            p99 = round(
                sorted(lats)[int(len(lats) * 0.99)] if lats else 0.0,
                2,
            )
            results.append(
                {
                    "hop_name": hop,
                    "service": hop_svc[hop],
                    "avg_latency_ms": avg,
                    "p99_latency_ms": p99,
                    "sample_count": len(lats),
                }
            )
        results.sort(
            key=lambda x: x["avg_latency_ms"],
            reverse=True,
        )
        return results

    def identify_proxy_overhead(
        self,
    ) -> list[dict[str, Any]]:
        """Identify proxy overhead per service."""
        svc_overhead: dict[str, list[float]] = {}
        for r in self._records:
            svc_overhead.setdefault(r.service, []).append(r.proxy_overhead_ms)
        results: list[dict[str, Any]] = []
        for svc, overheads in svc_overhead.items():
            avg = round(sum(overheads) / len(overheads), 2)
            results.append(
                {
                    "service": svc,
                    "avg_overhead_ms": avg,
                    "max_overhead_ms": round(max(overheads), 2),
                    "sample_count": len(overheads),
                }
            )
        results.sort(
            key=lambda x: x["avg_overhead_ms"],
            reverse=True,
        )
        return results

    def detect_latency_regression(
        self,
    ) -> list[dict[str, Any]]:
        """Detect latency regressions."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.regression_severity
                in (
                    RegressionSeverity.CRITICAL,
                    RegressionSeverity.MAJOR,
                )
                and r.hop_name not in seen
            ):
                seen.add(r.hop_name)
                delta = round(r.latency_ms - r.baseline_ms, 2)
                results.append(
                    {
                        "hop_name": r.hop_name,
                        "service": r.service,
                        "severity": (r.regression_severity.value),
                        "latency_ms": r.latency_ms,
                        "baseline_ms": r.baseline_ms,
                        "delta_ms": delta,
                    }
                )
        results.sort(
            key=lambda x: x["delta_ms"],
            reverse=True,
        )
        return results
