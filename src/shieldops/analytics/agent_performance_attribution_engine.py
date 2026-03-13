"""Agent Performance Attribution Engine —
compute component attribution, detect performance bottlenecks,
and rank components by impact for agent optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComponentType(StrEnum):
    PERCEPTION = "perception"
    REASONING = "reasoning"
    ACTION = "action"
    COMMUNICATION = "communication"


class AttributionMethod(StrEnum):
    SHAPLEY = "shapley"
    ABLATION = "ablation"
    GRADIENT = "gradient"
    PERTURBATION = "perturbation"


class PerformanceImpact(StrEnum):
    CRITICAL = "critical"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    NEGLIGIBLE = "negligible"


# --- Models ---


class PerformanceAttributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    component_type: ComponentType = ComponentType.REASONING
    attribution_method: AttributionMethod = AttributionMethod.SHAPLEY
    performance_impact: PerformanceImpact = PerformanceImpact.SIGNIFICANT
    attribution_score: float = 0.0
    baseline_performance: float = 0.0
    measured_performance: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerformanceAttributionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_attribution: float = 0.0
    top_component: ComponentType = ComponentType.REASONING
    dominant_method: AttributionMethod = AttributionMethod.SHAPLEY
    component_count: int = 0
    bottleneck_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerformanceAttributionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_attribution_score: float = 0.0
    by_component_type: dict[str, int] = Field(default_factory=dict)
    by_attribution_method: dict[str, int] = Field(default_factory=dict)
    by_performance_impact: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentPerformanceAttributionEngine:
    """Attribute performance to specific agent components,
    detect bottlenecks, and rank components by impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PerformanceAttributionRecord] = []
        self._analyses: dict[str, PerformanceAttributionAnalysis] = {}
        logger.info(
            "agent_performance_attribution.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        component_type: ComponentType = ComponentType.REASONING,
        attribution_method: AttributionMethod = AttributionMethod.SHAPLEY,
        performance_impact: PerformanceImpact = PerformanceImpact.SIGNIFICANT,
        attribution_score: float = 0.0,
        baseline_performance: float = 0.0,
        measured_performance: float = 0.0,
        description: str = "",
    ) -> PerformanceAttributionRecord:
        record = PerformanceAttributionRecord(
            agent_id=agent_id,
            component_type=component_type,
            attribution_method=attribution_method,
            performance_impact=performance_impact,
            attribution_score=attribution_score,
            baseline_performance=baseline_performance,
            measured_performance=measured_performance,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "performance_attribution.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> PerformanceAttributionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        scores = [r.attribution_score for r in agent_recs]
        avg_attr = round(sum(scores) / len(scores), 2) if scores else 0.0
        comp_scores: dict[str, list[float]] = {}
        for r in agent_recs:
            comp_scores.setdefault(r.component_type.value, []).append(r.attribution_score)
        top_comp_val = (
            max(
                comp_scores,
                key=lambda x: sum(comp_scores[x]) / len(comp_scores[x]),
            )
            if comp_scores
            else ComponentType.REASONING.value
        )
        top_component = ComponentType(top_comp_val)
        method_counts: dict[str, int] = {}
        for r in agent_recs:
            method_counts[r.attribution_method.value] = (
                method_counts.get(r.attribution_method.value, 0) + 1
            )
        dominant_method = (
            AttributionMethod(max(method_counts, key=lambda x: method_counts[x]))
            if method_counts
            else AttributionMethod.SHAPLEY
        )
        critical_count = sum(
            1 for r in agent_recs if r.performance_impact == PerformanceImpact.CRITICAL
        )
        bottleneck_score = round(critical_count / max(len(agent_recs), 1) * 100, 2)
        analysis = PerformanceAttributionAnalysis(
            agent_id=rec.agent_id,
            avg_attribution=avg_attr,
            top_component=top_component,
            dominant_method=dominant_method,
            component_count=len(set(r.component_type for r in agent_recs)),
            bottleneck_score=bottleneck_score,
            description=f"Agent {rec.agent_id} top component {top_component.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PerformanceAttributionReport:
        by_ct: dict[str, int] = {}
        by_am: dict[str, int] = {}
        by_pi: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_ct[r.component_type.value] = by_ct.get(r.component_type.value, 0) + 1
            by_am[r.attribution_method.value] = by_am.get(r.attribution_method.value, 0) + 1
            by_pi[r.performance_impact.value] = by_pi.get(r.performance_impact.value, 0) + 1
            scores.append(r.attribution_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        agent_totals: dict[str, float] = {}
        for r in self._records:
            agent_totals[r.agent_id] = agent_totals.get(r.agent_id, 0.0) + r.attribution_score
        ranked = sorted(
            agent_totals,
            key=lambda x: agent_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        critical = by_pi.get("critical", 0)
        if critical > 0:
            recs.append(f"{critical} critical performance bottlenecks — prioritize fixes")
        if not recs:
            recs.append("No critical bottlenecks detected")
        return PerformanceAttributionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_attribution_score=avg,
            by_component_type=by_ct,
            by_attribution_method=by_am,
            by_performance_impact=by_pi,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.component_type.value] = dist.get(r.component_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "component_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("agent_performance_attribution.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def compute_component_attribution(self) -> list[dict[str, Any]]:
        """Compute attribution scores per component type across all agents."""
        comp_data: dict[str, list[float]] = {}
        for r in self._records:
            comp_data.setdefault(r.component_type.value, []).append(r.attribution_score)
        results: list[dict[str, Any]] = []
        for comp, scores in comp_data.items():
            avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
            max_s = round(max(scores), 2) if scores else 0.0
            total_s = round(sum(scores), 2)
            results.append(
                {
                    "component_type": comp,
                    "avg_attribution": avg_s,
                    "max_attribution": max_s,
                    "total_attribution": total_s,
                    "sample_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_attribution"], reverse=True)
        return results

    def detect_performance_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect components that are consistently limiting performance."""
        comp_impact: dict[str, dict[str, int]] = {}
        for r in self._records:
            entry = comp_impact.setdefault(
                r.component_type.value,
                {"critical": 0, "significant": 0, "moderate": 0, "negligible": 0},
            )
            entry[r.performance_impact.value] = entry.get(r.performance_impact.value, 0) + 1
        results: list[dict[str, Any]] = []
        for comp, impact_counts in comp_impact.items():
            total = sum(impact_counts.values())
            critical_rate = round(impact_counts.get("critical", 0) / max(total, 1), 2)
            is_bottleneck = critical_rate > 0.3
            results.append(
                {
                    "component_type": comp,
                    "critical_rate": critical_rate,
                    "impact_counts": impact_counts,
                    "is_bottleneck": is_bottleneck,
                    "total_records": total,
                }
            )
        results.sort(key=lambda x: x["critical_rate"], reverse=True)
        return results

    def rank_components_by_impact(self) -> list[dict[str, Any]]:
        """Rank agent components by their overall performance impact."""
        impact_weight = {
            "critical": 4,
            "significant": 3,
            "moderate": 2,
            "negligible": 1,
        }
        comp_scores: dict[str, list[float]] = {}
        comp_weights: dict[str, float] = {}
        for r in self._records:
            comp_scores.setdefault(r.component_type.value, []).append(r.attribution_score)
            comp_weights[r.component_type.value] = comp_weights.get(
                r.component_type.value, 0.0
            ) + impact_weight.get(r.performance_impact.value, 1)
        results: list[dict[str, Any]] = []
        for comp, scores in comp_scores.items():
            avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
            total_w = comp_weights.get(comp, 0.0)
            impact_score = round(avg_s * total_w / max(len(scores), 1), 2)
            results.append(
                {
                    "component_type": comp,
                    "avg_attribution": avg_s,
                    "weighted_impact": impact_score,
                    "sample_count": len(scores),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["weighted_impact"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
