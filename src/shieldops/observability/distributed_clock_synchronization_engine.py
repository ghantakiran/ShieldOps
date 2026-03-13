"""Distributed Clock Synchronization Engine —
monitor clock sync in distributed traces,
detect clock drift, rank nodes by drift severity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ClockSource(StrEnum):
    NTP = "ntp"
    PTP = "ptp"
    SYSTEM = "system"
    HYBRID = "hybrid"


class SyncStatus(StrEnum):
    SYNCHRONIZED = "synchronized"
    DRIFTING = "drifting"
    UNSYNCHRONIZED = "unsynchronized"
    UNKNOWN = "unknown"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class ClockSyncRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    service_name: str = ""
    clock_source: ClockSource = ClockSource.NTP
    sync_status: SyncStatus = SyncStatus.SYNCHRONIZED
    drift_severity: DriftSeverity = DriftSeverity.LOW
    drift_ms: float = 0.0
    offset_ms: float = 0.0
    jitter_ms: float = 0.0
    last_sync_ago_s: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ClockSyncAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    service_name: str = ""
    clock_source: ClockSource = ClockSource.NTP
    sync_score: float = 0.0
    drift_detected: bool = False
    drift_severity: DriftSeverity = DriftSeverity.LOW
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ClockSyncReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_drift_ms: float = 0.0
    by_clock_source: dict[str, int] = Field(default_factory=dict)
    by_sync_status: dict[str, int] = Field(default_factory=dict)
    by_drift_severity: dict[str, int] = Field(default_factory=dict)
    drifting_nodes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DistributedClockSynchronizationEngine:
    """Monitor clock sync in distributed traces,
    detect clock drift, rank nodes by drift severity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ClockSyncRecord] = []
        self._analyses: dict[str, ClockSyncAnalysis] = {}
        logger.info("distributed_clock_synchronization_engine.init", max_records=max_records)

    def add_record(
        self,
        node_id: str = "",
        service_name: str = "",
        clock_source: ClockSource = ClockSource.NTP,
        sync_status: SyncStatus = SyncStatus.SYNCHRONIZED,
        drift_severity: DriftSeverity = DriftSeverity.LOW,
        drift_ms: float = 0.0,
        offset_ms: float = 0.0,
        jitter_ms: float = 0.0,
        last_sync_ago_s: float = 0.0,
        description: str = "",
    ) -> ClockSyncRecord:
        record = ClockSyncRecord(
            node_id=node_id,
            service_name=service_name,
            clock_source=clock_source,
            sync_status=sync_status,
            drift_severity=drift_severity,
            drift_ms=drift_ms,
            offset_ms=offset_ms,
            jitter_ms=jitter_ms,
            last_sync_ago_s=last_sync_ago_s,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "clock_sync.record_added",
            record_id=record.id,
            node_id=node_id,
        )
        return record

    def process(self, key: str) -> ClockSyncAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        sev_w = sev_weights.get(rec.drift_severity.value, 1)
        sync_score = max(0.0, round(100.0 - (sev_w * 20.0) - (rec.jitter_ms * 0.1), 2))
        drift_detected = rec.sync_status in (SyncStatus.DRIFTING, SyncStatus.UNSYNCHRONIZED)
        analysis = ClockSyncAnalysis(
            node_id=rec.node_id,
            service_name=rec.service_name,
            clock_source=rec.clock_source,
            sync_score=sync_score,
            drift_detected=drift_detected,
            drift_severity=rec.drift_severity,
            description=(
                f"Node {rec.node_id} drift {rec.drift_ms}ms status {rec.sync_status.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ClockSyncReport:
        by_src: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        drifts: list[float] = []
        for r in self._records:
            s = r.clock_source.value
            by_src[s] = by_src.get(s, 0) + 1
            st = r.sync_status.value
            by_status[st] = by_status.get(st, 0) + 1
            sv = r.drift_severity.value
            by_sev[sv] = by_sev.get(sv, 0) + 1
            drifts.append(r.drift_ms)
        avg = round(sum(drifts) / len(drifts), 2) if drifts else 0.0
        drifting_nodes = list(
            {
                r.node_id
                for r in self._records
                if r.sync_status in (SyncStatus.DRIFTING, SyncStatus.UNSYNCHRONIZED)
            }
        )[:10]
        recs: list[str] = []
        if drifting_nodes:
            recs.append(f"{len(drifting_nodes)} nodes with clock drift detected")
        if not recs:
            recs.append("All nodes clock-synchronized within acceptable limits")
        return ClockSyncReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_drift_ms=avg,
            by_clock_source=by_src,
            by_sync_status=by_status,
            by_drift_severity=by_sev,
            drifting_nodes=drifting_nodes,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            k = r.sync_status.value
            status_dist[k] = status_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "sync_status_distribution": status_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("distributed_clock_synchronization_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def evaluate_clock_synchronization(self) -> list[dict[str, Any]]:
        """Evaluate clock synchronization quality per node."""
        node_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            node_data.setdefault(r.node_id, []).append(
                {
                    "drift_ms": r.drift_ms,
                    "jitter_ms": r.jitter_ms,
                    "offset_ms": r.offset_ms,
                    "status": r.sync_status.value,
                }
            )
        results: list[dict[str, Any]] = []
        for nid, items in node_data.items():
            avg_drift = sum(i["drift_ms"] for i in items) / len(items)
            avg_jitter = sum(i["jitter_ms"] for i in items) / len(items)
            results.append(
                {
                    "node_id": nid,
                    "avg_drift_ms": round(avg_drift, 2),
                    "avg_jitter_ms": round(avg_jitter, 2),
                    "sample_count": len(items),
                    "sync_ok": avg_drift < 10.0,
                }
            )
        results.sort(key=lambda x: x["avg_drift_ms"], reverse=True)
        return results

    def detect_clock_drift(self) -> list[dict[str, Any]]:
        """Detect nodes experiencing clock drift beyond threshold."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.sync_status in (SyncStatus.DRIFTING, SyncStatus.UNSYNCHRONIZED)
                and r.node_id not in seen
            ):
                seen.add(r.node_id)
                results.append(
                    {
                        "node_id": r.node_id,
                        "service_name": r.service_name,
                        "sync_status": r.sync_status.value,
                        "drift_ms": r.drift_ms,
                        "drift_severity": r.drift_severity.value,
                        "clock_source": r.clock_source.value,
                    }
                )
        results.sort(key=lambda x: x["drift_ms"], reverse=True)
        return results

    def rank_nodes_by_drift_severity(self) -> list[dict[str, Any]]:
        """Rank nodes by composite drift severity score."""
        sev_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        node_scores: dict[str, float] = {}
        node_info: dict[str, dict[str, Any]] = {}
        for r in self._records:
            w = sev_weights.get(r.drift_severity.value, 1)
            score = w * (r.drift_ms + 1)
            node_scores[r.node_id] = node_scores.get(r.node_id, 0.0) + score
            node_info[r.node_id] = {
                "service_name": r.service_name,
                "clock_source": r.clock_source.value,
            }
        results: list[dict[str, Any]] = []
        for nid, total_score in node_scores.items():
            info = node_info.get(nid, {})
            results.append(
                {
                    "node_id": nid,
                    "service_name": info.get("service_name", ""),
                    "clock_source": info.get("clock_source", ""),
                    "drift_severity_score": round(total_score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["drift_severity_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
