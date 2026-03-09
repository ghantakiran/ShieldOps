"""eBPF Network Flow Analyzer

eBPF-based network flow capture, protocol detection, latency histograms,
and connection tracking for deep network observability.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlowProtocol(StrEnum):
    TCP = "tcp"
    UDP = "udp"
    HTTP = "http"
    GRPC = "grpc"
    DNS = "dns"
    TLS = "tls"
    QUIC = "quic"
    UNKNOWN = "unknown"


class FlowDirection(StrEnum):
    INGRESS = "ingress"
    EGRESS = "egress"
    INTERNAL = "internal"
    EXTERNAL = "external"


class ConnectionState(StrEnum):
    ESTABLISHED = "established"
    SYN_SENT = "syn_sent"
    FIN_WAIT = "fin_wait"
    CLOSE_WAIT = "close_wait"
    TIME_WAIT = "time_wait"
    CLOSED = "closed"
    RESET = "reset"


# --- Models ---


class NetworkFlowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ip: str = ""
    destination_ip: str = ""
    source_port: int = 0
    destination_port: int = 0
    protocol: FlowProtocol = FlowProtocol.UNKNOWN
    direction: FlowDirection = FlowDirection.INTERNAL
    connection_state: ConnectionState = ConnectionState.ESTABLISHED
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    latency_us: float = 0.0
    retransmits: int = 0
    service: str = ""
    namespace: str = ""
    node: str = ""
    created_at: float = Field(default_factory=time.time)


class FlowAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    protocol: FlowProtocol = FlowProtocol.UNKNOWN
    analysis_score: float = 0.0
    avg_latency_us: float = 0.0
    p99_latency_us: float = 0.0
    retransmit_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NetworkFlowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_bytes: int = 0
    total_packets: int = 0
    avg_latency_us: float = 0.0
    p50_latency_us: float = 0.0
    p95_latency_us: float = 0.0
    p99_latency_us: float = 0.0
    retransmit_rate: float = 0.0
    by_protocol: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_connection_state: dict[str, int] = Field(default_factory=dict)
    top_talkers: list[dict[str, Any]] = Field(default_factory=list)
    high_latency_flows: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EbpfNetworkFlowAnalyzer:
    """eBPF Network Flow Analyzer

    eBPF-based network flow capture, protocol detection, latency histograms,
    and connection tracking.
    """

    def __init__(
        self,
        max_records: int = 200000,
        latency_threshold_us: float = 50000.0,
        retransmit_threshold: float = 0.05,
    ) -> None:
        self._max_records = max_records
        self._latency_threshold_us = latency_threshold_us
        self._retransmit_threshold = retransmit_threshold
        self._records: list[NetworkFlowRecord] = []
        self._analyses: list[FlowAnalysis] = []
        logger.info(
            "ebpf_network_flow_analyzer.initialized",
            max_records=max_records,
            latency_threshold_us=latency_threshold_us,
        )

    def add_record(
        self,
        source_ip: str,
        destination_ip: str,
        protocol: FlowProtocol = FlowProtocol.TCP,
        direction: FlowDirection = FlowDirection.INTERNAL,
        connection_state: ConnectionState = ConnectionState.ESTABLISHED,
        source_port: int = 0,
        destination_port: int = 0,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        packets_sent: int = 0,
        packets_received: int = 0,
        latency_us: float = 0.0,
        retransmits: int = 0,
        service: str = "",
        namespace: str = "",
        node: str = "",
    ) -> NetworkFlowRecord:
        record = NetworkFlowRecord(
            source_ip=source_ip,
            destination_ip=destination_ip,
            source_port=source_port,
            destination_port=destination_port,
            protocol=protocol,
            direction=direction,
            connection_state=connection_state,
            bytes_sent=bytes_sent,
            bytes_received=bytes_received,
            packets_sent=packets_sent,
            packets_received=packets_received,
            latency_us=latency_us,
            retransmits=retransmits,
            service=service,
            namespace=namespace,
            node=node,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ebpf_network_flow_analyzer.record_added",
            record_id=record.id,
            source_ip=source_ip,
            destination_ip=destination_ip,
            protocol=protocol.value,
        )
        return record

    def get_record(self, record_id: str) -> NetworkFlowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        protocol: FlowProtocol | None = None,
        direction: FlowDirection | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[NetworkFlowRecord]:
        results = list(self._records)
        if protocol is not None:
            results = [r for r in results if r.protocol == protocol]
        if direction is not None:
            results = [r for r in results if r.direction == direction]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def compute_latency_histogram(self, service: str = "") -> dict[str, Any]:
        matching = [r for r in self._records if r.latency_us > 0]
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data", "buckets": {}}
        latencies = sorted(r.latency_us for r in matching)
        n = len(latencies)
        buckets = {
            "p50": latencies[int(n * 0.50)] if n > 0 else 0.0,
            "p75": latencies[int(n * 0.75)] if n > 1 else 0.0,
            "p90": latencies[int(n * 0.90)] if n > 2 else 0.0,
            "p95": latencies[int(n * 0.95)] if n > 3 else 0.0,
            "p99": latencies[min(int(n * 0.99), n - 1)] if n > 0 else 0.0,
            "max": latencies[-1],
            "min": latencies[0],
            "avg": round(sum(latencies) / n, 2),
        }
        return {"service": service or "all", "sample_count": n, "buckets": buckets}

    def identify_top_talkers(self, top_n: int = 10) -> list[dict[str, Any]]:
        ip_traffic: dict[str, int] = {}
        for r in self._records:
            ip_traffic[r.source_ip] = ip_traffic.get(r.source_ip, 0) + r.bytes_sent
            ip_traffic[r.destination_ip] = ip_traffic.get(r.destination_ip, 0) + r.bytes_received
        ranked = sorted(ip_traffic.items(), key=lambda x: x[1], reverse=True)
        return [{"ip": ip, "total_bytes": total} for ip, total in ranked[:top_n]]

    def detect_retransmit_issues(self) -> list[dict[str, Any]]:
        svc_stats: dict[str, dict[str, int]] = {}
        for r in self._records:
            if r.service not in svc_stats:
                svc_stats[r.service] = {"packets": 0, "retransmits": 0}
            svc_stats[r.service]["packets"] += r.packets_sent + r.packets_received
            svc_stats[r.service]["retransmits"] += r.retransmits
        issues: list[dict[str, Any]] = []
        for svc, stats in svc_stats.items():
            if stats["packets"] > 0:
                rate = stats["retransmits"] / stats["packets"]
                if rate > self._retransmit_threshold:
                    issues.append(
                        {
                            "service": svc,
                            "retransmit_rate": round(rate, 4),
                            "retransmits": stats["retransmits"],
                            "total_packets": stats["packets"],
                        }
                    )
        return sorted(issues, key=lambda x: x["retransmit_rate"], reverse=True)

    def process(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        latencies = [r.latency_us for r in matching if r.latency_us > 0]
        total_bytes = sum(r.bytes_sent + r.bytes_received for r in matching)
        total_retransmits = sum(r.retransmits for r in matching)
        total_packets = sum(r.packets_sent + r.packets_received for r in matching)
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        retransmit_rate = round(total_retransmits / total_packets, 4) if total_packets > 0 else 0.0
        health = "healthy"
        if avg_latency > self._latency_threshold_us:
            health = "high_latency"
        if retransmit_rate > self._retransmit_threshold:
            health = "retransmit_issues"
        return {
            "service": service,
            "flow_count": len(matching),
            "total_bytes": total_bytes,
            "avg_latency_us": avg_latency,
            "retransmit_rate": retransmit_rate,
            "health": health,
        }

    def generate_report(self) -> NetworkFlowReport:
        by_proto: dict[str, int] = {}
        by_dir: dict[str, int] = {}
        by_state: dict[str, int] = {}
        for r in self._records:
            by_proto[r.protocol.value] = by_proto.get(r.protocol.value, 0) + 1
            by_dir[r.direction.value] = by_dir.get(r.direction.value, 0) + 1
            by_state[r.connection_state.value] = by_state.get(r.connection_state.value, 0) + 1
        latencies = sorted(r.latency_us for r in self._records if r.latency_us > 0)
        n = len(latencies)
        total_bytes = sum(r.bytes_sent + r.bytes_received for r in self._records)
        total_packets = sum(r.packets_sent + r.packets_received for r in self._records)
        total_retransmits = sum(r.retransmits for r in self._records)
        retransmit_rate = round(total_retransmits / total_packets, 4) if total_packets > 0 else 0.0
        top_talkers = self.identify_top_talkers(5)
        high_lat = [r.service for r in self._records if r.latency_us > self._latency_threshold_us]
        recs: list[str] = []
        if retransmit_rate > self._retransmit_threshold:
            recs.append(
                f"Retransmit rate {retransmit_rate:.2%} exceeds threshold "
                f"{self._retransmit_threshold:.2%}"
            )
        if high_lat:
            recs.append(f"{len(set(high_lat))} service(s) with latency above threshold")
        reset_count = by_state.get("reset", 0)
        if reset_count > 0:
            recs.append(f"{reset_count} connection resets detected — investigate drops")
        if not recs:
            recs.append("Network flow health is nominal")
        return NetworkFlowReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_bytes=total_bytes,
            total_packets=total_packets,
            avg_latency_us=round(sum(latencies) / n, 2) if n else 0.0,
            p50_latency_us=latencies[int(n * 0.50)] if n > 0 else 0.0,
            p95_latency_us=latencies[int(n * 0.95)] if n > 3 else 0.0,
            p99_latency_us=latencies[min(int(n * 0.99), n - 1)] if n > 0 else 0.0,
            retransmit_rate=retransmit_rate,
            by_protocol=by_proto,
            by_direction=by_dir,
            by_connection_state=by_state,
            top_talkers=top_talkers,
            high_latency_flows=list(set(high_lat))[:10],
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        proto_dist: dict[str, int] = {}
        for r in self._records:
            proto_dist[r.protocol.value] = proto_dist.get(r.protocol.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "latency_threshold_us": self._latency_threshold_us,
            "retransmit_threshold": self._retransmit_threshold,
            "protocol_distribution": proto_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_source_ips": len({r.source_ip for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("ebpf_network_flow_analyzer.cleared")
        return {"status": "cleared"}
