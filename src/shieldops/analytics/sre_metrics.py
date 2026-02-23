"""SRE Metrics Aggregator — aggregates key SRE metrics for service scorecards."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MetricCategory(StrEnum):
    AVAILABILITY = "availability"
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    DEPLOYMENT = "deployment"
    COST = "cost"


class AggregationPeriod(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class MetricDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    category: MetricCategory
    metric_name: str
    value: float
    unit: str = ""
    period: AggregationPeriod = AggregationPeriod.DAILY
    recorded_at: float = Field(default_factory=time.time)


class ServiceScorecard(BaseModel):
    service: str
    availability_pct: float = 0.0
    mttr_minutes: float = 0.0
    error_rate_pct: float = 0.0
    deploy_frequency: float = 0.0
    cost_per_request: float = 0.0
    overall_score: float = 0.0
    generated_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class SREMetricsAggregator:
    """Aggregates SRE metrics and generates service scorecards."""

    def __init__(
        self,
        max_datapoints: int = 500000,
        max_scorecards: int = 1000,
    ) -> None:
        self.max_datapoints = max_datapoints
        self.max_scorecards = max_scorecards
        self._datapoints: list[MetricDataPoint] = []
        self._scorecards: dict[str, ServiceScorecard] = {}
        logger.info(
            "sre_metrics_aggregator.initialized",
            max_datapoints=max_datapoints,
            max_scorecards=max_scorecards,
        )

    def record_metric(
        self,
        service: str,
        category: MetricCategory | str,
        metric_name: str,
        value: float,
        unit: str = "",
        period: AggregationPeriod | str = AggregationPeriod.DAILY,
    ) -> MetricDataPoint:
        """Record a metric data point. Trims to max (FIFO)."""
        dp = MetricDataPoint(
            service=service,
            category=MetricCategory(category),
            metric_name=metric_name,
            value=value,
            unit=unit,
            period=AggregationPeriod(period),
        )
        self._datapoints.append(dp)
        if len(self._datapoints) > self.max_datapoints:
            self._datapoints = self._datapoints[-self.max_datapoints :]
        logger.info(
            "sre_metrics_aggregator.metric_recorded",
            metric_id=dp.id,
            service=service,
            category=str(category),
            metric_name=metric_name,
        )
        return dp

    def _latest_value(
        self,
        service: str,
        category: MetricCategory,
    ) -> float:
        """Return the latest value for a service+category pair."""
        for dp in reversed(self._datapoints):
            if dp.service == service and dp.category == category:
                return dp.value
        return 0.0

    def _compute_overall_score(self, card: ServiceScorecard) -> float:
        """Compute weighted overall score for a scorecard."""
        # Availability contributes most, then error rate (inverted), etc.
        score = 0.0
        score += card.availability_pct * 0.30
        # Lower MTTR is better — map to 0-100 scale (cap at 1440 min)
        mttr_score = max(0.0, 100.0 - (card.mttr_minutes / 14.4))
        score += mttr_score * 0.25
        # Lower error rate is better
        error_score = max(0.0, 100.0 - card.error_rate_pct)
        score += error_score * 0.25
        # Higher deploy freq is better (cap contribution at 100)
        deploy_score = min(card.deploy_frequency * 10, 100.0)
        score += deploy_score * 0.10
        # Lower cost per request is better (cap at $1.00 = 0 score)
        cost_score = max(0.0, 100.0 - card.cost_per_request * 100)
        score += cost_score * 0.10
        return round(score, 2)

    def generate_scorecard(self, service: str) -> ServiceScorecard:
        """Generate a scorecard from latest metrics for each category."""
        availability = self._latest_value(service, MetricCategory.AVAILABILITY)
        reliability = self._latest_value(service, MetricCategory.RELIABILITY)
        performance = self._latest_value(service, MetricCategory.PERFORMANCE)
        deployment = self._latest_value(service, MetricCategory.DEPLOYMENT)
        cost = self._latest_value(service, MetricCategory.COST)

        card = ServiceScorecard(
            service=service,
            availability_pct=availability,
            mttr_minutes=reliability,
            error_rate_pct=performance,
            deploy_frequency=deployment,
            cost_per_request=cost,
        )
        card.overall_score = self._compute_overall_score(card)

        # Store, enforcing max_scorecards
        if len(self._scorecards) >= self.max_scorecards and service not in self._scorecards:
            oldest_key = next(iter(self._scorecards))
            del self._scorecards[oldest_key]
        self._scorecards[service] = card

        logger.info(
            "sre_metrics_aggregator.scorecard_generated",
            service=service,
            overall_score=card.overall_score,
        )
        return card

    def get_scorecard(self, service: str) -> ServiceScorecard | None:
        """Return a cached scorecard for a service."""
        return self._scorecards.get(service)

    def list_scorecards(self) -> list[ServiceScorecard]:
        """List all cached scorecards."""
        return list(self._scorecards.values())

    def get_metrics(
        self,
        service: str | None = None,
        category: MetricCategory | str | None = None,
        limit: int = 100,
    ) -> list[MetricDataPoint]:
        """List metric data points with optional filters."""
        results = list(self._datapoints)
        if service is not None:
            results = [d for d in results if d.service == service]
        if category is not None:
            cat = MetricCategory(category) if isinstance(category, str) else category
            results = [d for d in results if d.category == cat]
        return results[-limit:]

    def get_trend(
        self,
        service: str,
        metric_name: str,
        limit: int = 30,
    ) -> list[MetricDataPoint]:
        """Return recent data points for a service+metric_name pair."""
        results = [
            dp for dp in self._datapoints if dp.service == service and dp.metric_name == metric_name
        ]
        return results[-limit:]

    def compare_services(
        self,
        services: list[str],
    ) -> list[ServiceScorecard]:
        """Generate/return scorecards for multiple services."""
        cards: list[ServiceScorecard] = []
        for svc in services:
            existing = self._scorecards.get(svc)
            if existing is not None:
                cards.append(existing)
            else:
                cards.append(self.generate_scorecard(svc))
        return cards

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        services: set[str] = set()
        category_dist: dict[str, int] = {}
        for dp in self._datapoints:
            services.add(dp.service)
            category_dist[dp.category] = category_dist.get(dp.category, 0) + 1
        return {
            "total_datapoints": len(self._datapoints),
            "total_scorecards": len(self._scorecards),
            "services_tracked": len(services),
            "category_distribution": category_dist,
        }
