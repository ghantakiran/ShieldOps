"""SRE Golden Signal Engine
compute golden signal health, detect signal anomalies,
rank services by signal degradation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GoldenSignal(StrEnum):
    LATENCY = "latency"
    TRAFFIC = "traffic"
    ERRORS = "errors"
    SATURATION = "saturation"


class SignalStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ServiceTier(StrEnum):
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"
    TIER4 = "tier4"


# --- Models ---


class GoldenSignalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    golden_signal: GoldenSignal = GoldenSignal.LATENCY
    signal_status: SignalStatus = SignalStatus.HEALTHY
    service_tier: ServiceTier = ServiceTier.TIER2
    value: float = 0.0
    threshold: float = 100.0
    baseline: float = 0.0
    region: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GoldenSignalAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    health_score: float = 0.0
    signal_status: SignalStatus = SignalStatus.HEALTHY
    anomaly_detected: bool = False
    signal_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GoldenSignalReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_health_score: float = 0.0
    by_signal: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_service_tier: dict[str, int] = Field(default_factory=dict)
    degraded_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SreGoldenSignalEngine:
    """Compute golden signal health, detect signal
    anomalies, rank services by signal degradation."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[GoldenSignalRecord] = []
        self._analyses: dict[str, GoldenSignalAnalysis] = {}
        logger.info(
            "sre_golden_signal_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service_id: str = "",
        golden_signal: GoldenSignal = GoldenSignal.LATENCY,
        signal_status: SignalStatus = SignalStatus.HEALTHY,
        service_tier: ServiceTier = ServiceTier.TIER2,
        value: float = 0.0,
        threshold: float = 100.0,
        baseline: float = 0.0,
        region: str = "",
        description: str = "",
    ) -> GoldenSignalRecord:
        record = GoldenSignalRecord(
            service_id=service_id,
            golden_signal=golden_signal,
            signal_status=signal_status,
            service_tier=service_tier,
            value=value,
            threshold=threshold,
            baseline=baseline,
            region=region,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sre_golden_signal_engine.record_added",
            record_id=record.id,
            service_id=service_id,
        )
        return record

    def process(self, key: str) -> GoldenSignalAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        signals = sum(1 for r in self._records if r.service_id == rec.service_id)
        health = round(max(0, 100 - abs(rec.value - rec.baseline)), 2)
        anomaly = rec.signal_status in (SignalStatus.DEGRADED, SignalStatus.CRITICAL)
        analysis = GoldenSignalAnalysis(
            service_id=rec.service_id,
            health_score=health,
            signal_status=rec.signal_status,
            anomaly_detected=anomaly,
            signal_count=signals,
            description=f"Service {rec.service_id} health {health}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> GoldenSignalReport:
        by_sig: dict[str, int] = {}
        by_st: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        healths: list[float] = []
        for r in self._records:
            k = r.golden_signal.value
            by_sig[k] = by_sig.get(k, 0) + 1
            k2 = r.signal_status.value
            by_st[k2] = by_st.get(k2, 0) + 1
            k3 = r.service_tier.value
            by_tier[k3] = by_tier.get(k3, 0) + 1
            healths.append(max(0, 100 - abs(r.value - r.baseline)))
        avg = round(sum(healths) / len(healths), 2) if healths else 0.0
        degraded = list(
            {
                r.service_id
                for r in self._records
                if r.signal_status in (SignalStatus.DEGRADED, SignalStatus.CRITICAL)
            }
        )[:10]
        recs: list[str] = []
        if degraded:
            recs.append(f"{len(degraded)} services with signal degradation")
        if not recs:
            recs.append("All golden signals within normal range")
        return GoldenSignalReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_health_score=avg,
            by_signal=by_sig,
            by_status=by_st,
            by_service_tier=by_tier,
            degraded_services=degraded,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        sig_dist: dict[str, int] = {}
        for r in self._records:
            k = r.golden_signal.value
            sig_dist[k] = sig_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "signal_distribution": sig_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("sre_golden_signal_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_golden_signal_health(
        self,
    ) -> list[dict[str, Any]]:
        """Aggregate golden signal health per service."""
        svc_data: dict[str, list[float]] = {}
        svc_tiers: dict[str, str] = {}
        for r in self._records:
            health = max(0, 100 - abs(r.value - r.baseline))
            svc_data.setdefault(r.service_id, []).append(health)
            svc_tiers[r.service_id] = r.service_tier.value
        results: list[dict[str, Any]] = []
        for sid, healths in svc_data.items():
            avg = round(sum(healths) / len(healths), 2)
            results.append(
                {
                    "service_id": sid,
                    "service_tier": svc_tiers[sid],
                    "avg_health": avg,
                    "signal_count": len(healths),
                }
            )
        results.sort(key=lambda x: x["avg_health"], reverse=True)
        return results

    def detect_signal_anomalies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with signal anomalies."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.signal_status in (SignalStatus.DEGRADED, SignalStatus.CRITICAL)
                and r.service_id not in seen
            ):
                seen.add(r.service_id)
                results.append(
                    {
                        "service_id": r.service_id,
                        "golden_signal": r.golden_signal.value,
                        "signal_status": r.signal_status.value,
                        "value": r.value,
                        "deviation": round(abs(r.value - r.baseline), 2),
                    }
                )
        results.sort(key=lambda x: x["deviation"], reverse=True)
        return results

    def rank_services_by_signal_degradation(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all services by signal degradation."""
        svc_data: dict[str, list[float]] = {}
        svc_tiers: dict[str, str] = {}
        for r in self._records:
            deviation = abs(r.value - r.baseline)
            svc_data.setdefault(r.service_id, []).append(deviation)
            svc_tiers[r.service_id] = r.service_tier.value
        results: list[dict[str, Any]] = []
        for sid, devs in svc_data.items():
            avg_dev = round(sum(devs) / len(devs), 2)
            results.append(
                {
                    "service_id": sid,
                    "service_tier": svc_tiers[sid],
                    "avg_deviation": avg_dev,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_deviation"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
