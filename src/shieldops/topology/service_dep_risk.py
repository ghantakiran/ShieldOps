"""Service Dependency Risk Scorer — score and manage service dependency risks."""

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
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class DependencyDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"
    INTERNAL = "internal"
    EXTERNAL = "external"


# --- Models ---


class DependencyRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    dependency: str = ""
    dep_type: DependencyType = DependencyType.SYNCHRONOUS
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskFactor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    dependency: str = ""
    factor_name: str = ""
    factor_score: float = 0.0
    weight: float = 1.0
    created_at: float = Field(default_factory=time.time)


class DependencyRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_factors: int = 0
    avg_risk_score: float = 0.0
    by_dep_type: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    high_risk_deps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceDependencyRiskScorer:
    """Score service dependency risks, track risk factors, and analyze risk patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        max_risk_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._max_risk_score = max_risk_score
        self._records: list[DependencyRiskRecord] = []
        self._factors: list[RiskFactor] = []
        logger.info(
            "service_dep_risk.initialized",
            max_records=max_records,
            max_risk_score=max_risk_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_risk(
        self,
        service: str,
        dependency: str,
        dep_type: DependencyType = DependencyType.SYNCHRONOUS,
        risk_score: float = 0.0,
        risk_level: RiskLevel = RiskLevel.LOW,
        direction: DependencyDirection = DependencyDirection.DOWNSTREAM,
        details: str = "",
    ) -> DependencyRiskRecord:
        record = DependencyRiskRecord(
            service=service,
            dependency=dependency,
            dep_type=dep_type,
            risk_score=risk_score,
            risk_level=risk_level,
            direction=direction,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_dep_risk.recorded",
            record_id=record.id,
            service=service,
            dependency=dependency,
            risk_level=risk_level.value,
        )
        return record

    def get_risk(self, record_id: str) -> DependencyRiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_risks(
        self,
        dep_type: DependencyType | None = None,
        risk_level: RiskLevel | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[DependencyRiskRecord]:
        results = list(self._records)
        if dep_type is not None:
            results = [r for r in results if r.dep_type == dep_type]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_risk_factor(
        self,
        service: str,
        dependency: str,
        factor_name: str,
        factor_score: float = 0.0,
        weight: float = 1.0,
    ) -> RiskFactor:
        factor = RiskFactor(
            service=service,
            dependency=dependency,
            factor_name=factor_name,
            factor_score=factor_score,
            weight=weight,
        )
        self._factors.append(factor)
        if len(self._factors) > self._max_records:
            self._factors = self._factors[-self._max_records :]
        logger.info(
            "service_dep_risk.factor_added",
            service=service,
            dependency=dependency,
            factor_name=factor_name,
        )
        return factor

    # -- domain operations -----------------------------------------------

    def analyze_risk_by_service(self) -> list[dict[str, Any]]:
        """Analyze average risk score per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def identify_high_risk_deps(self) -> list[dict[str, Any]]:
        """Find dependencies where risk_score exceeds the max_risk_score threshold."""
        high: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score > self._max_risk_score:
                high.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "dependency": r.dependency,
                        "risk_score": r.risk_score,
                        "risk_level": r.risk_level.value,
                    }
                )
        high.sort(key=lambda x: x["risk_score"], reverse=True)
        return high

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Rank services by average risk score."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_trends(self) -> list[dict[str, Any]]:
        """Detect risk trends using split-half comparison."""
        svc_records: dict[str, list[float]] = {}
        for r in self._records:
            svc_records.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_records.items():
            if len(scores) < 4:
                results.append({"service": svc, "trend": "insufficient_data"})
                continue
            mid = len(scores) // 2
            first_half_avg = sum(scores[:mid]) / mid
            second_half_avg = sum(scores[mid:]) / (len(scores) - mid)
            delta = second_half_avg - first_half_avg
            if delta > 5.0:
                trend = "increasing"
            elif delta < -5.0:
                trend = "decreasing"
            else:
                trend = "stable"
            results.append(
                {
                    "service": svc,
                    "first_half_avg": round(first_half_avg, 2),
                    "second_half_avg": round(second_half_avg, 2),
                    "delta": round(delta, 2),
                    "trend": trend,
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DependencyRiskReport:
        by_dep_type: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        for r in self._records:
            by_dep_type[r.dep_type.value] = by_dep_type.get(r.dep_type.value, 0) + 1
            by_risk_level[r.risk_level.value] = by_risk_level.get(r.risk_level.value, 0) + 1
            by_direction[r.direction.value] = by_direction.get(r.direction.value, 0) + 1
        avg_risk = (
            round(
                sum(r.risk_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_risk = self.identify_high_risk_deps()
        high_risk_names = [h["dependency"] for h in high_risk[:10]]
        recs: list[str] = []
        if avg_risk > self._max_risk_score:
            recs.append(f"Average risk score {avg_risk} exceeds {self._max_risk_score} threshold")
        if len(high_risk) > 0:
            recs.append(f"{len(high_risk)} high-risk dependency(ies) detected")
        if not recs:
            recs.append("Dependency risk levels within acceptable limits")
        return DependencyRiskReport(
            total_records=len(self._records),
            total_factors=len(self._factors),
            avg_risk_score=avg_risk,
            by_dep_type=by_dep_type,
            by_risk_level=by_risk_level,
            by_direction=by_direction,
            high_risk_deps=high_risk_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._factors.clear()
        logger.info("service_dep_risk.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dep_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_factors": len(self._factors),
            "max_risk_score": self._max_risk_score,
            "dep_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
        }
