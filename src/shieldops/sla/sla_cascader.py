"""Service Dependency SLA Cascader — compute cascading SLA impact across dependency chains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CascadeImpact(StrEnum):
    NONE = "none"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    TOTAL_OUTAGE = "total_outage"


class DependencyRelation(StrEnum):
    HARD = "hard"
    SOFT = "soft"
    OPTIONAL = "optional"
    FALLBACK_AVAILABLE = "fallback_available"
    CIRCUIT_BROKEN = "circuit_broken"


class PropagationMode(StrEnum):
    SERIAL = "serial"
    PARALLEL = "parallel"
    FAN_OUT = "fan_out"
    CONDITIONAL = "conditional"
    AGGREGATED = "aggregated"


# --- Models ---


class CascadeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    upstream_service: str = ""
    downstream_service: str = ""
    upstream_sla_pct: float = 99.9
    downstream_sla_pct: float = 99.9
    effective_sla_pct: float = 99.9
    relation: DependencyRelation = DependencyRelation.HARD
    propagation: PropagationMode = PropagationMode.SERIAL
    impact: CascadeImpact = CascadeImpact.NONE
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CascadePath(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    target_service: str = ""
    path: list[str] = Field(default_factory=list)
    effective_sla_pct: float = 99.9
    weakest_link: str = ""
    hop_count: int = 0
    created_at: float = Field(default_factory=time.time)


class CascadeReport(BaseModel):
    total_dependencies: int = 0
    avg_effective_sla_pct: float = 0.0
    below_threshold_count: int = 0
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_relation: dict[str, int] = Field(default_factory=dict)
    weakest_links: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Cascader ---


class ServiceSLACascader:
    """Compute cascading SLA impact across service dependency chains."""

    def __init__(
        self,
        max_records: int = 200000,
        min_acceptable_sla_pct: float = 99.0,
    ) -> None:
        self._max_records = max_records
        self._min_acceptable_sla_pct = min_acceptable_sla_pct
        self._records: list[CascadeRecord] = []
        self._paths: list[CascadePath] = []
        logger.info(
            "sla_cascader.initialized",
            max_records=max_records,
            min_acceptable_sla_pct=min_acceptable_sla_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_dependency(
        self,
        upstream_service: str,
        downstream_service: str,
        upstream_sla_pct: float = 99.9,
        downstream_sla_pct: float = 99.9,
        relation: DependencyRelation = DependencyRelation.HARD,
        propagation: PropagationMode = PropagationMode.SERIAL,
        team: str = "",
    ) -> CascadeRecord:
        """Record a dependency and compute effective SLA."""
        effective = self._compute_effective(
            upstream_sla_pct,
            downstream_sla_pct,
            relation,
        )
        impact = self._classify_impact(effective)
        record = CascadeRecord(
            upstream_service=upstream_service,
            downstream_service=downstream_service,
            upstream_sla_pct=upstream_sla_pct,
            downstream_sla_pct=downstream_sla_pct,
            effective_sla_pct=effective,
            relation=relation,
            propagation=propagation,
            impact=impact,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sla_cascader.dependency_recorded",
            record_id=record.id,
            upstream=upstream_service,
            downstream=downstream_service,
            effective_sla_pct=effective,
        )
        return record

    def get_record(self, record_id: str) -> CascadeRecord | None:
        """Get a single cascade record by ID."""
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        upstream_service: str | None = None,
        impact: CascadeImpact | None = None,
        limit: int = 50,
    ) -> list[CascadeRecord]:
        """List cascade records with optional filters."""
        results = list(self._records)
        if upstream_service is not None:
            results = [r for r in results if r.upstream_service == upstream_service]
        if impact is not None:
            results = [r for r in results if r.impact == impact]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def compute_effective_sla(
        self,
        upstream_sla_pct: float,
        downstream_sla_pct: float,
        relation: DependencyRelation = DependencyRelation.HARD,
    ) -> dict[str, Any]:
        """Standalone effective SLA computation."""
        effective = self._compute_effective(
            upstream_sla_pct,
            downstream_sla_pct,
            relation,
        )
        impact = self._classify_impact(effective)
        return {
            "upstream_sla_pct": upstream_sla_pct,
            "downstream_sla_pct": downstream_sla_pct,
            "relation": relation.value,
            "effective_sla_pct": effective,
            "impact": impact.value,
            "below_threshold": effective < self._min_acceptable_sla_pct,
        }

    def trace_cascade_paths(
        self,
        source_service: str,
    ) -> list[CascadePath]:
        """Follow downstream dependencies from a source service."""
        # Build adjacency map from upstream -> downstream
        adj: dict[str, list[CascadeRecord]] = {}
        for r in self._records:
            adj.setdefault(r.upstream_service, []).append(r)

        paths: list[CascadePath] = []
        # BFS through the dependency graph
        queue: list[tuple[str, list[str], float]] = [(source_service, [source_service], 100.0)]
        visited: set[str] = set()

        while queue:
            current, path, running_sla = queue.pop(0)
            downstream_records = adj.get(current, [])
            if not downstream_records and current != source_service:
                # Terminal node — record this path
                weakest = self._find_weakest_in_path(path)
                cascade_path = CascadePath(
                    source_service=source_service,
                    target_service=current,
                    path=path,
                    effective_sla_pct=round(running_sla, 4),
                    weakest_link=weakest,
                    hop_count=len(path) - 1,
                )
                paths.append(cascade_path)
                continue
            for dep in downstream_records:
                ds = dep.downstream_service
                if ds in visited:
                    continue
                visited.add(ds)
                new_sla = self._compute_effective(
                    running_sla,
                    dep.downstream_sla_pct,
                    dep.relation,
                )
                queue.append((ds, path + [ds], new_sla))

        self._paths = paths
        logger.info(
            "sla_cascader.paths_traced",
            source=source_service,
            path_count=len(paths),
        )
        return paths

    def identify_weakest_links(self) -> list[dict[str, Any]]:
        """Find services that appear as the weakest link most often."""
        link_counts: dict[str, int] = {}
        for p in self._paths:
            if p.weakest_link:
                link_counts[p.weakest_link] = link_counts.get(p.weakest_link, 0) + 1
        results: list[dict[str, Any]] = []
        for service, count in sorted(link_counts.items(), key=lambda x: x[1], reverse=True):
            results.append(
                {
                    "service": service,
                    "weakest_link_count": count,
                    "impact": "high" if count >= 3 else "medium" if count >= 2 else "low",
                }
            )
        return results

    def simulate_degradation(
        self,
        service: str,
        degraded_sla_pct: float,
    ) -> dict[str, Any]:
        """Simulate what happens if a service's SLA degrades."""
        affected: list[dict[str, Any]] = []
        for r in self._records:
            if r.upstream_service == service:
                new_effective = self._compute_effective(
                    degraded_sla_pct,
                    r.downstream_sla_pct,
                    r.relation,
                )
                old_impact = r.impact
                new_impact = self._classify_impact(new_effective)
                affected.append(
                    {
                        "downstream_service": r.downstream_service,
                        "original_effective_sla_pct": r.effective_sla_pct,
                        "new_effective_sla_pct": round(new_effective, 4),
                        "original_impact": old_impact.value,
                        "new_impact": new_impact.value,
                        "worsened": new_impact.value != old_impact.value,
                    }
                )
        logger.info(
            "sla_cascader.degradation_simulated",
            service=service,
            degraded_sla_pct=degraded_sla_pct,
            affected_count=len(affected),
        )
        return {
            "service": service,
            "degraded_sla_pct": degraded_sla_pct,
            "affected_services": len(affected),
            "details": affected,
        }

    def rank_by_cascade_risk(self) -> list[dict[str, Any]]:
        """Rank services by how many downstream services would be impacted."""
        downstream_counts: dict[str, int] = {}
        sla_sums: dict[str, float] = {}
        for r in self._records:
            downstream_counts[r.upstream_service] = downstream_counts.get(r.upstream_service, 0) + 1
            sla_sums[r.upstream_service] = (
                sla_sums.get(r.upstream_service, 0.0) + r.effective_sla_pct
            )
        results: list[dict[str, Any]] = []
        for service, count in downstream_counts.items():
            avg_effective = round(sla_sums[service] / count, 4) if count > 0 else 0.0
            results.append(
                {
                    "service": service,
                    "downstream_count": count,
                    "avg_effective_sla_pct": avg_effective,
                    "risk": "high" if count >= 5 else "medium" if count >= 2 else "low",
                }
            )
        results.sort(key=lambda x: x["downstream_count"], reverse=True)
        return results

    # -- report / stats ----------------------------------------------

    def generate_cascade_report(self) -> CascadeReport:
        """Generate a comprehensive cascade report."""
        by_impact: dict[str, int] = {}
        by_relation: dict[str, int] = {}
        effective_slas: list[float] = []
        below_count = 0
        for r in self._records:
            by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1
            by_relation[r.relation.value] = by_relation.get(r.relation.value, 0) + 1
            effective_slas.append(r.effective_sla_pct)
            if r.effective_sla_pct < self._min_acceptable_sla_pct:
                below_count += 1
        avg_effective = (
            round(sum(effective_slas) / len(effective_slas), 4) if effective_slas else 0.0
        )
        weakest = self.identify_weakest_links()
        weakest_names = [w["service"] for w in weakest[:5]]
        recs = self._build_recommendations(by_impact, below_count)
        return CascadeReport(
            total_dependencies=len(self._records),
            avg_effective_sla_pct=avg_effective,
            below_threshold_count=below_count,
            by_impact=by_impact,
            by_relation=by_relation,
            weakest_links=weakest_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all stored records and paths."""
        self._records.clear()
        self._paths.clear()
        logger.info("sla_cascader.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        impact_dist: dict[str, int] = {}
        for r in self._records:
            key = r.impact.value
            impact_dist[key] = impact_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_paths": len(self._paths),
            "min_acceptable_sla_pct": self._min_acceptable_sla_pct,
            "impact_distribution": impact_dist,
            "unique_upstream": len({r.upstream_service for r in self._records}),
            "unique_downstream": len({r.downstream_service for r in self._records}),
        }

    # -- internal helpers --------------------------------------------

    def _compute_effective(
        self,
        upstream_sla_pct: float,
        downstream_sla_pct: float,
        relation: DependencyRelation,
    ) -> float:
        """Compute effective SLA based on dependency relation."""
        if relation == DependencyRelation.HARD:
            effective = (upstream_sla_pct * downstream_sla_pct) / 100.0
        elif relation == DependencyRelation.SOFT:
            effective = max(upstream_sla_pct, downstream_sla_pct) - 0.01
        elif relation == DependencyRelation.OPTIONAL:
            effective = upstream_sla_pct
        elif relation == DependencyRelation.FALLBACK_AVAILABLE:
            effective = upstream_sla_pct * 0.999 + downstream_sla_pct * 0.001
        elif relation == DependencyRelation.CIRCUIT_BROKEN:
            effective = upstream_sla_pct
        else:
            effective = (upstream_sla_pct * downstream_sla_pct) / 100.0
        return round(effective, 4)

    def _classify_impact(self, effective_sla_pct: float) -> CascadeImpact:
        """Classify impact from effective SLA percentage."""
        if effective_sla_pct >= 99.9:
            return CascadeImpact.NONE
        if effective_sla_pct >= 99.5:
            return CascadeImpact.DEGRADED
        if effective_sla_pct >= 99.0:
            return CascadeImpact.PARTIAL_OUTAGE
        if effective_sla_pct >= 95.0:
            return CascadeImpact.MAJOR_OUTAGE
        return CascadeImpact.TOTAL_OUTAGE

    def _find_weakest_in_path(self, path: list[str]) -> str:
        """Find the service with lowest SLA in a path."""
        weakest_service = ""
        lowest_sla = 100.0
        for r in self._records:
            if (
                r.upstream_service in path or r.downstream_service in path
            ) and r.effective_sla_pct < lowest_sla:
                lowest_sla = r.effective_sla_pct
                weakest_service = r.downstream_service
        return weakest_service

    def _build_recommendations(
        self,
        by_impact: dict[str, int],
        below_count: int,
    ) -> list[str]:
        """Build recommendations from cascade analysis."""
        recs: list[str] = []
        major = by_impact.get(CascadeImpact.MAJOR_OUTAGE.value, 0)
        total = by_impact.get(CascadeImpact.TOTAL_OUTAGE.value, 0)
        if total > 0:
            recs.append(f"{total} dependency chain(s) at total outage risk — add redundancy")
        if major > 0:
            recs.append(f"{major} dependency chain(s) at major outage risk — review SLAs")
        if below_count > 0:
            recs.append(f"{below_count} chain(s) below {self._min_acceptable_sla_pct}% threshold")
        if not recs:
            recs.append("All dependency chains within acceptable SLA bounds")
        return recs
