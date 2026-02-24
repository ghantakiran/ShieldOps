"""Event Correlation Engine — cross-source event timeline, causal chain inference."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EventSource(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    KUBERNETES = "kubernetes"
    DEPLOYMENT = "deployment"
    DNS = "dns"
    NETWORK = "network"
    MANUAL = "manual"


class CausalityConfidence(StrEnum):
    DEFINITE = "definite"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    UNKNOWN = "unknown"


class CorrelationStrategy(StrEnum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    TOPOLOGICAL = "topological"
    HYBRID = "hybrid"


# --- Models ---


class CorrelationEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: EventSource = EventSource.METRICS
    service: str = ""
    event_type: str = ""
    description: str = ""
    severity: str = "info"
    tags: dict[str, str] = Field(default_factory=dict)
    occurred_at: float = Field(default_factory=time.time)


class CausalChain(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    root_event_id: str = ""
    chain: list[str] = Field(default_factory=list)
    confidence: CausalityConfidence = CausalityConfidence.UNKNOWN
    strategy: CorrelationStrategy = CorrelationStrategy.TEMPORAL
    services_affected: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class CorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    window_start: float = 0.0
    window_end: float = 0.0
    events_analyzed: int = 0
    causal_chains: list[CausalChain] = Field(default_factory=list)
    root_causes: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventCorrelationEngine:
    """Cross-source event timeline reconstruction, causal chain inference, root cause ranking."""

    def __init__(
        self,
        max_events: int = 500000,
        window_minutes: int = 30,
    ) -> None:
        self._max_events = max_events
        self._window_minutes = window_minutes
        self._events: list[CorrelationEvent] = []
        self._reports: list[CorrelationReport] = []
        logger.info(
            "event_correlation.initialized",
            max_events=max_events,
            window_minutes=window_minutes,
        )

    def submit_event(
        self,
        source: EventSource = EventSource.METRICS,
        service: str = "",
        event_type: str = "",
        description: str = "",
        severity: str = "info",
        tags: dict[str, str] | None = None,
        occurred_at: float | None = None,
    ) -> CorrelationEvent:
        event = CorrelationEvent(
            source=source,
            service=service,
            event_type=event_type,
            description=description,
            severity=severity,
            tags=tags or {},
            occurred_at=occurred_at or time.time(),
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]
        logger.info(
            "event_correlation.event_submitted",
            event_id=event.id,
            source=source,
            service=service,
        )
        return event

    def get_event(self, event_id: str) -> CorrelationEvent | None:
        for e in self._events:
            if e.id == event_id:
                return e
        return None

    def list_events(
        self,
        source: EventSource | None = None,
        service: str | None = None,
        limit: int = 100,
    ) -> list[CorrelationEvent]:
        results = list(self._events)
        if source is not None:
            results = [e for e in results if e.source == source]
        if service is not None:
            results = [e for e in results if e.service == service]
        return results[-limit:]

    def correlate_window(
        self,
        window_start: float | None = None,
        window_end: float | None = None,
        strategy: CorrelationStrategy = CorrelationStrategy.TEMPORAL,
    ) -> CorrelationReport:
        now = time.time()
        ws = window_start or (now - self._window_minutes * 60)
        we = window_end or now
        window_events = [e for e in self._events if ws <= e.occurred_at <= we]
        window_events.sort(key=lambda e: e.occurred_at)

        # Build causal chains by grouping temporally close events
        chains: list[CausalChain] = []
        if window_events:
            current_chain_events: list[CorrelationEvent] = [window_events[0]]
            for i in range(1, len(window_events)):
                gap = window_events[i].occurred_at - window_events[i - 1].occurred_at
                if gap <= self._window_minutes * 60 / 10:  # 1/10 of window
                    current_chain_events.append(window_events[i])
                else:
                    if len(current_chain_events) > 1:
                        services = list({e.service for e in current_chain_events if e.service})
                        chains.append(
                            CausalChain(
                                root_event_id=current_chain_events[0].id,
                                chain=[e.id for e in current_chain_events],
                                confidence=CausalityConfidence.PROBABLE
                                if len(current_chain_events) > 2
                                else CausalityConfidence.POSSIBLE,
                                strategy=strategy,
                                services_affected=services,
                            )
                        )
                    current_chain_events = [window_events[i]]
            if len(current_chain_events) > 1:
                services = list({e.service for e in current_chain_events if e.service})
                chains.append(
                    CausalChain(
                        root_event_id=current_chain_events[0].id,
                        chain=[e.id for e in current_chain_events],
                        confidence=CausalityConfidence.PROBABLE
                        if len(current_chain_events) > 2
                        else CausalityConfidence.POSSIBLE,
                        strategy=strategy,
                        services_affected=services,
                    )
                )

        report = CorrelationReport(
            window_start=ws,
            window_end=we,
            events_analyzed=len(window_events),
            causal_chains=chains,
        )
        self._reports.append(report)
        logger.info(
            "event_correlation.window_correlated",
            report_id=report.id,
            events=len(window_events),
            chains=len(chains),
        )
        return report

    def build_causal_chain(self, event_ids: list[str]) -> CausalChain:
        events = [e for e in self._events if e.id in event_ids]
        events.sort(key=lambda e: e.occurred_at)
        services = list({e.service for e in events if e.service})
        confidence = (
            CausalityConfidence.PROBABLE if len(events) > 2 else CausalityConfidence.POSSIBLE
        )
        chain = CausalChain(
            root_event_id=events[0].id if events else "",
            chain=[e.id for e in events],
            confidence=confidence,
            strategy=CorrelationStrategy.CAUSAL,
            services_affected=services,
        )
        return chain

    def rank_root_causes(self, report_id: str | None = None) -> list[dict[str, Any]]:
        if report_id:
            reports = [r for r in self._reports if r.id == report_id]
        else:
            reports = self._reports[-5:] if self._reports else []
        root_counts: dict[str, int] = {}
        for r in reports:
            for chain in r.causal_chains:
                rid = chain.root_event_id
                root_counts[rid] = root_counts.get(rid, 0) + 1
        ranked: list[dict[str, Any]] = []
        for eid, count in sorted(root_counts.items(), key=lambda x: x[1], reverse=True):
            event = self.get_event(eid)
            ranked.append(
                {
                    "event_id": eid,
                    "service": event.service if event else "unknown",
                    "event_type": event.event_type if event else "unknown",
                    "chain_count": count,
                    "rank_score": count,
                }
            )
        return ranked

    def get_timeline(
        self,
        service: str | None = None,
        window_minutes: int | None = None,
    ) -> list[dict[str, Any]]:
        now = time.time()
        wm = window_minutes or self._window_minutes
        cutoff = now - wm * 60
        events = [e for e in self._events if e.occurred_at >= cutoff]
        if service:
            events = [e for e in events if e.service == service]
        events.sort(key=lambda e: e.occurred_at)
        return [
            {
                "event_id": e.id,
                "source": e.source.value,
                "service": e.service,
                "event_type": e.event_type,
                "severity": e.severity,
                "occurred_at": e.occurred_at,
            }
            for e in events
        ]

    def list_reports(self, limit: int = 20) -> list[CorrelationReport]:
        return self._reports[-limit:]

    def clear_events(self) -> int:
        count = len(self._events)
        self._events.clear()
        self._reports.clear()
        logger.info("event_correlation.events_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        source_counts: dict[str, int] = {}
        service_counts: dict[str, int] = {}
        for e in self._events:
            source_counts[e.source] = source_counts.get(e.source, 0) + 1
            if e.service:
                service_counts[e.service] = service_counts.get(e.service, 0) + 1
        return {
            "total_events": len(self._events),
            "total_reports": len(self._reports),
            "unique_services": len(service_counts),
            "source_distribution": source_counts,
            "service_distribution": service_counts,
        }
