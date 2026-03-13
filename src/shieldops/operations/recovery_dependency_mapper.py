"""Recovery Dependency Mapper — compute recovery critical path,
detect circular dependencies, rank services by recovery priority."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyType(StrEnum):
    HARD = "hard"
    SOFT = "soft"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"


class RecoveryOrder(StrEnum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    STAGED = "staged"
    PRIORITY = "priority"


class DependencyRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class RecoveryDependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source_service: str = ""
    target_service: str = ""
    dependency_type: DependencyType = DependencyType.HARD
    recovery_order: RecoveryOrder = RecoveryOrder.SEQUENTIAL
    dependency_risk: DependencyRisk = DependencyRisk.MEDIUM
    recovery_time_seconds: float = 0.0
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RecoveryDependencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source_service: str = ""
    critical_path_length: int = 0
    has_circular: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecoveryDependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_dependency_type: dict[str, int] = Field(default_factory=dict)
    by_recovery_order: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RecoveryDependencyMapper:
    """Compute recovery critical path, detect circular dependencies,
    rank services by recovery priority."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RecoveryDependencyRecord] = []
        self._analyses: dict[str, RecoveryDependencyAnalysis] = {}
        logger.info(
            "recovery_dependency_mapper.init",
            max_records=max_records,
        )

    def record_item(
        self,
        name: str = "",
        source_service: str = "",
        target_service: str = "",
        dependency_type: DependencyType = DependencyType.HARD,
        recovery_order: RecoveryOrder = RecoveryOrder.SEQUENTIAL,
        dependency_risk: DependencyRisk = DependencyRisk.MEDIUM,
        recovery_time_seconds: float = 0.0,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RecoveryDependencyRecord:
        record = RecoveryDependencyRecord(
            name=name,
            source_service=source_service,
            target_service=target_service,
            dependency_type=dependency_type,
            recovery_order=recovery_order,
            dependency_risk=dependency_risk,
            recovery_time_seconds=recovery_time_seconds,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "recovery_dependency.record_added",
            record_id=record.id,
            source_service=source_service,
        )
        return record

    def process(self, key: str) -> RecoveryDependencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        deps = [r for r in self._records if r.source_service == rec.source_service]
        path_len = len(deps)
        # Simple circular check
        targets = {r.target_service for r in deps}
        has_circular = rec.source_service in targets
        analysis = RecoveryDependencyAnalysis(
            name=rec.name,
            source_service=rec.source_service,
            critical_path_length=path_len,
            has_circular=has_circular,
            description=f"Service {rec.source_service} -> {rec.target_service}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RecoveryDependencyReport:
        by_dt: dict[str, int] = {}
        by_ro: dict[str, int] = {}
        by_rk: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_dt[r.dependency_type.value] = by_dt.get(r.dependency_type.value, 0) + 1
            by_ro[r.recovery_order.value] = by_ro.get(r.recovery_order.value, 0) + 1
            by_rk[r.dependency_risk.value] = by_rk.get(r.dependency_risk.value, 0) + 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps: list[str] = []
        critical = by_rk.get("critical", 0)
        if critical > 0:
            gaps.append(f"{critical} critical dependency risks found")
        recs: list[str] = []
        if gaps:
            recs.extend(gaps)
        if not recs:
            recs.append("Recovery dependencies within acceptable parameters")
        return RecoveryDependencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg,
            by_dependency_type=by_dt,
            by_recovery_order=by_ro,
            by_risk=by_rk,
            top_gaps=gaps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dependency_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dependency_type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("recovery_dependency_mapper.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_recovery_critical_path(self) -> list[dict[str, Any]]:
        """Compute recovery critical path per service."""
        service_deps: dict[str, list[RecoveryDependencyRecord]] = {}
        for r in self._records:
            service_deps.setdefault(r.source_service, []).append(r)
        results: list[dict[str, Any]] = []
        for svc, deps in service_deps.items():
            hard_deps = [d for d in deps if d.dependency_type == DependencyType.HARD]
            total_time = round(sum(d.recovery_time_seconds for d in hard_deps), 2)
            results.append(
                {
                    "source_service": svc,
                    "total_dependencies": len(deps),
                    "hard_dependencies": len(hard_deps),
                    "critical_path_time": total_time,
                }
            )
        results.sort(key=lambda x: x["critical_path_time"], reverse=True)
        return results

    def detect_circular_dependencies(self) -> list[dict[str, Any]]:
        """Detect circular dependencies in recovery graph."""
        graph: dict[str, set[str]] = {}
        for r in self._records:
            graph.setdefault(r.source_service, set()).add(r.target_service)
        results: list[dict[str, Any]] = []
        for src, targets in graph.items():
            for tgt in targets:
                if tgt in graph and src in graph.get(tgt, set()):
                    pair = tuple(sorted([src, tgt]))
                    entry = {
                        "service_a": pair[0],
                        "service_b": pair[1],
                        "circular": True,
                    }
                    if entry not in results:
                        results.append(entry)
        return results

    def rank_services_by_recovery_priority(self) -> list[dict[str, Any]]:
        """Rank services by recovery priority (dependencies + risk)."""
        service_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = r.source_service
            if k not in service_data:
                service_data[k] = {"dep_count": 0, "scores": [], "hard_deps": 0}
            service_data[k]["dep_count"] += 1
            service_data[k]["scores"].append(r.score)
            if r.dependency_type == DependencyType.HARD:
                service_data[k]["hard_deps"] += 1
        results: list[dict[str, Any]] = []
        for svc, data in service_data.items():
            avg_score = round(sum(data["scores"]) / len(data["scores"]), 2)
            priority = round(avg_score * (1 + data["hard_deps"]), 2)
            results.append(
                {
                    "service": svc,
                    "priority_score": priority,
                    "dependency_count": data["dep_count"],
                    "hard_dependencies": data["hard_deps"],
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["priority_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
