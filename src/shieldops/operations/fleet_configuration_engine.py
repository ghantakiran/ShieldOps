"""FleetConfigurationEngine

Multi-cluster configuration management, fleet-wide policy
enforcement, config propagation tracking.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConfigScope(StrEnum):
    CLUSTER = "cluster"
    NAMESPACE = "namespace"
    WORKLOAD = "workload"
    NODE_POOL = "node_pool"
    FLEET_WIDE = "fleet_wide"


class PropagationStatus(StrEnum):
    PENDING = "pending"
    PROPAGATING = "propagating"
    APPLIED = "applied"
    FAILED = "failed"
    PARTIAL = "partial"


class PolicyEnforcement(StrEnum):
    ENFORCED = "enforced"
    AUDIT = "audit"
    WARN = "warn"
    DISABLED = "disabled"
    PENDING_REVIEW = "pending_review"


# --- Models ---


class FleetConfigurationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    config_key: str = ""
    config_scope: ConfigScope = ConfigScope.CLUSTER
    propagation_status: PropagationStatus = PropagationStatus.PENDING
    policy_enforcement: PolicyEnforcement = PolicyEnforcement.AUDIT
    target_clusters: int = 0
    applied_clusters: int = 0
    failed_clusters: int = 0
    propagation_time_seconds: float = 0.0
    config_version: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FleetConfigurationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    config_scope: ConfigScope = ConfigScope.CLUSTER
    analysis_score: float = 0.0
    consistency_rate: float = 0.0
    policy_compliance_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FleetConfigurationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    fully_applied: int = 0
    partially_applied: int = 0
    failed_count: int = 0
    avg_propagation_time: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_propagation: dict[str, int] = Field(default_factory=dict)
    by_enforcement: dict[str, int] = Field(default_factory=dict)
    top_failing_configs: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class FleetConfigurationEngine:
    """Multi-cluster configuration management with fleet-wide policy enforcement."""

    def __init__(
        self,
        max_records: int = 200000,
        consistency_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._consistency_threshold = consistency_threshold
        self._records: list[FleetConfigurationRecord] = []
        self._analyses: list[FleetConfigurationAnalysis] = []
        logger.info(
            "fleet.configuration.engine.initialized",
            max_records=max_records,
            consistency_threshold=consistency_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        config_key: str = "",
        config_scope: ConfigScope = ConfigScope.CLUSTER,
        propagation_status: PropagationStatus = PropagationStatus.PENDING,
        policy_enforcement: PolicyEnforcement = PolicyEnforcement.AUDIT,
        target_clusters: int = 0,
        applied_clusters: int = 0,
        failed_clusters: int = 0,
        propagation_time_seconds: float = 0.0,
        config_version: str = "",
        service: str = "",
        team: str = "",
    ) -> FleetConfigurationRecord:
        record = FleetConfigurationRecord(
            name=name,
            config_key=config_key,
            config_scope=config_scope,
            propagation_status=propagation_status,
            policy_enforcement=policy_enforcement,
            target_clusters=target_clusters,
            applied_clusters=applied_clusters,
            failed_clusters=failed_clusters,
            propagation_time_seconds=propagation_time_seconds,
            config_version=config_version,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "fleet.configuration.engine.item_recorded",
            record_id=record.id,
            name=name,
            config_scope=config_scope.value,
            propagation_status=propagation_status.value,
        )
        return record

    def get_record(self, record_id: str) -> FleetConfigurationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        config_scope: ConfigScope | None = None,
        propagation_status: PropagationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FleetConfigurationRecord]:
        results = list(self._records)
        if config_scope is not None:
            results = [r for r in results if r.config_scope == config_scope]
        if propagation_status is not None:
            results = [r for r in results if r.propagation_status == propagation_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        config_scope: ConfigScope = ConfigScope.CLUSTER,
        analysis_score: float = 0.0,
        consistency_rate: float = 0.0,
        policy_compliance_rate: float = 0.0,
        description: str = "",
    ) -> FleetConfigurationAnalysis:
        analysis = FleetConfigurationAnalysis(
            name=name,
            config_scope=config_scope,
            analysis_score=analysis_score,
            consistency_rate=consistency_rate,
            policy_compliance_rate=policy_compliance_rate,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "fleet.configuration.engine.analysis_added",
            name=name,
            config_scope=config_scope.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def measure_consistency(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.target_clusters > 0:
                consistency = round(r.applied_clusters / r.target_clusters * 100, 2)
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "config_key": r.config_key,
                        "consistency_rate": consistency,
                        "target_clusters": r.target_clusters,
                        "applied_clusters": r.applied_clusters,
                        "failed_clusters": r.failed_clusters,
                    }
                )
        return sorted(results, key=lambda x: x["consistency_rate"])

    def track_propagation(self) -> dict[str, Any]:
        scope_times: dict[str, list[float]] = {}
        for r in self._records:
            scope_times.setdefault(r.config_scope.value, []).append(r.propagation_time_seconds)
        result: dict[str, Any] = {}
        for scope, times in scope_times.items():
            result[scope] = {
                "count": len(times),
                "avg_time": round(sum(times) / len(times), 2),
                "max_time": round(max(times), 2),
            }
        return result

    def audit_policy_enforcement(self) -> dict[str, Any]:
        enforcement_counts: dict[str, int] = {}
        non_enforced: list[str] = []
        for r in self._records:
            enforcement_counts[r.policy_enforcement.value] = (
                enforcement_counts.get(r.policy_enforcement.value, 0) + 1
            )
            if r.policy_enforcement in (PolicyEnforcement.DISABLED, PolicyEnforcement.WARN):
                non_enforced.append(r.name)
        total = len(self._records)
        enforced = enforcement_counts.get("enforced", 0)
        return {
            "enforcement_rate": round(enforced / total * 100, 2) if total else 0.0,
            "by_enforcement": enforcement_counts,
            "non_enforced_configs": non_enforced[:10],
        }

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> FleetConfigurationReport:
        by_scope: dict[str, int] = {}
        by_prop: dict[str, int] = {}
        by_enf: dict[str, int] = {}
        for r in self._records:
            by_scope[r.config_scope.value] = by_scope.get(r.config_scope.value, 0) + 1
            by_prop[r.propagation_status.value] = by_prop.get(r.propagation_status.value, 0) + 1
            by_enf[r.policy_enforcement.value] = by_enf.get(r.policy_enforcement.value, 0) + 1
        fully_applied = sum(
            1 for r in self._records if r.propagation_status == PropagationStatus.APPLIED
        )
        partial = sum(1 for r in self._records if r.propagation_status == PropagationStatus.PARTIAL)
        failed = sum(1 for r in self._records if r.propagation_status == PropagationStatus.FAILED)
        times = [
            r.propagation_time_seconds for r in self._records if r.propagation_time_seconds > 0
        ]
        avg_time = round(sum(times) / len(times), 2) if times else 0.0
        failing = [r.name for r in self._records if r.failed_clusters > 0]
        recs: list[str] = []
        if failed > 0:
            recs.append(f"{failed} config propagation(s) failed — investigate cluster connectivity")
        if partial > 0:
            recs.append(f"{partial} partial propagation(s) — retry or escalate")
        if avg_time > 120.0:
            recs.append(f"Avg propagation time {avg_time}s exceeds 120s target")
        if not recs:
            recs.append("Fleet configuration is healthy — all configs propagated")
        return FleetConfigurationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            fully_applied=fully_applied,
            partially_applied=partial,
            failed_count=failed,
            avg_propagation_time=avg_time,
            by_scope=by_scope,
            by_propagation=by_prop,
            by_enforcement=by_enf,
            top_failing_configs=failing[:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("fleet.configuration.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            scope_dist[r.config_scope.value] = scope_dist.get(r.config_scope.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "consistency_threshold": self._consistency_threshold,
            "scope_distribution": scope_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
