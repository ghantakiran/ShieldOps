"""Service Communication Mapper — map and analyze service communication patterns."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CommProtocol(StrEnum):
    HTTP = "http"
    GRPC = "grpc"
    MESSAGE_QUEUE = "message_queue"
    WEBSOCKET = "websocket"
    EVENT_STREAM = "event_stream"


class CommPattern(StrEnum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    REQUEST_REPLY = "request_reply"
    FIRE_AND_FORGET = "fire_and_forget"


class CommHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNSTABLE = "unstable"
    FAILING = "failing"
    UNKNOWN = "unknown"


# --- Models ---


class CommRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service_name: str = ""
    protocol: CommProtocol = CommProtocol.HTTP
    pattern: CommPattern = CommPattern.SYNCHRONOUS
    health: CommHealth = CommHealth.HEALTHY
    traffic_volume: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CommLink(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    source_service: str = ""
    target_service: str = ""
    protocol: CommProtocol = CommProtocol.HTTP
    health: CommHealth = CommHealth.HEALTHY
    latency_ms: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CommMapperReport(BaseModel):
    total_records: int = 0
    total_links: int = 0
    avg_traffic_volume: float = 0.0
    by_protocol: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    unhealthy_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceCommunicationMapper:
    """Map and analyze service communication patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        max_unhealthy_links: int = 10,
    ) -> None:
        self._max_records = max_records
        self._max_unhealthy_links = max_unhealthy_links
        self._records: list[CommRecord] = []
        self._links: list[CommLink] = []
        logger.info(
            "comm_mapper.initialized",
            max_records=max_records,
            max_unhealthy_links=max_unhealthy_links,
        )

    # -- record / get / list ---------------------------------------------

    def record_comm(
        self,
        service_name: str,
        protocol: CommProtocol = CommProtocol.HTTP,
        pattern: CommPattern = CommPattern.SYNCHRONOUS,
        health: CommHealth = CommHealth.HEALTHY,
        traffic_volume: float = 0.0,
        details: str = "",
    ) -> CommRecord:
        record = CommRecord(
            service_name=service_name,
            protocol=protocol,
            pattern=pattern,
            health=health,
            traffic_volume=traffic_volume,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "comm_mapper.recorded",
            record_id=record.id,
            service_name=service_name,
            health=health.value,
        )
        return record

    def get_comm(self, record_id: str) -> CommRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_comms(
        self,
        service_name: str | None = None,
        protocol: CommProtocol | None = None,
        limit: int = 50,
    ) -> list[CommRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if protocol is not None:
            results = [r for r in results if r.protocol == protocol]
        return results[-limit:]

    def add_link(
        self,
        source_service: str,
        target_service: str,
        protocol: CommProtocol = CommProtocol.HTTP,
        health: CommHealth = CommHealth.HEALTHY,
        latency_ms: float = 0.0,
        description: str = "",
    ) -> CommLink:
        link = CommLink(
            source_service=source_service,
            target_service=target_service,
            protocol=protocol,
            health=health,
            latency_ms=latency_ms,
            description=description,
        )
        self._links.append(link)
        if len(self._links) > self._max_records:
            self._links = self._links[-self._max_records :]
        logger.info(
            "comm_mapper.link_added",
            source_service=source_service,
            target_service=target_service,
            latency_ms=latency_ms,
        )
        return link

    # -- domain operations -----------------------------------------------

    def analyze_comm_patterns(self, service_name: str) -> dict[str, Any]:
        """Analyze communication patterns for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_volume = round(sum(r.traffic_volume for r in records) / len(records), 2)
        unhealthy = {CommHealth.FAILING, CommHealth.UNSTABLE}
        unhealthy_count = sum(1 for r in records if r.health in unhealthy)
        return {
            "service_name": service_name,
            "total": len(records),
            "avg_traffic_volume": avg_volume,
            "unhealthy_count": unhealthy_count,
            "within_limits": unhealthy_count <= self._max_unhealthy_links,
        }

    def identify_unhealthy_links(self) -> list[dict[str, Any]]:
        """Find links with failing or unstable health."""
        unhealthy = {CommHealth.FAILING, CommHealth.UNSTABLE}
        service_counts: dict[str, int] = {}
        for r in self._records:
            if r.health in unhealthy:
                service_counts[r.service_name] = service_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in service_counts.items():
            if count > 1:
                results.append({"service_name": name, "unhealthy_count": count})
        results.sort(key=lambda x: x["unhealthy_count"], reverse=True)
        return results

    def rank_by_traffic_volume(self) -> list[dict[str, Any]]:
        """Rank services by average traffic volume descending."""
        service_volumes: dict[str, list[float]] = {}
        for r in self._records:
            service_volumes.setdefault(r.service_name, []).append(r.traffic_volume)
        results: list[dict[str, Any]] = []
        for name, volumes in service_volumes.items():
            avg = round(sum(volumes) / len(volumes), 2)
            results.append({"service_name": name, "avg_traffic_volume": avg})
        results.sort(key=lambda x: x["avg_traffic_volume"], reverse=True)
        return results

    def detect_comm_anomalies(self) -> list[dict[str, Any]]:
        """Detect communication anomalies for services with sufficient data."""
        service_records: dict[str, list[CommRecord]] = {}
        for r in self._records:
            service_records.setdefault(r.service_name, []).append(r)
        results: list[dict[str, Any]] = []
        for name, records in service_records.items():
            if len(records) > 3:
                volumes = [r.traffic_volume for r in records]
                pattern = "spiking" if volumes[-1] > volumes[0] else "dropping"
                results.append(
                    {
                        "service_name": name,
                        "record_count": len(records),
                        "anomaly_pattern": pattern,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CommMapperReport:
        by_protocol: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_protocol[r.protocol.value] = by_protocol.get(r.protocol.value, 0) + 1
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
        avg_volume = (
            round(
                sum(r.traffic_volume for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        unhealthy = {CommHealth.FAILING, CommHealth.UNSTABLE}
        unhealthy_count = sum(1 for r in self._records if r.health in unhealthy)
        recs: list[str] = []
        if unhealthy_count > self._max_unhealthy_links:
            recs.append(
                f"{unhealthy_count} unhealthy link(s) exceeds limit of {self._max_unhealthy_links}"
            )
        elif unhealthy_count > 0:
            recs.append(f"{unhealthy_count} link(s) with failing/unstable health detected")
        if not recs:
            recs.append("Service communication health within acceptable limits")
        return CommMapperReport(
            total_records=len(self._records),
            total_links=len(self._links),
            avg_traffic_volume=avg_volume,
            by_protocol=by_protocol,
            by_health=by_health,
            unhealthy_count=unhealthy_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._links.clear()
        logger.info("comm_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        protocol_dist: dict[str, int] = {}
        for r in self._records:
            key = r.protocol.value
            protocol_dist[key] = protocol_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_links": len(self._links),
            "max_unhealthy_links": self._max_unhealthy_links,
            "protocol_distribution": protocol_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
