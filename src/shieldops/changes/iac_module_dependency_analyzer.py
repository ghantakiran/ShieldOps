"""IaC Module Dependency Analyzer
map module dependency graphs, detect circular
dependencies, rank modules by update impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ModuleSource(StrEnum):
    REGISTRY = "registry"
    GIT = "git"
    LOCAL = "local"
    S3 = "s3"


class DependencyDepth(StrEnum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    DEEP = "deep"
    CIRCULAR = "circular"


class UpdateRisk(StrEnum):
    BREAKING = "breaking"
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


# --- Models ---


class ModuleDependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    module_id: str = ""
    module_name: str = ""
    module_source: ModuleSource = ModuleSource.REGISTRY
    dependency_depth: DependencyDepth = DependencyDepth.DIRECT
    update_risk: UpdateRisk = UpdateRisk.PATCH
    dependent_count: int = 0
    dependency_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ModuleDependencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    module_id: str = ""
    dependency_depth: DependencyDepth = DependencyDepth.DIRECT
    impact_score: float = 0.0
    has_circular: bool = False
    total_dependents: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ModuleDependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_dependents: float = 0.0
    by_module_source: dict[str, int] = Field(default_factory=dict)
    by_dependency_depth: dict[str, int] = Field(default_factory=dict)
    by_update_risk: dict[str, int] = Field(default_factory=dict)
    high_impact_modules: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IacModuleDependencyAnalyzer:
    """Map module dependency graphs, detect circular
    dependencies, rank modules by update impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ModuleDependencyRecord] = []
        self._analyses: dict[str, ModuleDependencyAnalysis] = {}
        logger.info(
            "iac_module_dependency_analyzer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        module_id: str = "",
        module_name: str = "",
        module_source: ModuleSource = (ModuleSource.REGISTRY),
        dependency_depth: DependencyDepth = (DependencyDepth.DIRECT),
        update_risk: UpdateRisk = UpdateRisk.PATCH,
        dependent_count: int = 0,
        dependency_count: int = 0,
        description: str = "",
    ) -> ModuleDependencyRecord:
        record = ModuleDependencyRecord(
            module_id=module_id,
            module_name=module_name,
            module_source=module_source,
            dependency_depth=dependency_depth,
            update_risk=update_risk,
            dependent_count=dependent_count,
            dependency_count=dependency_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "module_dependency.record_added",
            record_id=record.id,
            module_id=module_id,
        )
        return record

    def process(self, key: str) -> ModuleDependencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        has_circ = rec.dependency_depth == DependencyDepth.CIRCULAR
        impact = round(
            rec.dependent_count * 10.0 + rec.dependency_count * 5.0,
            2,
        )
        analysis = ModuleDependencyAnalysis(
            module_id=rec.module_id,
            dependency_depth=rec.dependency_depth,
            impact_score=impact,
            has_circular=has_circ,
            total_dependents=rec.dependent_count,
            description=(f"Module {rec.module_id} impact {impact}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> ModuleDependencyReport:
        by_ms: dict[str, int] = {}
        by_dd: dict[str, int] = {}
        by_ur: dict[str, int] = {}
        dep_counts: list[int] = []
        for r in self._records:
            k = r.module_source.value
            by_ms[k] = by_ms.get(k, 0) + 1
            k2 = r.dependency_depth.value
            by_dd[k2] = by_dd.get(k2, 0) + 1
            k3 = r.update_risk.value
            by_ur[k3] = by_ur.get(k3, 0) + 1
            dep_counts.append(r.dependent_count)
        avg = round(sum(dep_counts) / len(dep_counts), 2) if dep_counts else 0.0
        high = list(
            {
                r.module_id
                for r in self._records
                if r.update_risk in (UpdateRisk.BREAKING, UpdateRisk.MAJOR)
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-impact modules found")
        if not recs:
            recs.append("No high-impact modules found")
        return ModuleDependencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_dependents=avg,
            by_module_source=by_ms,
            by_dependency_depth=by_dd,
            by_update_risk=by_ur,
            high_impact_modules=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ms_dist: dict[str, int] = {}
        for r in self._records:
            k = r.module_source.value
            ms_dist[k] = ms_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "module_source_distribution": ms_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("iac_module_dependency_analyzer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def map_module_dependency_graph(
        self,
    ) -> list[dict[str, Any]]:
        """Map dependency graph per module."""
        module_deps: dict[str, int] = {}
        module_dependents: dict[str, int] = {}
        for r in self._records:
            module_deps[r.module_id] = module_deps.get(r.module_id, 0) + r.dependency_count
            module_dependents[r.module_id] = (
                module_dependents.get(r.module_id, 0) + r.dependent_count
            )
        results: list[dict[str, Any]] = []
        for mid in module_deps:
            results.append(
                {
                    "module_id": mid,
                    "total_dependencies": (module_deps[mid]),
                    "total_dependents": (module_dependents.get(mid, 0)),
                    "fan_out": module_deps[mid],
                    "fan_in": (module_dependents.get(mid, 0)),
                }
            )
        results.sort(
            key=lambda x: x["total_dependents"],
            reverse=True,
        )
        return results

    def detect_circular_dependencies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect circular dependencies."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.dependency_depth == DependencyDepth.CIRCULAR:
                results.append(
                    {
                        "module_id": r.module_id,
                        "module_name": r.module_name,
                        "source": (r.module_source.value),
                        "dependent_count": (r.dependent_count),
                    }
                )
        results.sort(
            key=lambda x: x["dependent_count"],
            reverse=True,
        )
        return results

    def rank_modules_by_update_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Rank modules by update impact."""
        module_impact: dict[str, float] = {}
        for r in self._records:
            score = float(r.dependent_count * 10 + r.dependency_count * 5)
            module_impact[r.module_id] = module_impact.get(r.module_id, 0.0) + score
        results: list[dict[str, Any]] = []
        for mid, total in module_impact.items():
            results.append(
                {
                    "module_id": mid,
                    "impact_score": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["impact_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
