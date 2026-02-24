"""Service Health Aggregator — composite health scoring from multiple sources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthSignalSource(StrEnum):
    METRICS = "metrics"
    ALERTS = "alerts"
    INCIDENTS = "incidents"
    DEPENDENCIES = "dependencies"
    SYNTHETIC_CHECKS = "synthetic_checks"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    UNKNOWN = "unknown"


class AggregationStrategy(StrEnum):
    WORST_OF = "worst_of"
    WEIGHTED_AVERAGE = "weighted_average"
    MAJORITY_VOTE = "majority_vote"
    THRESHOLD_BASED = "threshold_based"
    CUSTOM = "custom"


# --- Models ---


class HealthSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    source: HealthSignalSource = HealthSignalSource.METRICS
    status: HealthStatus = HealthStatus.UNKNOWN
    score: float = 100.0
    details: str = ""
    reported_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class ServiceHealthScore(BaseModel):
    service_name: str = ""
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    overall_score: float = 0.0
    signal_count: int = 0
    by_source: dict[str, float] = Field(default_factory=dict)
    last_updated: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class HealthAggReport(BaseModel):
    total_services: int = 0
    total_signals: int = 0
    avg_health_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    unhealthy_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Status score mapping ---

_STATUS_SCORES: dict[HealthStatus, float] = {
    HealthStatus.HEALTHY: 100.0,
    HealthStatus.DEGRADED: 70.0,
    HealthStatus.PARTIAL_OUTAGE: 40.0,
    HealthStatus.MAJOR_OUTAGE: 10.0,
    HealthStatus.UNKNOWN: 50.0,
}

_SOURCE_WEIGHTS: dict[HealthSignalSource, float] = {
    HealthSignalSource.METRICS: 0.25,
    HealthSignalSource.ALERTS: 0.25,
    HealthSignalSource.INCIDENTS: 0.20,
    HealthSignalSource.DEPENDENCIES: 0.15,
    HealthSignalSource.SYNTHETIC_CHECKS: 0.15,
}


# --- Engine ---


class ServiceHealthAggregator:
    """Aggregate health signals from multiple sources into
    a composite health score per service."""

    def __init__(
        self,
        max_signals: int = 500000,
        health_threshold: float = 70.0,
    ) -> None:
        self._max_signals = max_signals
        self._health_threshold = health_threshold
        self._items: list[HealthSignal] = []
        self._scores: dict[str, ServiceHealthScore] = {}
        logger.info(
            "service_health_agg.initialized",
            max_signals=max_signals,
            health_threshold=health_threshold,
        )

    # -- CRUD -------------------------------------------------------

    def report_signal(
        self,
        service_name: str,
        source: HealthSignalSource = HealthSignalSource.METRICS,
        status: HealthStatus = HealthStatus.UNKNOWN,
        score: float = 100.0,
        details: str = "",
        **kw: Any,
    ) -> HealthSignal:
        """Report a health signal for a service."""
        signal = HealthSignal(
            service_name=service_name,
            source=source,
            status=status,
            score=score,
            details=details,
            **kw,
        )
        self._items.append(signal)
        if len(self._items) > self._max_signals:
            self._items = self._items[-self._max_signals :]
        logger.info(
            "service_health_agg.signal_reported",
            signal_id=signal.id,
            service_name=service_name,
            source=source,
            status=status,
        )
        return signal

    def get_signal(
        self,
        signal_id: str,
    ) -> HealthSignal | None:
        """Retrieve a signal by ID."""
        for item in self._items:
            if item.id == signal_id:
                return item
        return None

    def list_signals(
        self,
        service_name: str | None = None,
        source: HealthSignalSource | None = None,
        limit: int = 50,
    ) -> list[HealthSignal]:
        """List signals with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [s for s in results if s.service_name == service_name]
        if source is not None:
            results = [s for s in results if s.source == source]
        return results[-limit:]

    # -- Domain operations ------------------------------------------

    def calculate_health_score(
        self,
        service_name: str,
        strategy: AggregationStrategy = (AggregationStrategy.WEIGHTED_AVERAGE),
    ) -> ServiceHealthScore:
        """Calculate composite health score for a service."""
        signals = [s for s in self._items if s.service_name == service_name]
        if not signals:
            return ServiceHealthScore(
                service_name=service_name,
            )

        by_source: dict[str, float] = {}
        source_signals: dict[str, list[float]] = {}
        for s in signals:
            key = s.source.value
            source_signals.setdefault(key, []).append(s.score)

        for src, scores in source_signals.items():
            by_source[src] = round(
                sum(scores) / len(scores),
                2,
            )

        if strategy == AggregationStrategy.WORST_OF:
            overall = min(by_source.values()) if by_source else 0
        elif strategy == AggregationStrategy.MAJORITY_VOTE:
            overall = self._majority_vote(signals)
        elif strategy == AggregationStrategy.THRESHOLD_BASED:
            overall = self._threshold_based(by_source)
        else:
            overall = self._weighted_average(by_source)

        overall = round(float(overall), 2)
        status = self._score_to_status(overall)

        health = ServiceHealthScore(
            service_name=service_name,
            overall_status=status,
            overall_score=overall,
            signal_count=len(signals),
            by_source=by_source,
        )
        self._scores[service_name] = health
        logger.info(
            "service_health_agg.score_calculated",
            service_name=service_name,
            overall_score=overall,
            status=status,
        )
        return health

    def _weighted_average(
        self,
        by_source: dict[str, float],
    ) -> float:
        """Compute weighted average across sources."""
        total_weight = 0.0
        weighted_sum = 0.0
        for src_val, score in by_source.items():
            try:
                src = HealthSignalSource(src_val)
                weight = _SOURCE_WEIGHTS.get(src, 0.2)
            except ValueError:
                weight = 0.2
            weighted_sum += score * weight
            total_weight += weight
        return weighted_sum / total_weight if total_weight else 0

    def _majority_vote(
        self,
        signals: list[HealthSignal],
    ) -> float:
        """Use majority vote on status to derive score."""
        status_counts: dict[HealthStatus, int] = {}
        for s in signals:
            status_counts[s.status] = status_counts.get(s.status, 0) + 1
        majority = max(
            status_counts,
            key=lambda k: status_counts[k],
        )
        return _STATUS_SCORES.get(majority, 50.0)

    def _threshold_based(
        self,
        by_source: dict[str, float],
    ) -> float:
        """Check each source against threshold."""
        if not by_source:
            return 0.0
        below = sum(1 for v in by_source.values() if v < self._health_threshold)
        ratio = below / len(by_source)
        if ratio == 0:
            return 100.0
        if ratio < 0.3:
            return 80.0
        if ratio < 0.5:
            return 50.0
        return 20.0

    @staticmethod
    def _score_to_status(score: float) -> HealthStatus:
        """Map a numeric score to a health status."""
        if score >= 90:
            return HealthStatus.HEALTHY
        if score >= 70:
            return HealthStatus.DEGRADED
        if score >= 40:
            return HealthStatus.PARTIAL_OUTAGE
        if score > 0:
            return HealthStatus.MAJOR_OUTAGE
        return HealthStatus.UNKNOWN

    def detect_health_degradation(
        self,
        service_name: str,
    ) -> list[HealthSignal]:
        """Detect signals indicating degradation."""
        signals = [
            s
            for s in self._items
            if s.service_name == service_name and s.score < self._health_threshold
        ]
        logger.info(
            "service_health_agg.degradation_detected",
            service_name=service_name,
            count=len(signals),
        )
        return signals

    def rank_services_by_health(
        self,
    ) -> list[ServiceHealthScore]:
        """Rank all services by health score (worst first)."""
        services: set[str] = {s.service_name for s in self._items}
        scores: list[ServiceHealthScore] = []
        for svc in services:
            score = self.calculate_health_score(svc)
            scores.append(score)
        scores.sort(key=lambda s: s.overall_score)
        return scores

    def identify_flapping_services(
        self,
    ) -> list[dict[str, Any]]:
        """Identify services with frequently changing status."""
        svc_signals: dict[str, list[HealthSignal]] = {}
        for s in self._items:
            svc_signals.setdefault(
                s.service_name,
                [],
            ).append(s)

        flapping: list[dict[str, Any]] = []
        for svc, signals in svc_signals.items():
            if len(signals) < 3:
                continue
            sorted_sigs = sorted(
                signals,
                key=lambda x: x.reported_at,
            )
            changes = 0
            for i in range(1, len(sorted_sigs)):
                if sorted_sigs[i].status != sorted_sigs[i - 1].status:
                    changes += 1
            if changes >= 2:
                flapping.append(
                    {
                        "service_name": svc,
                        "signal_count": len(signals),
                        "status_changes": changes,
                        "flap_rate": round(
                            changes / (len(signals) - 1),
                            4,
                        ),
                    }
                )
        flapping.sort(
            key=lambda f: f["flap_rate"],
            reverse=True,
        )
        return flapping

    def calculate_availability_pct(
        self,
        service_name: str,
    ) -> float:
        """Calculate availability percentage from signals."""
        signals = [s for s in self._items if s.service_name == service_name]
        if not signals:
            return 0.0
        healthy = sum(1 for s in signals if s.status == HealthStatus.HEALTHY)
        return round(healthy / len(signals) * 100, 2)

    # -- Report / stats --------------------------------------------

    def generate_health_report(self) -> HealthAggReport:
        """Generate a comprehensive health report."""
        total_signals = len(self._items)
        services: set[str] = {s.service_name for s in self._items}
        total_services = len(services)

        # Source distribution
        by_source: dict[str, int] = {}
        for s in self._items:
            key = s.source.value
            by_source[key] = by_source.get(key, 0) + 1

        # Status distribution and health scores
        rankings = self.rank_services_by_health()
        by_status: dict[str, int] = {}
        total_score = 0.0
        unhealthy: list[str] = []
        for r in rankings:
            key = r.overall_status.value
            by_status[key] = by_status.get(key, 0) + 1
            total_score += r.overall_score
            if r.overall_score < self._health_threshold:
                unhealthy.append(r.service_name)
        avg_score = round(total_score / len(rankings), 2) if rankings else 0.0

        # Recommendations
        recs: list[str] = []
        if unhealthy:
            recs.append(
                f"{len(unhealthy)} service(s) below health threshold — investigate root causes"
            )
        flapping = self.identify_flapping_services()
        if flapping:
            recs.append(f"{len(flapping)} service(s) are flapping — stabilize deployments")
        outage = by_status.get(
            HealthStatus.MAJOR_OUTAGE.value,
            0,
        )
        if outage > 0:
            recs.append(f"{outage} service(s) in major outage — escalate immediately")
        unknown = by_status.get(
            HealthStatus.UNKNOWN.value,
            0,
        )
        if unknown > 0:
            recs.append(f"{unknown} service(s) have unknown status — verify monitoring")

        return HealthAggReport(
            total_services=total_services,
            total_signals=total_signals,
            avg_health_score=avg_score,
            by_status=by_status,
            by_source=by_source,
            unhealthy_services=unhealthy,
            recommendations=recs,
        )

    def clear_data(self) -> None:
        """Clear all stored data."""
        self._items.clear()
        self._scores.clear()
        logger.info("service_health_agg.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        services: set[str] = set()
        sources: dict[str, int] = {}
        statuses: dict[str, int] = {}
        total_score = 0.0
        for s in self._items:
            services.add(s.service_name)
            sources[s.source.value] = sources.get(s.source.value, 0) + 1
            statuses[s.status.value] = statuses.get(s.status.value, 0) + 1
            total_score += s.score
        total = len(self._items)
        return {
            "total_signals": total,
            "unique_services": len(services),
            "avg_signal_score": (round(total_score / total, 2) if total else 0.0),
            "source_distribution": sources,
            "status_distribution": statuses,
        }
