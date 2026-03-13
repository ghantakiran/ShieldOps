"""Service Dependency Risk Engine.

Quantify dependency risk, detect shared failure domains,
and recommend dependency decoupling strategies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CouplingStrength(StrEnum):
    TIGHT = "tight"
    MODERATE = "moderate"
    LOOSE = "loose"
    NONE = "none"


class FailureDomain(StrEnum):
    AVAILABILITY_ZONE = "availability_zone"
    REGION = "region"
    PROVIDER = "provider"
    SHARED_SERVICE = "shared_service"


# --- Models ---


class DependencyRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    target_service: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    coupling_strength: CouplingStrength = CouplingStrength.LOOSE
    failure_domain: FailureDomain = FailureDomain.AVAILABILITY_ZONE
    risk_score: float = 0.0
    call_frequency: float = 0.0
    fallback_available: bool = False
    created_at: float = Field(default_factory=time.time)


class DependencyRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str = ""
    target_service: str = ""
    computed_risk: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    has_fallback: bool = False
    dependency_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_coupling_strength: dict[str, int] = Field(default_factory=dict)
    by_failure_domain: dict[str, int] = Field(default_factory=dict)
    high_risk_deps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceDependencyRiskEngine:
    """Quantify dependency risk, detect shared failure
    domains, recommend decoupling strategies."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DependencyRiskRecord] = []
        self._analyses: dict[str, DependencyRiskAnalysis] = {}
        logger.info(
            "service_dependency_risk_engine.init",
            max_records=max_records,
        )

    def record_item(
        self,
        source_service: str = "",
        target_service: str = "",
        risk_level: RiskLevel = RiskLevel.LOW,
        coupling_strength: CouplingStrength = (CouplingStrength.LOOSE),
        failure_domain: FailureDomain = (FailureDomain.AVAILABILITY_ZONE),
        risk_score: float = 0.0,
        call_frequency: float = 0.0,
        fallback_available: bool = False,
    ) -> DependencyRiskRecord:
        record = DependencyRiskRecord(
            source_service=source_service,
            target_service=target_service,
            risk_level=risk_level,
            coupling_strength=coupling_strength,
            failure_domain=failure_domain,
            risk_score=risk_score,
            call_frequency=call_frequency,
            fallback_available=fallback_available,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_risk.record_added",
            record_id=record.id,
            source=source_service,
        )
        return record

    def process(self, key: str) -> DependencyRiskAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        deps = sum(1 for r in self._records if r.source_service == rec.source_service)
        analysis = DependencyRiskAnalysis(
            source_service=rec.source_service,
            target_service=rec.target_service,
            computed_risk=round(rec.risk_score, 2),
            risk_level=rec.risk_level,
            has_fallback=rec.fallback_available,
            dependency_count=deps,
            description=(f"{rec.source_service} -> {rec.target_service} risk {rec.risk_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> DependencyRiskReport:
        by_rl: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        by_fd: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.risk_level.value
            by_rl[k] = by_rl.get(k, 0) + 1
            k2 = r.coupling_strength.value
            by_cs[k2] = by_cs.get(k2, 0) + 1
            k3 = r.failure_domain.value
            by_fd[k3] = by_fd.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high = list(
            {
                f"{r.source_service}->{r.target_service}"
                for r in self._records
                if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            }
        )[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} high-risk dependencies")
        if not recs:
            recs.append("No high-risk dependencies")
        return DependencyRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_risk_level=by_rl,
            by_coupling_strength=by_cs,
            by_failure_domain=by_fd,
            high_risk_deps=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.risk_level.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_level_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("service_dependency_risk_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def quantify_dependency_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Quantify risk per service dependency."""
        dep_scores: dict[str, list[float]] = {}
        dep_meta: dict[str, dict[str, str]] = {}
        for r in self._records:
            k = f"{r.source_service}->{r.target_service}"
            dep_scores.setdefault(k, []).append(r.risk_score)
            dep_meta[k] = {
                "source": r.source_service,
                "target": r.target_service,
            }
        results: list[dict[str, Any]] = []
        for dep, scores in dep_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "dependency": dep,
                    "source": dep_meta[dep]["source"],
                    "target": dep_meta[dep]["target"],
                    "avg_risk": avg,
                    "sample_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_risk"],
            reverse=True,
        )
        return results

    def detect_shared_failure_domains(
        self,
    ) -> list[dict[str, Any]]:
        """Detect shared failure domains."""
        domain_svcs: dict[str, set[str]] = {}
        for r in self._records:
            domain_svcs.setdefault(r.failure_domain.value, set()).add(r.source_service)
        results: list[dict[str, Any]] = []
        for domain, svcs in domain_svcs.items():
            if len(svcs) > 1:
                results.append(
                    {
                        "failure_domain": domain,
                        "service_count": len(svcs),
                        "services": sorted(svcs)[:10],
                    }
                )
        results.sort(
            key=lambda x: x["service_count"],
            reverse=True,
        )
        return results

    def recommend_dependency_decoupling(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend decoupling for tight deps."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            k = f"{r.source_service}->{r.target_service}"
            if (
                r.coupling_strength
                in (
                    CouplingStrength.TIGHT,
                    CouplingStrength.MODERATE,
                )
                and k not in seen
            ):
                seen.add(k)
                results.append(
                    {
                        "dependency": k,
                        "coupling": (r.coupling_strength.value),
                        "risk_score": r.risk_score,
                        "recommendation": (
                            "Introduce async boundary"
                            if r.coupling_strength == CouplingStrength.TIGHT
                            else "Monitor coupling"
                        ),
                    }
                )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        return results
