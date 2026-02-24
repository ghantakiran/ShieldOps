"""SLO Target Advisor — SLO target recommendations, error budget policy suggestions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SLOMetricType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SATURATION = "saturation"


class TargetConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"


class BudgetPolicyAction(StrEnum):
    ALERT = "alert"
    THROTTLE = "throttle"
    FREEZE_DEPLOYS = "freeze_deploys"
    PAGE_ONCALL = "page_oncall"
    AUTO_ROLLBACK = "auto_rollback"


# --- Models ---


class PerformanceSample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    metric_type: SLOMetricType = SLOMetricType.AVAILABILITY
    value: float = 0.0
    unit: str = ""
    created_at: float = Field(default_factory=time.time)


class SLORecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    metric_type: SLOMetricType = SLOMetricType.AVAILABILITY
    recommended_target: float = 0.0
    current_p50: float = 0.0
    current_p99: float = 0.0
    confidence: TargetConfidence = TargetConfidence.SPECULATIVE
    reasoning: str = ""
    created_at: float = Field(default_factory=time.time)


class AdvisorReport(BaseModel):
    total_services: int = 0
    total_samples: int = 0
    recommendations_count: int = 0
    budget_policies: list[dict[str, Any]] = Field(default_factory=list)
    service_readiness: dict[str, str] = Field(default_factory=dict)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOTargetAdvisor:
    """SLO target recommendations, error budget policy suggestions."""

    def __init__(
        self,
        max_samples: int = 500000,
        min_sample_count: int = 100,
    ) -> None:
        self._max_samples = max_samples
        self._min_sample_count = min_sample_count
        self._samples: list[PerformanceSample] = []
        self._recommendations: list[SLORecommendation] = []
        logger.info(
            "slo_advisor.initialized",
            max_samples=max_samples,
            min_sample_count=min_sample_count,
        )

    def record_sample(
        self,
        service: str,
        metric_type: SLOMetricType,
        value: float,
        unit: str = "",
    ) -> PerformanceSample:
        sample = PerformanceSample(
            service=service,
            metric_type=metric_type,
            value=value,
            unit=unit,
        )
        self._samples.append(sample)
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples :]
        logger.info(
            "slo_advisor.sample_recorded",
            sample_id=sample.id,
            service=service,
            metric_type=metric_type,
            value=value,
        )
        return sample

    def get_sample(self, sample_id: str) -> PerformanceSample | None:
        for s in self._samples:
            if s.id == sample_id:
                return s
        return None

    def list_samples(
        self,
        service: str | None = None,
        metric_type: SLOMetricType | None = None,
        limit: int = 100,
    ) -> list[PerformanceSample]:
        results = list(self._samples)
        if service is not None:
            results = [s for s in results if s.service == service]
        if metric_type is not None:
            results = [s for s in results if s.metric_type == metric_type]
        return results[-limit:]

    def _compute_percentile(self, values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = (percentile / 100.0) * (len(sorted_vals) - 1)
        lower = int(idx)
        upper = min(lower + 1, len(sorted_vals) - 1)
        frac = idx - lower
        return round(sorted_vals[lower] + frac * (sorted_vals[upper] - sorted_vals[lower]), 4)

    def _determine_confidence(self, n: int) -> TargetConfidence:
        if n >= 100:
            return TargetConfidence.HIGH
        if n >= 30:
            return TargetConfidence.MEDIUM
        if n >= 10:
            return TargetConfidence.LOW
        return TargetConfidence.SPECULATIVE

    def recommend_target(
        self,
        service: str,
        metric_type: SLOMetricType,
    ) -> SLORecommendation | None:
        relevant = [
            s for s in self._samples if s.service == service and s.metric_type == metric_type
        ]
        if not relevant:
            return None

        values = [s.value for s in relevant]
        n = len(values)
        p50 = self._compute_percentile(values, 50)
        p99 = self._compute_percentile(values, 99)
        confidence = self._determine_confidence(n)

        # Compute recommended target based on metric type
        if metric_type == SLOMetricType.LATENCY:
            target = round(p99 * 1.1, 4)
            reasoning = (
                f"Latency target set to p99 * 1.1 = {target} (p50={p50}, p99={p99}, samples={n})"
            )
        elif metric_type == SLOMetricType.AVAILABILITY:
            target = round(p50 * 0.99, 4)
            reasoning = (
                f"Availability target set to p50 * 0.99 = {target} "
                f"(p50={p50}, p99={p99}, samples={n})"
            )
        elif metric_type == SLOMetricType.ERROR_RATE:
            target = round(p99 * 0.9, 4)
            reasoning = (
                f"Error rate target set to p99 * 0.9 = {target} (p50={p50}, p99={p99}, samples={n})"
            )
        else:
            # THROUGHPUT, SATURATION — use p50-based target
            target = round(p50 * 0.95, 4)
            reasoning = (
                f"{metric_type.value} target set to p50 * 0.95 = {target} "
                f"(p50={p50}, p99={p99}, samples={n})"
            )

        rec = SLORecommendation(
            service=service,
            metric_type=metric_type,
            recommended_target=target,
            current_p50=p50,
            current_p99=p99,
            confidence=confidence,
            reasoning=reasoning,
        )
        self._recommendations.append(rec)
        logger.info(
            "slo_advisor.target_recommended",
            service=service,
            metric_type=metric_type,
            target=target,
            confidence=confidence,
        )
        return rec

    def recommend_all_targets(self, service: str) -> list[SLORecommendation]:
        # Find all metric types with data for this service
        metric_types = {s.metric_type for s in self._samples if s.service == service}
        recommendations: list[SLORecommendation] = []
        for mt in sorted(metric_types, key=lambda m: m.value):
            rec = self.recommend_target(service, mt)
            if rec is not None:
                recommendations.append(rec)
        logger.info(
            "slo_advisor.all_targets_recommended",
            service=service,
            count=len(recommendations),
        )
        return recommendations

    def suggest_budget_policy(self, service: str) -> list[dict[str, Any]]:
        relevant = [s for s in self._samples if s.service == service]
        if not relevant:
            return []

        # Group by metric type and compute variance
        per_metric: dict[SLOMetricType, list[float]] = {}
        for s in relevant:
            per_metric.setdefault(s.metric_type, []).append(s.value)

        policies: list[dict[str, Any]] = []
        for mt, values in per_metric.items():
            n = len(values)
            if n < 2:
                continue
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            std_dev = variance**0.5
            cv = std_dev / mean if mean > 0 else 0.0  # coefficient of variation

            if cv > 0.5:
                # High variance — aggressive policy
                policies.append(
                    {
                        "service": service,
                        "metric_type": mt.value,
                        "variance": round(variance, 4),
                        "coefficient_of_variation": round(cv, 4),
                        "risk_level": "high",
                        "actions": [
                            BudgetPolicyAction.PAGE_ONCALL.value,
                            BudgetPolicyAction.FREEZE_DEPLOYS.value,
                        ],
                        "reason": (
                            f"High variance (cv={cv:.2f}) in {mt.value} — "
                            f"recommend aggressive error budget policy"
                        ),
                    }
                )
            elif cv > 0.2:
                # Moderate variance
                policies.append(
                    {
                        "service": service,
                        "metric_type": mt.value,
                        "variance": round(variance, 4),
                        "coefficient_of_variation": round(cv, 4),
                        "risk_level": "medium",
                        "actions": [
                            BudgetPolicyAction.ALERT.value,
                            BudgetPolicyAction.THROTTLE.value,
                        ],
                        "reason": (
                            f"Moderate variance (cv={cv:.2f}) in {mt.value} — "
                            f"recommend cautious error budget policy"
                        ),
                    }
                )
            else:
                # Low variance — light policy
                policies.append(
                    {
                        "service": service,
                        "metric_type": mt.value,
                        "variance": round(variance, 4),
                        "coefficient_of_variation": round(cv, 4),
                        "risk_level": "low",
                        "actions": [BudgetPolicyAction.ALERT.value],
                        "reason": (
                            f"Low variance (cv={cv:.2f}) in {mt.value} — "
                            f"standard alerting sufficient"
                        ),
                    }
                )

        logger.info(
            "slo_advisor.budget_policy_suggested",
            service=service,
            policy_count=len(policies),
        )
        return policies

    def analyze_historical_performance(self, service: str) -> dict[str, Any]:
        relevant = [s for s in self._samples if s.service == service]
        if not relevant:
            return {}

        per_metric: dict[str, list[float]] = {}
        for s in relevant:
            per_metric.setdefault(s.metric_type.value, []).append(s.value)

        result: dict[str, Any] = {}
        for mt, values in per_metric.items():
            n = len(values)
            avg = round(sum(values) / n, 4) if n > 0 else 0.0
            p50 = self._compute_percentile(values, 50)
            p99 = self._compute_percentile(values, 99)
            result[mt] = {
                "sample_count": n,
                "avg": avg,
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "p50": p50,
                "p99": p99,
            }
        return result

    def compare_targets(
        self,
        service: str,
        proposed_targets: dict[str, float],
    ) -> dict[str, Any]:
        recommendations = self.recommend_all_targets(service)
        rec_map: dict[str, SLORecommendation] = {r.metric_type.value: r for r in recommendations}

        comparisons: dict[str, Any] = {}
        for metric_key, proposed_value in proposed_targets.items():
            rec = rec_map.get(metric_key)
            if rec is None:
                comparisons[metric_key] = {
                    "proposed": proposed_value,
                    "recommended": None,
                    "verdict": "no_data",
                    "message": f"No recommendation available for {metric_key}",
                }
                continue

            diff = proposed_value - rec.recommended_target
            diff_pct = (
                round(diff / rec.recommended_target * 100, 2)
                if rec.recommended_target != 0
                else 0.0
            )

            if abs(diff_pct) <= 5:
                verdict = "aligned"
            elif diff_pct > 5:
                verdict = "aggressive"
            else:
                verdict = "conservative"

            comparisons[metric_key] = {
                "proposed": proposed_value,
                "recommended": rec.recommended_target,
                "difference": round(diff, 4),
                "difference_pct": diff_pct,
                "confidence": rec.confidence.value,
                "verdict": verdict,
                "message": (
                    f"Proposed {proposed_value} vs recommended {rec.recommended_target} "
                    f"({diff_pct:+.1f}%) — {verdict}"
                ),
            }

        return comparisons

    def generate_advisor_report(self) -> AdvisorReport:
        services = {s.service for s in self._samples}
        total_samples = len(self._samples)

        # Generate recommendations for all services
        all_recs: list[SLORecommendation] = []
        for svc in sorted(services):
            recs = self.recommend_all_targets(svc)
            all_recs.extend(recs)

        # Generate budget policies for all services
        all_policies: list[dict[str, Any]] = []
        for svc in sorted(services):
            policies = self.suggest_budget_policy(svc)
            all_policies.extend(policies)

        # Determine service readiness based on sample count
        service_readiness: dict[str, str] = {}
        for svc in sorted(services):
            svc_samples = sum(1 for s in self._samples if s.service == svc)
            if svc_samples >= self._min_sample_count:
                service_readiness[svc] = "ready"
            elif svc_samples >= 30:
                service_readiness[svc] = "partial"
            elif svc_samples >= 10:
                service_readiness[svc] = "limited"
            else:
                service_readiness[svc] = "insufficient"

        report = AdvisorReport(
            total_services=len(services),
            total_samples=total_samples,
            recommendations_count=len(all_recs),
            budget_policies=all_policies,
            service_readiness=service_readiness,
        )
        logger.info(
            "slo_advisor.report_generated",
            total_services=len(services),
            total_samples=total_samples,
            recommendations_count=len(all_recs),
        )
        return report

    def clear_data(self) -> None:
        self._samples.clear()
        self._recommendations.clear()
        logger.info("slo_advisor.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        services = {s.service for s in self._samples}
        metric_types = {s.metric_type.value for s in self._samples}
        return {
            "total_samples": len(self._samples),
            "total_recommendations": len(self._recommendations),
            "unique_services": len(services),
            "unique_metric_types": len(metric_types),
            "services": sorted(services),
            "metric_types": sorted(metric_types),
        }
