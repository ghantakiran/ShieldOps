"""Dependency Topology Analyzer — analyze service dependency graphs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TopologyPattern(StrEnum):
    LINEAR_CHAIN = "linear_chain"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"
    MESH = "mesh"
    STAR = "star"


class CouplingLevel(StrEnum):
    TIGHT = "tight"
    MODERATE = "moderate"
    LOOSE = "loose"
    DECOUPLED = "decoupled"
    ISOLATED = "isolated"


class TopologyRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class TopologyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    pattern: TopologyPattern = TopologyPattern.LINEAR_CHAIN
    coupling: CouplingLevel = CouplingLevel.MODERATE
    risk: TopologyRisk = TopologyRisk.LOW
    depth_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class TopologyRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    pattern: TopologyPattern = TopologyPattern.LINEAR_CHAIN
    coupling: CouplingLevel = CouplingLevel.MODERATE
    max_depth: int = 5
    max_fan_out: float = 10.0
    created_at: float = Field(default_factory=time.time)


class TopologyAnalyzerReport(BaseModel):
    total_observations: int = 0
    total_rules: int = 0
    low_risk_rate_pct: float = 0.0
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_coupling: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyTopologyAnalyzer:
    """Analyze service dependency graphs."""

    def __init__(
        self,
        max_records: int = 200000,
        max_coupling_depth: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_coupling_depth = max_coupling_depth
        self._records: list[TopologyRecord] = []
        self._rules: list[TopologyRule] = []
        logger.info(
            "dependency_topology.initialized",
            max_records=max_records,
            max_coupling_depth=max_coupling_depth,
        )

    # -- record / get / list -----------------------------------------

    def record_observation(
        self,
        service_name: str,
        pattern: TopologyPattern = (TopologyPattern.LINEAR_CHAIN),
        coupling: CouplingLevel = (CouplingLevel.MODERATE),
        risk: TopologyRisk = TopologyRisk.LOW,
        depth_score: float = 0.0,
        details: str = "",
    ) -> TopologyRecord:
        record = TopologyRecord(
            service_name=service_name,
            pattern=pattern,
            coupling=coupling,
            risk=risk,
            depth_score=depth_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_topology.recorded",
            record_id=record.id,
            service_name=service_name,
            pattern=pattern.value,
            coupling=coupling.value,
        )
        return record

    def get_observation(self, record_id: str) -> TopologyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_observations(
        self,
        service_name: str | None = None,
        pattern: TopologyPattern | None = None,
        limit: int = 50,
    ) -> list[TopologyRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if pattern is not None:
            results = [r for r in results if r.pattern == pattern]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        pattern: TopologyPattern = (TopologyPattern.LINEAR_CHAIN),
        coupling: CouplingLevel = (CouplingLevel.MODERATE),
        max_depth: int = 5,
        max_fan_out: float = 10.0,
    ) -> TopologyRule:
        rule = TopologyRule(
            rule_name=rule_name,
            pattern=pattern,
            coupling=coupling,
            max_depth=max_depth,
            max_fan_out=max_fan_out,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "dependency_topology.rule_added",
            rule_name=rule_name,
            pattern=pattern.value,
            coupling=coupling.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_topology_health(self, service_name: str) -> dict[str, Any]:
        """Analyze topology health for a service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        low_risk = sum(1 for r in records if r.risk in (TopologyRisk.LOW, TopologyRisk.MINIMAL))
        low_risk_rate = round(low_risk / len(records) * 100, 2)
        avg_depth = round(
            sum(r.depth_score for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "observation_count": len(records),
            "low_risk_count": low_risk,
            "low_risk_rate": low_risk_rate,
            "avg_depth": avg_depth,
            "meets_threshold": (avg_depth <= self._max_coupling_depth),
        }

    def identify_tightly_coupled(
        self,
    ) -> list[dict[str, Any]]:
        """Find services with tight coupling."""
        counts: dict[str, int] = {}
        for r in self._records:
            if r.coupling == CouplingLevel.TIGHT:
                counts[r.service_name] = counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "tight_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["tight_count"],
            reverse=True,
        )
        return results

    def rank_by_depth(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by avg depth desc."""
        svc_vals: dict[str, list[float]] = {}
        for r in self._records:
            svc_vals.setdefault(r.service_name, []).append(r.depth_score)
        results: list[dict[str, Any]] = []
        for svc, vals in svc_vals.items():
            avg = round(sum(vals) / len(vals), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_depth": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_depth"],
            reverse=True,
        )
        return results

    def detect_topology_risks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with topology risks (>3)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.risk not in (
                TopologyRisk.LOW,
                TopologyRisk.MINIMAL,
            ):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "risk_count": count,
                        "risk_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["risk_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> TopologyAnalyzerReport:
        by_pattern: dict[str, int] = {}
        by_coupling: dict[str, int] = {}
        for r in self._records:
            by_pattern[r.pattern.value] = by_pattern.get(r.pattern.value, 0) + 1
            by_coupling[r.coupling.value] = by_coupling.get(r.coupling.value, 0) + 1
        low_risk_count = sum(
            1 for r in self._records if r.risk in (TopologyRisk.LOW, TopologyRisk.MINIMAL)
        )
        low_risk_rate = (
            round(
                low_risk_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        critical = sum(1 for r in self._records if r.risk == TopologyRisk.CRITICAL)
        tight_svcs = len(self.identify_tightly_coupled())
        recs: list[str] = []
        if tight_svcs > 0:
            recs.append(f"{tight_svcs} service(s) with tight coupling")
        risks = len(self.detect_topology_risks())
        if risks > 0:
            recs.append(f"{risks} service(s) with topology risks")
        if critical > 0:
            recs.append(f"{critical} critical risk observation(s)")
        if not recs:
            recs.append("Dependency topology is healthy")
        return TopologyAnalyzerReport(
            total_observations=len(self._records),
            total_rules=len(self._rules),
            low_risk_rate_pct=low_risk_rate,
            by_pattern=by_pattern,
            by_coupling=by_coupling,
            critical_count=critical,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("dependency_topology.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pattern_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pattern.value
            pattern_dist[key] = pattern_dist.get(key, 0) + 1
        return {
            "total_observations": len(self._records),
            "total_rules": len(self._rules),
            "max_coupling_depth": (self._max_coupling_depth),
            "pattern_distribution": pattern_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
