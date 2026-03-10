"""HybridCloudTelemetryBridge — cross-cloud bridge."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CloudProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    ONPREM = "onprem"


class BridgeStatus(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    SYNCING = "syncing"


class NormalizationLevel(StrEnum):
    RAW = "raw"
    NORMALIZED = "normalized"
    ENRICHED = "enriched"


# --- Models ---


class BridgeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: CloudProvider = CloudProvider.AWS
    status: BridgeStatus = BridgeStatus.ACTIVE
    normalization: NormalizationLevel = NormalizationLevel.RAW
    score: float = 0.0
    sync_lag_ms: float = 0.0
    format_match_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BridgeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: CloudProvider = CloudProvider.AWS
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BridgeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    avg_sync_lag_ms: float = 0.0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_normalization: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class HybridCloudTelemetryBridge:
    """Hybrid Cloud Telemetry Bridge.

    Bridges telemetry across cloud providers
    and on-prem environments with format
    normalization and health monitoring.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[BridgeRecord] = []
        self._analyses: list[BridgeAnalysis] = []
        logger.info(
            "hybrid_cloud_telemetry_bridge.init",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        provider: CloudProvider = CloudProvider.AWS,
        status: BridgeStatus = BridgeStatus.ACTIVE,
        normalization: NormalizationLevel = (NormalizationLevel.RAW),
        score: float = 0.0,
        sync_lag_ms: float = 0.0,
        format_match_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BridgeRecord:
        record = BridgeRecord(
            name=name,
            provider=provider,
            status=status,
            normalization=normalization,
            score=score,
            sync_lag_ms=sync_lag_ms,
            format_match_pct=format_match_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "hybrid_cloud_telemetry_bridge.added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.name == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        scores = [r.score for r in matching]
        avg = round(sum(scores) / len(scores), 2)
        lags = [r.sync_lag_ms for r in matching]
        avg_lag = round(sum(lags) / len(lags), 2)
        return {
            "key": key,
            "record_count": len(matching),
            "avg_score": avg,
            "avg_sync_lag_ms": avg_lag,
        }

    def generate_report(self) -> BridgeReport:
        by_p: dict[str, int] = {}
        by_s: dict[str, int] = {}
        by_n: dict[str, int] = {}
        for r in self._records:
            v1 = r.provider.value
            by_p[v1] = by_p.get(v1, 0) + 1
            v2 = r.status.value
            by_s[v2] = by_s.get(v2, 0) + 1
            v3 = r.normalization.value
            by_n[v3] = by_n.get(v3, 0) + 1
        scores = [r.score for r in self._records]
        avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
        lags = [r.sync_lag_ms for r in self._records]
        avg_lag = round(sum(lags) / len(lags), 2) if lags else 0.0
        recs: list[str] = []
        offline = by_s.get("offline", 0)
        degraded = by_s.get("degraded", 0)
        if offline > 0:
            recs.append(f"{offline} bridge(s) offline")
        if degraded > 0:
            recs.append(f"{degraded} bridge(s) degraded")
        if not recs:
            recs.append("All bridges healthy")
        return BridgeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_s,
            avg_sync_lag_ms=avg_lag,
            by_provider=by_p,
            by_status=by_s,
            by_normalization=by_n,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        p_dist: dict[str, int] = {}
        for r in self._records:
            k = r.provider.value
            p_dist[k] = p_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "provider_distribution": p_dist,
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("hybrid_cloud_telemetry_bridge.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def detect_format_mismatches(
        self,
    ) -> list[dict[str, Any]]:
        """Detect format mismatches across clouds."""
        mismatches: list[dict[str, Any]] = []
        for r in self._records:
            if r.format_match_pct < 0.9:
                mismatches.append(
                    {
                        "name": r.name,
                        "provider": r.provider.value,
                        "service": r.service,
                        "format_match_pct": (r.format_match_pct),
                        "normalization": (r.normalization.value),
                        "gap": round(
                            1.0 - r.format_match_pct,
                            4,
                        ),
                    }
                )
        mismatches.sort(key=lambda x: x["format_match_pct"])
        return mismatches

    def compute_bridge_health(
        self,
    ) -> dict[str, Any]:
        """Compute health of each bridge."""
        if not self._records:
            return {"status": "no_data"}
        provider_health: dict[str, dict[str, Any]] = {}
        for r in self._records:
            pv = r.provider.value
            if pv not in provider_health:
                provider_health[pv] = {
                    "scores": [],
                    "lags": [],
                    "statuses": [],
                }
            provider_health[pv]["scores"].append(r.score)
            provider_health[pv]["lags"].append(r.sync_lag_ms)
            provider_health[pv]["statuses"].append(r.status.value)
        result: dict[str, Any] = {}
        for pv, data in provider_health.items():
            scores = data["scores"]
            lags = data["lags"]
            avg_s = round(sum(scores) / len(scores), 2)
            avg_l = round(sum(lags) / len(lags), 2)
            active_pct = round(
                data["statuses"].count("active") / len(data["statuses"]) * 100,
                1,
            )
            result[pv] = {
                "avg_score": avg_s,
                "avg_sync_lag_ms": avg_l,
                "active_pct": active_pct,
                "healthy": (avg_s >= self._threshold and active_pct >= 80),
            }
        return result

    def reconcile_cross_cloud_metrics(
        self,
    ) -> dict[str, Any]:
        """Reconcile metrics across clouds."""
        if not self._records:
            return {"status": "no_data"}
        svc_providers: dict[str, dict[str, list[float]]] = {}
        for r in self._records:
            if r.service not in svc_providers:
                svc_providers[r.service] = {}
            pv = r.provider.value
            svc_providers[r.service].setdefault(pv, []).append(r.score)
        multi_cloud: list[dict[str, Any]] = []
        for svc, providers in svc_providers.items():
            if len(providers) < 2:
                continue
            avgs = {}
            for pv, scores in providers.items():
                avgs[pv] = round(sum(scores) / len(scores), 2)
            vals = list(avgs.values())
            drift = round(max(vals) - min(vals), 2)
            multi_cloud.append(
                {
                    "service": svc,
                    "providers": avgs,
                    "drift": drift,
                    "aligned": drift < 10.0,
                }
            )
        multi_cloud.sort(key=lambda x: x["drift"], reverse=True)
        return {
            "multi_cloud_services": len(multi_cloud),
            "details": multi_cloud,
        }
