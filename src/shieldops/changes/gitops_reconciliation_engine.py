"""GitOpsReconciliationEngine
Git-to-cluster state reconciliation, drift detection, auto-sync tracking, conflict resolution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReconciliationStatus(StrEnum):
    SYNCED = "synced"
    DRIFTED = "drifted"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    FAILED = "failed"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SyncStrategy(StrEnum):
    AUTO_SYNC = "auto_sync"
    MANUAL_APPROVAL = "manual_approval"
    DRY_RUN = "dry_run"
    FORCE_SYNC = "force_sync"
    ROLLBACK = "rollback"


# --- Models ---


class ReconciliationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cluster: str = ""
    namespace: str = ""
    repo_url: str = ""
    branch: str = "main"
    status: ReconciliationStatus = ReconciliationStatus.SYNCED
    drift_severity: DriftSeverity = DriftSeverity.INFO
    sync_strategy: SyncStrategy = SyncStrategy.AUTO_SYNC
    desired_hash: str = ""
    actual_hash: str = ""
    drift_resources: int = 0
    sync_duration_seconds: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReconciliationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cluster: str = ""
    analysis_score: float = 0.0
    drift_count: int = 0
    conflict_count: int = 0
    auto_resolved: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReconciliationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    synced_count: int = 0
    drifted_count: int = 0
    conflict_count: int = 0
    avg_sync_duration: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_drifted_clusters: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class GitOpsReconciliationEngine:
    """Git-to-cluster state reconciliation with drift detection and auto-sync."""

    def __init__(
        self,
        max_records: int = 200000,
        drift_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._drift_threshold = drift_threshold
        self._records: list[ReconciliationRecord] = []
        self._analyses: list[ReconciliationAnalysis] = []
        logger.info(
            "gitops.reconciliation.engine.initialized",
            max_records=max_records,
            drift_threshold=drift_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        cluster: str = "",
        namespace: str = "default",
        repo_url: str = "",
        branch: str = "main",
        status: ReconciliationStatus = ReconciliationStatus.SYNCED,
        drift_severity: DriftSeverity = DriftSeverity.INFO,
        sync_strategy: SyncStrategy = SyncStrategy.AUTO_SYNC,
        desired_hash: str = "",
        actual_hash: str = "",
        drift_resources: int = 0,
        sync_duration_seconds: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReconciliationRecord:
        record = ReconciliationRecord(
            name=name,
            cluster=cluster,
            namespace=namespace,
            repo_url=repo_url,
            branch=branch,
            status=status,
            drift_severity=drift_severity,
            sync_strategy=sync_strategy,
            desired_hash=desired_hash,
            actual_hash=actual_hash,
            drift_resources=drift_resources,
            sync_duration_seconds=sync_duration_seconds,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "gitops.reconciliation.engine.item_recorded",
            record_id=record.id,
            name=name,
            cluster=cluster,
            status=status.value,
        )
        return record

    def get_record(self, record_id: str) -> ReconciliationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        status: ReconciliationStatus | None = None,
        cluster: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReconciliationRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.status == status]
        if cluster is not None:
            results = [r for r in results if r.cluster == cluster]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        cluster: str = "",
        analysis_score: float = 0.0,
        drift_count: int = 0,
        conflict_count: int = 0,
        auto_resolved: int = 0,
        description: str = "",
    ) -> ReconciliationAnalysis:
        analysis = ReconciliationAnalysis(
            name=name,
            cluster=cluster,
            analysis_score=analysis_score,
            drift_count=drift_count,
            conflict_count=conflict_count,
            auto_resolved=auto_resolved,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "gitops.reconciliation.engine.analysis_added",
            name=name,
            cluster=cluster,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def detect_drift(self) -> list[dict[str, Any]]:
        drifted: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in (ReconciliationStatus.DRIFTED, ReconciliationStatus.CONFLICT):
                drifted.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "cluster": r.cluster,
                        "namespace": r.namespace,
                        "drift_severity": r.drift_severity.value,
                        "drift_resources": r.drift_resources,
                        "desired_hash": r.desired_hash,
                        "actual_hash": r.actual_hash,
                    }
                )
        return sorted(drifted, key=lambda x: x["drift_resources"], reverse=True)

    def analyze_sync_performance(self) -> dict[str, Any]:
        cluster_durations: dict[str, list[float]] = {}
        for r in self._records:
            cluster_durations.setdefault(r.cluster, []).append(r.sync_duration_seconds)
        result: dict[str, Any] = {}
        for cluster, durations in cluster_durations.items():
            result[cluster] = {
                "count": len(durations),
                "avg_duration": round(sum(durations) / len(durations), 2),
                "max_duration": round(max(durations), 2),
            }
        return result

    def identify_conflict_hotspots(self) -> list[dict[str, Any]]:
        ns_conflicts: dict[str, int] = {}
        for r in self._records:
            if r.status == ReconciliationStatus.CONFLICT:
                key = f"{r.cluster}/{r.namespace}"
                ns_conflicts[key] = ns_conflicts.get(key, 0) + 1
        results = [{"location": k, "conflict_count": v} for k, v in ns_conflicts.items()]
        return sorted(results, key=lambda x: x["conflict_count"], reverse=True)

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ReconciliationReport:
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_severity[r.drift_severity.value] = by_severity.get(r.drift_severity.value, 0) + 1
            by_strategy[r.sync_strategy.value] = by_strategy.get(r.sync_strategy.value, 0) + 1
        synced = sum(1 for r in self._records if r.status == ReconciliationStatus.SYNCED)
        drifted = sum(1 for r in self._records if r.status == ReconciliationStatus.DRIFTED)
        conflicts = sum(1 for r in self._records if r.status == ReconciliationStatus.CONFLICT)
        durations = [r.sync_duration_seconds for r in self._records if r.sync_duration_seconds > 0]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        cluster_drift: dict[str, int] = {}
        for r in self._records:
            if r.status == ReconciliationStatus.DRIFTED:
                cluster_drift[r.cluster] = cluster_drift.get(r.cluster, 0) + 1
        top_drifted = sorted(cluster_drift, key=cluster_drift.get, reverse=True)[:5]  # type: ignore[arg-type]
        recs: list[str] = []
        if drifted > 0:
            recs.append(f"{drifted} resource(s) drifted from desired state")
        if conflicts > 0:
            recs.append(f"{conflicts} conflict(s) require manual resolution")
        if avg_duration > 60.0:
            recs.append(f"Avg sync duration {avg_duration}s exceeds 60s target")
        if not recs:
            recs.append("GitOps reconciliation is healthy — all clusters synced")
        return ReconciliationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            synced_count=synced,
            drifted_count=drifted,
            conflict_count=conflicts,
            avg_sync_duration=avg_duration,
            by_status=by_status,
            by_severity=by_severity,
            by_strategy=by_strategy,
            top_drifted_clusters=top_drifted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("gitops.reconciliation.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            status_dist[r.status.value] = status_dist.get(r.status.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "drift_threshold": self._drift_threshold,
            "status_distribution": status_dist,
            "unique_clusters": len({r.cluster for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
