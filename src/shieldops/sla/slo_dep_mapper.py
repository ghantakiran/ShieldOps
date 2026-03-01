"""SLO Dependency Mapper — map SLO dependencies between services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MappingStatus(StrEnum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTING = "conflicting"


class DependencyType(StrEnum):
    HARD = "hard"
    SOFT = "soft"
    OPTIONAL = "optional"
    TRANSITIVE = "transitive"
    CIRCULAR = "circular"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


# --- Models ---


class MappingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    dependency_service: str = ""
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    dependency_type: DependencyType = DependencyType.HARD
    risk_level: RiskLevel = RiskLevel.NONE
    slo_target_pct: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class MappingRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    dependency_type: DependencyType = DependencyType.HARD
    min_slo_pct: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class SLODependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    unmapped_count: int = 0
    high_risk_count: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    cascade_risk_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLODependencyMapper:
    """Map SLO dependencies between services; cascading risk analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        min_slo_target_pct: float = 99.0,
    ) -> None:
        self._max_records = max_records
        self._min_slo_target_pct = min_slo_target_pct
        self._records: list[MappingRecord] = []
        self._rules: list[MappingRule] = []
        logger.info(
            "slo_dep_mapper.initialized",
            max_records=max_records,
            min_slo_target_pct=min_slo_target_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_mapping(
        self,
        service: str,
        dependency_service: str = "",
        mapping_status: MappingStatus = MappingStatus.UNMAPPED,
        dependency_type: DependencyType = DependencyType.HARD,
        risk_level: RiskLevel = RiskLevel.NONE,
        slo_target_pct: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> MappingRecord:
        record = MappingRecord(
            service=service,
            dependency_service=dependency_service,
            mapping_status=mapping_status,
            dependency_type=dependency_type,
            risk_level=risk_level,
            slo_target_pct=slo_target_pct,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_dep_mapper.mapping_recorded",
            record_id=record.id,
            service=service,
            mapping_status=mapping_status.value,
            dependency_type=dependency_type.value,
        )
        return record

    def get_mapping(self, record_id: str) -> MappingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mappings(
        self,
        mapping_status: MappingStatus | None = None,
        dependency_type: DependencyType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MappingRecord]:
        results = list(self._records)
        if mapping_status is not None:
            results = [r for r in results if r.mapping_status == mapping_status]
        if dependency_type is not None:
            results = [r for r in results if r.dependency_type == dependency_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        service_pattern: str,
        mapping_status: MappingStatus = MappingStatus.UNMAPPED,
        dependency_type: DependencyType = DependencyType.HARD,
        min_slo_pct: float = 0.0,
        reason: str = "",
    ) -> MappingRule:
        rule = MappingRule(
            service_pattern=service_pattern,
            mapping_status=mapping_status,
            dependency_type=dependency_type,
            min_slo_pct=min_slo_pct,
            reason=reason,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "slo_dep_mapper.rule_added",
            service_pattern=service_pattern,
            mapping_status=mapping_status.value,
            dependency_type=dependency_type.value,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_mapping_coverage(self) -> dict[str, Any]:
        """Group by mapping status; return count per status."""
        status_data: dict[str, int] = {}
        for r in self._records:
            key = r.mapping_status.value
            status_data[key] = status_data.get(key, 0) + 1
        return status_data

    def identify_unmapped_deps(self) -> list[dict[str, Any]]:
        """Return mappings where status is UNMAPPED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.mapping_status == MappingStatus.UNMAPPED:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "dependency_service": r.dependency_service,
                        "dependency_type": r.dependency_type.value,
                        "risk_level": r.risk_level.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_cascade_risk(self) -> list[dict[str, Any]]:
        """Group by service, count high-risk deps, sort desc."""
        high_risk_levels = {RiskLevel.CRITICAL, RiskLevel.HIGH}
        svc_risk: dict[str, int] = {}
        for r in self._records:
            if r.risk_level in high_risk_levels:
                svc_risk[r.service] = svc_risk.get(r.service, 0) + 1
        results: list[dict[str, Any]] = []
        for service, count in svc_risk.items():
            results.append(
                {
                    "service": service,
                    "high_risk_dep_count": count,
                }
            )
        results.sort(
            key=lambda x: x["high_risk_dep_count"],
            reverse=True,
        )
        return results

    def detect_mapping_trends(self) -> dict[str, Any]:
        """Split-half comparison on slo_target_pct; delta 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.slo_target_pct for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SLODependencyReport:
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_status[r.mapping_status.value] = by_status.get(r.mapping_status.value, 0) + 1
            by_type[r.dependency_type.value] = by_type.get(r.dependency_type.value, 0) + 1
            by_risk[r.risk_level.value] = by_risk.get(r.risk_level.value, 0) + 1
        unmapped_count = sum(1 for r in self._records if r.mapping_status == MappingStatus.UNMAPPED)
        high_risk_count = sum(
            1 for r in self._records if r.risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}
        )
        cascade = self.rank_by_cascade_risk()
        cascade_risk_services = [c["service"] for c in cascade]
        recs: list[str] = []
        if unmapped_count > 0:
            recs.append(
                f"{unmapped_count} unmapped dependency(ies) — map them to ensure SLO coverage"
            )
        if high_risk_count > 0:
            recs.append(f"{high_risk_count} high-risk dependency(ies) — review cascade impact")
        if not recs:
            recs.append("SLO dependency mapping levels are healthy")
        return SLODependencyReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            unmapped_count=unmapped_count,
            high_risk_count=high_risk_count,
            by_status=by_status,
            by_type=by_type,
            by_risk=by_risk,
            cascade_risk_services=cascade_risk_services,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("slo_dep_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.mapping_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_slo_target_pct": self._min_slo_target_pct,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
