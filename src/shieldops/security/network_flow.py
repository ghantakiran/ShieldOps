"""Network Flow Analyzer — traffic pattern analysis, anomaly detection, firewall recommendations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlowDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    LATERAL = "lateral"
    EXTERNAL = "external"


class TrafficAnomaly(StrEnum):
    NONE = "none"
    SPIKE = "spike"
    DATA_EXFILTRATION = "data_exfiltration"
    PORT_SCAN = "port_scan"
    UNUSUAL_DESTINATION = "unusual_destination"
    PROTOCOL_VIOLATION = "protocol_violation"


class RuleAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    LOG = "log"
    RATE_LIMIT = "rate_limit"


# --- Models ---


class FlowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ip: str
    dest_ip: str
    source_port: int = 0
    dest_port: int = 0
    protocol: str = "tcp"
    direction: FlowDirection = FlowDirection.INBOUND
    bytes_transferred: int = 0
    packets: int = 0
    anomaly: TrafficAnomaly = TrafficAnomaly.NONE
    created_at: float = Field(default_factory=time.time)


class FirewallRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ip: str = ""
    dest_ip: str = ""
    port: int = 0
    protocol: str = "tcp"
    action: RuleAction = RuleAction.DENY
    reason: str = ""
    confidence: float = 0.0
    created_at: float = Field(default_factory=time.time)


class FlowAnalysisSummary(BaseModel):
    total_flows: int = 0
    anomaly_count: int = 0
    top_talkers: list[dict[str, Any]] = Field(default_factory=list)
    direction_breakdown: dict[str, int] = Field(default_factory=dict)
    recommendations_count: int = 0
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class NetworkFlowAnalyzer:
    """Network traffic pattern analysis, anomaly detection, firewall rule recommendations."""

    def __init__(
        self,
        max_records: int = 500000,
        anomaly_threshold: float = 0.8,
    ) -> None:
        self._max_records = max_records
        self._anomaly_threshold = anomaly_threshold
        self._flows: list[FlowRecord] = []
        self._recommendations: list[FirewallRecommendation] = []
        logger.info(
            "network_flow.initialized",
            max_records=max_records,
            anomaly_threshold=anomaly_threshold,
        )

    # --- Constants for anomaly detection ---
    _SPIKE_BYTES = 10 * 1024 * 1024  # 10 MB
    _EXFIL_BYTES = 50 * 1024 * 1024  # 50 MB
    _PORT_SCAN_PACKETS = 1000
    _PORT_SCAN_BYTES = 1000

    def record_flow(
        self,
        source_ip: str,
        dest_ip: str,
        source_port: int = 0,
        dest_port: int = 0,
        protocol: str = "tcp",
        direction: FlowDirection = FlowDirection.INBOUND,
        bytes_transferred: int = 0,
        packets: int = 0,
    ) -> FlowRecord:
        """Record a network flow and detect anomalies."""
        anomaly = self._classify_anomaly(direction, bytes_transferred, packets)
        flow = FlowRecord(
            source_ip=source_ip,
            dest_ip=dest_ip,
            source_port=source_port,
            dest_port=dest_port,
            protocol=protocol,
            direction=direction,
            bytes_transferred=bytes_transferred,
            packets=packets,
            anomaly=anomaly,
        )
        self._flows.append(flow)
        if len(self._flows) > self._max_records:
            self._flows = self._flows[-self._max_records :]
        if anomaly != TrafficAnomaly.NONE:
            logger.warning(
                "network_flow.anomaly_detected",
                flow_id=flow.id,
                anomaly=anomaly,
                source_ip=source_ip,
                dest_ip=dest_ip,
            )
        else:
            logger.debug("network_flow.recorded", flow_id=flow.id)
        return flow

    def _classify_anomaly(
        self,
        direction: FlowDirection,
        bytes_transferred: int,
        packets: int,
    ) -> TrafficAnomaly:
        """Classify the anomaly type for a flow based on heuristics."""
        if direction == FlowDirection.OUTBOUND and bytes_transferred > self._EXFIL_BYTES:
            return TrafficAnomaly.DATA_EXFILTRATION
        if packets > self._PORT_SCAN_PACKETS and bytes_transferred < self._PORT_SCAN_BYTES:
            return TrafficAnomaly.PORT_SCAN
        if bytes_transferred > self._SPIKE_BYTES:
            return TrafficAnomaly.SPIKE
        return TrafficAnomaly.NONE

    def get_flow(self, flow_id: str) -> FlowRecord | None:
        """Retrieve a single flow by ID."""
        for flow in self._flows:
            if flow.id == flow_id:
                return flow
        return None

    def list_flows(
        self,
        direction: FlowDirection | None = None,
        anomaly: TrafficAnomaly | None = None,
        limit: int = 100,
    ) -> list[FlowRecord]:
        """List flows with optional filtering by direction and anomaly type."""
        results = list(self._flows)
        if direction is not None:
            results = [f for f in results if f.direction == direction]
        if anomaly is not None:
            results = [f for f in results if f.anomaly == anomaly]
        return results[-limit:]

    def detect_anomalies(self, limit: int = 50) -> list[FlowRecord]:
        """Return flows that have a detected anomaly."""
        anomalous = [f for f in self._flows if f.anomaly != TrafficAnomaly.NONE]
        return anomalous[-limit:]

    def get_top_talkers(self, limit: int = 10) -> list[dict[str, Any]]:
        """Aggregate bytes transferred by source IP, sorted descending."""
        ip_bytes: dict[str, int] = {}
        for flow in self._flows:
            ip_bytes[flow.source_ip] = ip_bytes.get(flow.source_ip, 0) + flow.bytes_transferred
        sorted_ips = sorted(ip_bytes.items(), key=lambda x: x[1], reverse=True)
        return [{"source_ip": ip, "total_bytes": total} for ip, total in sorted_ips[:limit]]

    def generate_firewall_recommendations(self) -> list[FirewallRecommendation]:
        """Generate firewall recommendations for each anomalous flow."""
        anomalous = [f for f in self._flows if f.anomaly != TrafficAnomaly.NONE]
        new_recs: list[FirewallRecommendation] = []
        for flow in anomalous:
            action, reason, confidence = self._recommendation_for_anomaly(flow)
            rec = FirewallRecommendation(
                source_ip=flow.source_ip,
                dest_ip=flow.dest_ip,
                port=flow.dest_port,
                protocol=flow.protocol,
                action=action,
                reason=reason,
                confidence=confidence,
            )
            new_recs.append(rec)
            self._recommendations.append(rec)
        logger.info(
            "network_flow.recommendations_generated",
            count=len(new_recs),
        )
        return new_recs

    def _recommendation_for_anomaly(self, flow: FlowRecord) -> tuple[RuleAction, str, float]:
        """Map an anomaly type to a firewall action, reason, and confidence."""
        if flow.anomaly == TrafficAnomaly.DATA_EXFILTRATION:
            return (
                RuleAction.DENY,
                f"Data exfiltration detected from {flow.source_ip} to {flow.dest_ip}",
                0.95,
            )
        if flow.anomaly == TrafficAnomaly.SPIKE:
            return (
                RuleAction.RATE_LIMIT,
                f"Traffic spike from {flow.source_ip} ({flow.bytes_transferred} bytes)",
                0.8,
            )
        if flow.anomaly == TrafficAnomaly.PORT_SCAN:
            return (
                RuleAction.LOG,
                f"Potential port scan from {flow.source_ip} ({flow.packets} packets)",
                0.7,
            )
        return (
            RuleAction.LOG,
            f"Anomalous traffic from {flow.source_ip}: {flow.anomaly}",
            0.5,
        )

    def analyze_traffic_patterns(self, source_ip: str | None = None) -> dict[str, Any]:
        """Analyze traffic patterns with direction/protocol breakdown and average bytes."""
        flows = list(self._flows)
        if source_ip is not None:
            flows = [f for f in flows if f.source_ip == source_ip]
        if not flows:
            return {
                "direction_breakdown": {},
                "protocol_breakdown": {},
                "avg_bytes": 0.0,
                "total_flows": 0,
            }
        direction_counts: dict[str, int] = {}
        protocol_counts: dict[str, int] = {}
        total_bytes = 0
        for flow in flows:
            direction_counts[flow.direction] = direction_counts.get(flow.direction, 0) + 1
            protocol_counts[flow.protocol] = protocol_counts.get(flow.protocol, 0) + 1
            total_bytes += flow.bytes_transferred
        return {
            "direction_breakdown": direction_counts,
            "protocol_breakdown": protocol_counts,
            "avg_bytes": round(total_bytes / len(flows), 2),
            "total_flows": len(flows),
        }

    def detect_data_exfiltration(self, threshold_bytes: int | None = None) -> list[FlowRecord]:
        """Detect outbound flows exceeding a byte threshold (default 50 MB)."""
        threshold = threshold_bytes if threshold_bytes is not None else self._EXFIL_BYTES
        return [
            f
            for f in self._flows
            if f.direction == FlowDirection.OUTBOUND and f.bytes_transferred > threshold
        ]

    def generate_summary(self) -> FlowAnalysisSummary:
        """Generate a comprehensive flow analysis summary."""
        anomaly_count = sum(1 for f in self._flows if f.anomaly != TrafficAnomaly.NONE)
        direction_breakdown: dict[str, int] = {}
        for flow in self._flows:
            direction_breakdown[flow.direction] = direction_breakdown.get(flow.direction, 0) + 1
        return FlowAnalysisSummary(
            total_flows=len(self._flows),
            anomaly_count=anomaly_count,
            top_talkers=self.get_top_talkers(limit=10),
            direction_breakdown=direction_breakdown,
            recommendations_count=len(self._recommendations),
        )

    def clear_data(self) -> None:
        """Clear all stored flows and recommendations."""
        self._flows.clear()
        self._recommendations.clear()
        logger.info("network_flow.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored flows and recommendations."""
        anomaly_counts: dict[str, int] = {}
        direction_counts: dict[str, int] = {}
        total_bytes = 0
        for flow in self._flows:
            if flow.anomaly != TrafficAnomaly.NONE:
                anomaly_counts[flow.anomaly] = anomaly_counts.get(flow.anomaly, 0) + 1
            direction_counts[flow.direction] = direction_counts.get(flow.direction, 0) + 1
            total_bytes += flow.bytes_transferred
        return {
            "total_flows": len(self._flows),
            "total_recommendations": len(self._recommendations),
            "anomaly_distribution": anomaly_counts,
            "direction_distribution": direction_counts,
            "total_bytes_transferred": total_bytes,
        }
