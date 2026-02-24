"""Tests for shieldops.security.network_flow — NetworkFlowAnalyzer."""

from __future__ import annotations

from shieldops.security.network_flow import (
    FirewallRecommendation,
    FlowAnalysisSummary,
    FlowDirection,
    FlowRecord,
    NetworkFlowAnalyzer,
    RuleAction,
    TrafficAnomaly,
)


def _engine(**kw) -> NetworkFlowAnalyzer:
    return NetworkFlowAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # FlowDirection (4)
    def test_direction_inbound(self):
        assert FlowDirection.INBOUND == "inbound"

    def test_direction_outbound(self):
        assert FlowDirection.OUTBOUND == "outbound"

    def test_direction_lateral(self):
        assert FlowDirection.LATERAL == "lateral"

    def test_direction_external(self):
        assert FlowDirection.EXTERNAL == "external"

    # TrafficAnomaly (6)
    def test_anomaly_none(self):
        assert TrafficAnomaly.NONE == "none"

    def test_anomaly_spike(self):
        assert TrafficAnomaly.SPIKE == "spike"

    def test_anomaly_data_exfiltration(self):
        assert TrafficAnomaly.DATA_EXFILTRATION == "data_exfiltration"

    def test_anomaly_port_scan(self):
        assert TrafficAnomaly.PORT_SCAN == "port_scan"

    def test_anomaly_unusual_destination(self):
        assert TrafficAnomaly.UNUSUAL_DESTINATION == "unusual_destination"

    def test_anomaly_protocol_violation(self):
        assert TrafficAnomaly.PROTOCOL_VIOLATION == "protocol_violation"

    # RuleAction (4)
    def test_action_allow(self):
        assert RuleAction.ALLOW == "allow"

    def test_action_deny(self):
        assert RuleAction.DENY == "deny"

    def test_action_log(self):
        assert RuleAction.LOG == "log"

    def test_action_rate_limit(self):
        assert RuleAction.RATE_LIMIT == "rate_limit"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_flow_record_defaults(self):
        f = FlowRecord(source_ip="10.0.0.1", dest_ip="10.0.0.2")
        assert f.id
        assert f.direction == FlowDirection.INBOUND
        assert f.anomaly == TrafficAnomaly.NONE
        assert f.protocol == "tcp"

    def test_firewall_recommendation_defaults(self):
        r = FirewallRecommendation()
        assert r.id
        assert r.action == RuleAction.DENY
        assert r.confidence == 0.0

    def test_flow_analysis_summary_defaults(self):
        s = FlowAnalysisSummary()
        assert s.total_flows == 0
        assert s.anomaly_count == 0
        assert s.top_talkers == []


# ---------------------------------------------------------------------------
# record_flow
# ---------------------------------------------------------------------------


class TestRecordFlow:
    def test_normal_flow_no_anomaly(self):
        eng = _engine()
        f = eng.record_flow(source_ip="10.0.0.1", dest_ip="10.0.0.2", bytes_transferred=1000)
        assert f.source_ip == "10.0.0.1"
        assert f.anomaly == TrafficAnomaly.NONE

    def test_spike_large_bytes(self):
        eng = _engine()
        f = eng.record_flow(
            source_ip="10.0.0.1",
            dest_ip="10.0.0.2",
            bytes_transferred=11 * 1024 * 1024,  # > 10 MB
        )
        assert f.anomaly == TrafficAnomaly.SPIKE

    def test_port_scan(self):
        eng = _engine()
        f = eng.record_flow(
            source_ip="10.0.0.1",
            dest_ip="10.0.0.2",
            packets=2000,  # > 1000
            bytes_transferred=500,  # < 1000
        )
        assert f.anomaly == TrafficAnomaly.PORT_SCAN

    def test_data_exfiltration(self):
        eng = _engine()
        f = eng.record_flow(
            source_ip="10.0.0.1",
            dest_ip="192.168.1.1",
            direction=FlowDirection.OUTBOUND,
            bytes_transferred=60 * 1024 * 1024,  # > 50 MB outbound
        )
        assert f.anomaly == TrafficAnomaly.DATA_EXFILTRATION

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_flow(source_ip=f"10.0.0.{i}", dest_ip="10.0.0.99")
        assert len(eng._flows) == 3


# ---------------------------------------------------------------------------
# get_flow
# ---------------------------------------------------------------------------


class TestGetFlow:
    def test_found(self):
        eng = _engine()
        f = eng.record_flow(source_ip="10.0.0.1", dest_ip="10.0.0.2")
        assert eng.get_flow(f.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_flow("nonexistent") is None


# ---------------------------------------------------------------------------
# list_flows
# ---------------------------------------------------------------------------


class TestListFlows:
    def test_list_all(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2")
        eng.record_flow("10.0.0.3", "10.0.0.4")
        assert len(eng.list_flows()) == 2

    def test_filter_direction(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", direction=FlowDirection.INBOUND)
        eng.record_flow("10.0.0.3", "10.0.0.4", direction=FlowDirection.OUTBOUND)
        results = eng.list_flows(direction=FlowDirection.OUTBOUND)
        assert len(results) == 1
        assert results[0].direction == FlowDirection.OUTBOUND

    def test_filter_anomaly(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=100)
        eng.record_flow("10.0.0.3", "10.0.0.4", bytes_transferred=11 * 1024 * 1024)
        results = eng.list_flows(anomaly=TrafficAnomaly.SPIKE)
        assert len(results) == 1
        assert results[0].anomaly == TrafficAnomaly.SPIKE


# ---------------------------------------------------------------------------
# detect_anomalies
# ---------------------------------------------------------------------------


class TestDetectAnomalies:
    def test_none(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=100)
        assert len(eng.detect_anomalies()) == 0

    def test_some_anomalies(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=100)
        eng.record_flow("10.0.0.3", "10.0.0.4", bytes_transferred=11 * 1024 * 1024)
        anomalies = eng.detect_anomalies()
        assert len(anomalies) == 1
        assert anomalies[0].anomaly != TrafficAnomaly.NONE


# ---------------------------------------------------------------------------
# get_top_talkers
# ---------------------------------------------------------------------------


class TestGetTopTalkers:
    def test_empty(self):
        eng = _engine()
        assert eng.get_top_talkers() == []

    def test_with_data(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=5000)
        eng.record_flow("10.0.0.1", "10.0.0.3", bytes_transferred=3000)
        eng.record_flow("10.0.0.9", "10.0.0.2", bytes_transferred=1000)
        top = eng.get_top_talkers(limit=2)
        assert len(top) == 2
        assert top[0]["source_ip"] == "10.0.0.1"
        assert top[0]["total_bytes"] == 8000


# ---------------------------------------------------------------------------
# generate_firewall_recommendations
# ---------------------------------------------------------------------------


class TestGenerateFirewallRecommendations:
    def test_no_anomalies(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=100)
        recs = eng.generate_firewall_recommendations()
        assert len(recs) == 0

    def test_with_anomalies(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=11 * 1024 * 1024)
        recs = eng.generate_firewall_recommendations()
        assert len(recs) == 1
        assert recs[0].action == RuleAction.RATE_LIMIT
        assert recs[0].confidence > 0.0


# ---------------------------------------------------------------------------
# analyze_traffic_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeTrafficPatterns:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_traffic_patterns()
        assert result["total_flows"] == 0
        assert result["direction_breakdown"] == {}

    def test_with_data(self):
        eng = _engine()
        eng.record_flow(
            "10.0.0.1",
            "10.0.0.2",
            direction=FlowDirection.INBOUND,
            bytes_transferred=1000,
        )
        eng.record_flow(
            "10.0.0.3",
            "10.0.0.4",
            direction=FlowDirection.OUTBOUND,
            bytes_transferred=2000,
        )
        result = eng.analyze_traffic_patterns()
        assert result["total_flows"] == 2
        assert FlowDirection.INBOUND in result["direction_breakdown"]
        assert result["avg_bytes"] == 1500.0

    def test_filter_source_ip(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=1000)
        eng.record_flow("10.0.0.9", "10.0.0.2", bytes_transferred=2000)
        result = eng.analyze_traffic_patterns(source_ip="10.0.0.1")
        assert result["total_flows"] == 1


# ---------------------------------------------------------------------------
# detect_data_exfiltration
# ---------------------------------------------------------------------------


class TestDetectDataExfiltration:
    def test_none(self):
        eng = _engine()
        eng.record_flow(
            "10.0.0.1",
            "10.0.0.2",
            direction=FlowDirection.OUTBOUND,
            bytes_transferred=1000,
        )
        assert len(eng.detect_data_exfiltration()) == 0

    def test_some(self):
        eng = _engine()
        eng.record_flow(
            "10.0.0.1",
            "10.0.0.2",
            direction=FlowDirection.OUTBOUND,
            bytes_transferred=60 * 1024 * 1024,
        )
        exfil = eng.detect_data_exfiltration()
        assert len(exfil) == 1
        assert exfil[0].direction == FlowDirection.OUTBOUND


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    def test_basic_summary(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=100)
        eng.record_flow("10.0.0.3", "10.0.0.4", bytes_transferred=11 * 1024 * 1024)
        summary = eng.generate_summary()
        assert summary.total_flows == 2
        assert summary.anomaly_count == 1
        assert len(summary.top_talkers) >= 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        eng.record_flow("10.0.0.1", "10.0.0.2", bytes_transferred=11 * 1024 * 1024)
        eng.generate_firewall_recommendations()
        eng.clear_data()
        assert len(eng._flows) == 0
        assert len(eng._recommendations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_flows"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["total_bytes_transferred"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_flow(
            "10.0.0.1",
            "10.0.0.2",
            bytes_transferred=5000,
            direction=FlowDirection.INBOUND,
        )
        eng.record_flow("10.0.0.3", "10.0.0.4", bytes_transferred=11 * 1024 * 1024)
        eng.generate_firewall_recommendations()
        stats = eng.get_stats()
        assert stats["total_flows"] == 2
        assert stats["total_recommendations"] == 1
        assert stats["total_bytes_transferred"] > 0
        assert FlowDirection.INBOUND in stats["direction_distribution"]
