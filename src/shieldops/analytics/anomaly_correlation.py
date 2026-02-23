"""Anomaly Correlation Engine — correlates anomalies across services to find root causes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyType(StrEnum):
    METRIC_SPIKE = "metric_spike"
    METRIC_DROP = "metric_drop"
    ERROR_BURST = "error_burst"
    LATENCY = "latency"
    SATURATION = "saturation"
    TRAFFIC_ANOMALY = "traffic_anomaly"


class CorrelationStrength(StrEnum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    DEFINITIVE = "definitive"


# --- Models ---


class AnomalyEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    anomaly_type: AnomalyType
    metric_name: str = ""
    value: float = 0.0
    baseline: float = 0.0
    deviation_pct: float = 0.0
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorrelationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_ids: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    root_cause_service: str = ""
    correlation_strength: CorrelationStrength = CorrelationStrength.WEAK
    time_window_seconds: float = 0.0
    description: str = ""
    detected_at: float = Field(default_factory=time.time)


class CorrelationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    source_service: str
    target_service: str
    max_delay_seconds: float = 300.0
    min_confidence: float = 0.5
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AnomalyCorrelationEngine:
    """Correlates anomalies across services to find root causes."""

    def __init__(self, max_events: int = 50000, correlation_window_seconds: float = 300) -> None:
        self.max_events = max_events
        self.correlation_window_seconds = correlation_window_seconds
        self._anomalies: list[AnomalyEvent] = []
        self._correlations: list[CorrelationResult] = []
        self._rules: dict[str, CorrelationRule] = {}
        logger.info(
            "anomaly_correlation_engine.initialized",
            max_events=max_events,
            correlation_window_seconds=correlation_window_seconds,
        )

    def record_anomaly(self, service: str, anomaly_type: AnomalyType, **kw: Any) -> AnomalyEvent:
        """Record an anomaly event. Trims to max_events (FIFO)."""
        event = AnomalyEvent(service=service, anomaly_type=anomaly_type, **kw)
        self._anomalies.append(event)
        if len(self._anomalies) > self.max_events:
            self._anomalies = self._anomalies[-self.max_events :]
        logger.info(
            "anomaly_correlation_engine.anomaly_recorded",
            anomaly_id=event.id,
            service=service,
            anomaly_type=anomaly_type,
        )
        return event

    def create_rule(
        self, name: str, source_service: str, target_service: str, **kw: Any
    ) -> CorrelationRule:
        """Create a correlation rule."""
        rule = CorrelationRule(
            name=name,
            source_service=source_service,
            target_service=target_service,
            **kw,
        )
        self._rules[rule.id] = rule
        logger.info(
            "anomaly_correlation_engine.rule_created",
            rule_id=rule.id,
            name=name,
            source_service=source_service,
            target_service=target_service,
        )
        return rule

    def _determine_strength(self, count: int) -> CorrelationStrength:
        """Determine correlation strength based on number of correlated anomalies."""
        if count >= 5:
            return CorrelationStrength.DEFINITIVE
        if count >= 4:
            return CorrelationStrength.STRONG
        if count >= 3:
            return CorrelationStrength.MODERATE
        return CorrelationStrength.WEAK

    def correlate(self, time_window_seconds: float | None = None) -> list[CorrelationResult]:
        """Find correlated anomalies within a time window.

        Groups anomalies by temporal proximity. The first service with an anomaly
        in each group is considered the root_cause_service. Strength is based on
        the number of correlated anomalies.
        """
        window = time_window_seconds or self.correlation_window_seconds
        if not self._anomalies:
            return []

        sorted_anomalies = sorted(self._anomalies, key=lambda a: a.timestamp)
        used: set[str] = set()
        results: list[CorrelationResult] = []

        for i, anchor in enumerate(sorted_anomalies):
            if anchor.id in used:
                continue
            group = [anchor]
            used.add(anchor.id)
            for j in range(i + 1, len(sorted_anomalies)):
                candidate = sorted_anomalies[j]
                if candidate.id in used:
                    continue
                if candidate.timestamp - anchor.timestamp > window:
                    break
                if candidate.service != anchor.service:
                    group.append(candidate)
                    used.add(candidate.id)

            if len(group) < 2:
                used.discard(anchor.id)
                continue

            anomaly_ids = [a.id for a in group]
            services = list(dict.fromkeys(a.service for a in group))
            time_span = group[-1].timestamp - group[0].timestamp
            strength = self._determine_strength(len(group))

            result = CorrelationResult(
                anomaly_ids=anomaly_ids,
                services=services,
                root_cause_service=services[0],
                correlation_strength=strength,
                time_window_seconds=time_span,
                description=(
                    f"Correlated {len(group)} anomalies across {len(services)} services "
                    f"within {time_span:.1f}s window"
                ),
            )
            self._correlations.append(result)
            results.append(result)

        logger.info(
            "anomaly_correlation_engine.correlation_complete",
            results_count=len(results),
        )
        return results

    def get_correlations(
        self,
        service: str | None = None,
        min_strength: CorrelationStrength | None = None,
    ) -> list[CorrelationResult]:
        """List stored correlations with optional filters."""
        strength_order = [
            CorrelationStrength.WEAK,
            CorrelationStrength.MODERATE,
            CorrelationStrength.STRONG,
            CorrelationStrength.DEFINITIVE,
        ]
        results = list(self._correlations)
        if service is not None:
            results = [r for r in results if service in r.services]
        if min_strength is not None:
            min_idx = strength_order.index(min_strength)
            results = [
                r for r in results if strength_order.index(r.correlation_strength) >= min_idx
            ]
        return results

    def list_rules(self, enabled_only: bool = False) -> list[CorrelationRule]:
        """List correlation rules."""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a correlation rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(
                "anomaly_correlation_engine.rule_deleted",
                rule_id=rule_id,
            )
            return True
        return False

    def list_anomalies(
        self,
        service: str | None = None,
        anomaly_type: AnomalyType | None = None,
        limit: int = 100,
    ) -> list[AnomalyEvent]:
        """List anomaly events with optional filters."""
        results = list(self._anomalies)
        if service is not None:
            results = [a for a in results if a.service == service]
        if anomaly_type is not None:
            results = [a for a in results if a.anomaly_type == anomaly_type]
        return results[-limit:]

    def clear_anomalies(self, before_timestamp: float | None = None) -> int:
        """Remove old anomalies. Returns the number removed."""
        if before_timestamp is None:
            count = len(self._anomalies)
            self._anomalies.clear()
            logger.info(
                "anomaly_correlation_engine.anomalies_cleared",
                removed=count,
            )
            return count
        original = len(self._anomalies)
        self._anomalies = [a for a in self._anomalies if a.timestamp >= before_timestamp]
        removed = original - len(self._anomalies)
        logger.info(
            "anomaly_correlation_engine.anomalies_cleared",
            removed=removed,
            before_timestamp=before_timestamp,
        )
        return removed

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics."""
        services: set[str] = set()
        type_distribution: dict[str, int] = {}
        for a in self._anomalies:
            services.add(a.service)
            type_distribution[a.anomaly_type] = type_distribution.get(a.anomaly_type, 0) + 1
        return {
            "total_anomalies": len(self._anomalies),
            "total_correlations": len(self._correlations),
            "total_rules": len(self._rules),
            "services_affected": len(services),
            "type_distribution": type_distribution,
        }
