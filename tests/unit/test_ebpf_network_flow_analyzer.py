"""Tests for shieldops.observability.ebpf_network_flow_analyzer — EbpfNetworkFlowAnalyzer."""

from __future__ import annotations

from shieldops.observability.ebpf_network_flow_analyzer import (
    ConnectionState,
    EbpfNetworkFlowAnalyzer,
    FlowDirection,
    FlowProtocol,
    NetworkFlowRecord,
    NetworkFlowReport,
)


def _engine(**kw) -> EbpfNetworkFlowAnalyzer:
    return EbpfNetworkFlowAnalyzer(**kw)


class TestEnums:
    def test_protocol_tcp(self):
        assert FlowProtocol.TCP == "tcp"

    def test_protocol_grpc(self):
        assert FlowProtocol.GRPC == "grpc"

    def test_direction_ingress(self):
        assert FlowDirection.INGRESS == "ingress"

    def test_connection_state_established(self):
        assert ConnectionState.ESTABLISHED == "established"


class TestModels:
    def test_record_defaults(self):
        r = NetworkFlowRecord()
        assert r.id
        assert r.source_ip == ""
        assert r.protocol == FlowProtocol.UNKNOWN

    def test_report_defaults(self):
        r = NetworkFlowReport()
        assert r.id
        assert r.total_records == 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(source_ip="10.0.0.1", destination_ip="10.0.0.2")
        assert rec.source_ip == "10.0.0.1"
        assert rec.destination_ip == "10.0.0.2"

    def test_with_protocol(self):
        eng = _engine()
        rec = eng.add_record(
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
            protocol=FlowProtocol.HTTP,
        )
        assert rec.protocol == FlowProtocol.HTTP

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(source_ip=f"10.0.0.{i}", destination_ip="10.0.0.99")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(source_ip="10.0.0.1", destination_ip="10.0.0.2", service="api")
        result = eng.process("api")
        assert result.get("service") == "api" or result.get("count", 0) >= 1

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result.get("status") == "no_data" or result.get("count", 0) == 0


class TestComputeLatencyHistogram:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            source_ip="10.0.0.1", destination_ip="10.0.0.2", latency_us=100.0, service="svc-a"
        )
        eng.add_record(
            source_ip="10.0.0.1", destination_ip="10.0.0.2", latency_us=200.0, service="svc-a"
        )
        result = eng.compute_latency_histogram("svc-a")
        assert isinstance(result, dict)


class TestTopTalkers:
    def test_basic(self):
        eng = _engine()
        for i in range(5):
            eng.add_record(source_ip="10.0.0.1", destination_ip="10.0.0.2", bytes_sent=1000 * i)
        result = eng.identify_top_talkers()
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(source_ip="10.0.0.1", destination_ip="10.0.0.2")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(source_ip="10.0.0.1", destination_ip="10.0.0.2")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(source_ip="10.0.0.1", destination_ip="10.0.0.2")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
