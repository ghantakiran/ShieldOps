"""Reliability Target Advisor — recommend SLO targets from historical data."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BusinessTier(StrEnum):
    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    INTERNAL = "internal"


class RecommendationBasis(StrEnum):
    HISTORICAL_P50 = "historical_p50"
    HISTORICAL_P95 = "historical_p95"
    DEPENDENCY_CHAIN = "dependency_chain"
    INDUSTRY_BENCHMARK = "industry_benchmark"
    CUSTOM = "custom"


class TargetConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class ReliabilityTarget(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    business_tier: BusinessTier = BusinessTier.SILVER
    current_reliability_pct: float = 0.0
    recommended_target_pct: float = 0.0
    basis: RecommendationBasis = RecommendationBasis.HISTORICAL_P50
    confidence: TargetConfidence = TargetConfidence.INSUFFICIENT_DATA
    gap_pct: float = 0.0
    dependencies: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class TargetAssessment(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    target_id: str = ""
    actual_pct: float = 0.0
    target_pct: float = 0.0
    met: bool = False
    assessment_window: str = ""
    created_at: float = Field(default_factory=time.time)


class TargetAdvisorReport(BaseModel):
    total_targets: int = 0
    total_assessments: int = 0
    avg_reliability_pct: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(
        default_factory=dict,
    )
    underperforming: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Advisor ---


_TIER_TARGETS: dict[BusinessTier, float] = {
    BusinessTier.PLATINUM: 99.99,
    BusinessTier.GOLD: 99.95,
    BusinessTier.SILVER: 99.9,
    BusinessTier.BRONZE: 99.5,
    BusinessTier.INTERNAL: 99.0,
}


class ReliabilityTargetAdvisor:
    """Recommend SLO targets based on history and tier."""

    def __init__(
        self,
        max_targets: int = 50000,
        default_target_pct: float = 99.9,
    ) -> None:
        self._max_targets = max_targets
        self._default_target_pct = default_target_pct
        self._targets: list[ReliabilityTarget] = []
        self._assessments: list[TargetAssessment] = []
        logger.info(
            "reliability_target.initialized",
            max_targets=max_targets,
            default_target_pct=default_target_pct,
        )

    # -- CRUD --

    def create_target(
        self,
        service_name: str,
        business_tier: BusinessTier = BusinessTier.SILVER,
        current_reliability_pct: float = 0.0,
        dependencies: list[str] | None = None,
    ) -> ReliabilityTarget:
        recommended = _TIER_TARGETS.get(business_tier, self._default_target_pct)
        gap = round(recommended - current_reliability_pct, 4)
        target = ReliabilityTarget(
            service_name=service_name,
            business_tier=business_tier,
            current_reliability_pct=current_reliability_pct,
            recommended_target_pct=recommended,
            gap_pct=gap,
            dependencies=dependencies or [],
        )
        self._targets.append(target)
        if len(self._targets) > self._max_targets:
            self._targets = self._targets[-self._max_targets :]
        logger.info(
            "reliability_target.created",
            target_id=target.id,
            service=service_name,
        )
        return target

    def get_target(self, target_id: str) -> ReliabilityTarget | None:
        for t in self._targets:
            if t.id == target_id:
                return t
        return None

    def list_targets(
        self,
        service_name: str | None = None,
        business_tier: BusinessTier | None = None,
        limit: int = 50,
    ) -> list[ReliabilityTarget]:
        results = list(self._targets)
        if service_name is not None:
            results = [t for t in results if t.service_name == service_name]
        if business_tier is not None:
            results = [t for t in results if t.business_tier == business_tier]
        return results[-limit:]

    # -- Domain operations --

    def recommend_target(
        self,
        service_name: str,
        business_tier: BusinessTier,
        historical_pct: float,
    ) -> ReliabilityTarget:
        benchmark = _TIER_TARGETS.get(business_tier, self._default_target_pct)
        if historical_pct >= benchmark:
            recommended = historical_pct
            basis = RecommendationBasis.HISTORICAL_P95
            confidence = TargetConfidence.VERY_HIGH
        elif historical_pct >= benchmark - 1.0:
            recommended = benchmark
            basis = RecommendationBasis.HISTORICAL_P50
            confidence = TargetConfidence.HIGH
        else:
            recommended = round((historical_pct + benchmark) / 2.0, 4)
            basis = RecommendationBasis.INDUSTRY_BENCHMARK
            confidence = TargetConfidence.MODERATE
        gap = round(recommended - historical_pct, 4)
        target = ReliabilityTarget(
            service_name=service_name,
            business_tier=business_tier,
            current_reliability_pct=historical_pct,
            recommended_target_pct=recommended,
            basis=basis,
            confidence=confidence,
            gap_pct=gap,
        )
        self._targets.append(target)
        if len(self._targets) > self._max_targets:
            self._targets = self._targets[-self._max_targets :]
        logger.info(
            "reliability_target.recommended",
            target_id=target.id,
            service=service_name,
            recommended=recommended,
        )
        return target

    def assess_target(
        self,
        target_id: str,
        actual_pct: float,
    ) -> TargetAssessment | None:
        target = self.get_target(target_id)
        if target is None:
            return None
        met = actual_pct >= target.recommended_target_pct
        assessment = TargetAssessment(
            target_id=target_id,
            actual_pct=actual_pct,
            target_pct=target.recommended_target_pct,
            met=met,
            assessment_window=target.business_tier.value,
        )
        self._assessments.append(assessment)
        target.current_reliability_pct = actual_pct
        target.gap_pct = round(target.recommended_target_pct - actual_pct, 4)
        logger.info(
            "reliability_target.assessed",
            target_id=target_id,
            met=met,
        )
        return assessment

    def identify_overcommitted(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for t in self._targets:
            if t.current_reliability_pct > 0 and t.gap_pct > 2.0:
                results.append(
                    {
                        "service": t.service_name,
                        "target": t.recommended_target_pct,
                        "actual": t.current_reliability_pct,
                        "gap": t.gap_pct,
                        "tier": t.business_tier.value,
                    }
                )
        return results

    def identify_undercommitted(
        self,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for t in self._targets:
            if (
                t.current_reliability_pct > 0
                and t.current_reliability_pct > t.recommended_target_pct + 0.5
            ):
                results.append(
                    {
                        "service": t.service_name,
                        "target": t.recommended_target_pct,
                        "actual": t.current_reliability_pct,
                        "surplus": round(
                            t.current_reliability_pct - t.recommended_target_pct,
                            4,
                        ),
                        "tier": t.business_tier.value,
                    }
                )
        return results

    def analyze_dependency_impact(
        self,
    ) -> list[dict[str, Any]]:
        dep_map: dict[str, list[str]] = {}
        for t in self._targets:
            for dep in t.dependencies:
                dep_map.setdefault(dep, []).append(t.service_name)
        results: list[dict[str, Any]] = []
        for dep_name, dependents in dep_map.items():
            dep_target = None
            for t in self._targets:
                if t.service_name == dep_name:
                    dep_target = t
                    break
            reliability = dep_target.current_reliability_pct if dep_target else 0.0
            results.append(
                {
                    "dependency": dep_name,
                    "dependents": dependents,
                    "dependent_count": len(dependents),
                    "reliability": reliability,
                    "impact": "high"
                    if len(dependents) >= 3
                    else "medium"
                    if len(dependents) >= 2
                    else "low",
                }
            )
        results.sort(key=lambda r: r["dependent_count"], reverse=True)
        return results

    # -- Reports --

    def generate_advisor_report(self) -> TargetAdvisorReport:
        by_tier: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        reliabilities: list[float] = []
        underperforming: list[str] = []
        for t in self._targets:
            by_tier[t.business_tier.value] = by_tier.get(t.business_tier.value, 0) + 1
            by_confidence[t.confidence.value] = by_confidence.get(t.confidence.value, 0) + 1
            if t.current_reliability_pct > 0:
                reliabilities.append(t.current_reliability_pct)
            if t.gap_pct > 1.0:
                underperforming.append(t.service_name)
        avg_rel = round(sum(reliabilities) / len(reliabilities), 4) if reliabilities else 0.0
        recs: list[str] = []
        if underperforming:
            recs.append(f"Improve {len(underperforming)} underperforming services")
        overcommitted = self.identify_overcommitted()
        if overcommitted:
            recs.append(f"Relax targets for {len(overcommitted)} overcommitted services")
        undercommitted = self.identify_undercommitted()
        if undercommitted:
            recs.append(f"Raise targets for {len(undercommitted)} undercommitted services")
        return TargetAdvisorReport(
            total_targets=len(self._targets),
            total_assessments=len(self._assessments),
            avg_reliability_pct=avg_rel,
            by_tier=by_tier,
            by_confidence=by_confidence,
            underperforming=underperforming,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._targets.clear()
        self._assessments.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tiers = [t.business_tier.value for t in self._targets]
        return {
            "total_targets": len(self._targets),
            "total_assessments": len(self._assessments),
            "unique_services": len({t.service_name for t in self._targets}),
            "tiers": list(set(tiers)),
            "targets_met": sum(1 for a in self._assessments if a.met),
            "targets_missed": sum(1 for a in self._assessments if not a.met),
        }
