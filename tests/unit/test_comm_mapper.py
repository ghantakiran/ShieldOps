"""Tests for shieldops.topology.comm_mapper — ServiceCommunicationMapper."""

from __future__ import annotations

from shieldops.topology.comm_mapper import (
    CommHealth,
    CommLink,
    CommMapperReport,
    CommPattern,
    CommProtocol,
    CommRecord,
    ServiceCommunicationMapper,
)


def _engine(**kw) -> ServiceCommunicationMapper:
    return ServiceCommunicationMapper(**kw)


class TestEnums:
    def test_protocol_http(self):
        assert CommProtocol.HTTP == "http"

    def test_protocol_grpc(self):
        assert CommProtocol.GRPC == "grpc"

    def test_protocol_message_queue(self):
        assert CommProtocol.MESSAGE_QUEUE == "message_queue"

    def test_protocol_websocket(self):
        assert CommProtocol.WEBSOCKET == "websocket"

    def test_protocol_event_stream(self):
        assert CommProtocol.EVENT_STREAM == "event_stream"

    def test_pattern_synchronous(self):
        assert CommPattern.SYNCHRONOUS == "synchronous"

    def test_pattern_asynchronous(self):
        assert CommPattern.ASYNCHRONOUS == "asynchronous"

    def test_pattern_publish_subscribe(self):
        assert CommPattern.PUBLISH_SUBSCRIBE == "publish_subscribe"

    def test_pattern_request_reply(self):
        assert CommPattern.REQUEST_REPLY == "request_reply"

    def test_pattern_fire_and_forget(self):
        assert CommPattern.FIRE_AND_FORGET == "fire_and_forget"

    def test_health_healthy(self):
        assert CommHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert CommHealth.DEGRADED == "degraded"

    def test_health_unstable(self):
        assert CommHealth.UNSTABLE == "unstable"

    def test_health_failing(self):
        assert CommHealth.FAILING == "failing"

    def test_health_unknown(self):
        assert CommHealth.UNKNOWN == "unknown"


class TestModels:
    def test_comm_record_defaults(self):
        r = CommRecord()
        assert r.id
        assert r.service_name == ""
        assert r.protocol == CommProtocol.HTTP
        assert r.pattern == CommPattern.SYNCHRONOUS
        assert r.health == CommHealth.HEALTHY
        assert r.traffic_volume == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_comm_link_defaults(self):
        r = CommLink()
        assert r.id
        assert r.source_service == ""
        assert r.target_service == ""
        assert r.protocol == CommProtocol.HTTP
        assert r.health == CommHealth.HEALTHY
        assert r.latency_ms == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CommMapperReport()
        assert r.total_records == 0
        assert r.total_links == 0
        assert r.avg_traffic_volume == 0.0
        assert r.by_protocol == {}
        assert r.by_health == {}
        assert r.unhealthy_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordComm:
    def test_basic(self):
        eng = _engine()
        r = eng.record_comm("svc-a", traffic_volume=500.0)
        assert r.service_name == "svc-a"
        assert r.traffic_volume == 500.0

    def test_with_health(self):
        eng = _engine()
        r = eng.record_comm("svc-b", health=CommHealth.DEGRADED)
        assert r.health == CommHealth.DEGRADED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_comm(f"svc-{i}")
        assert len(eng._records) == 3


class TestGetComm:
    def test_found(self):
        eng = _engine()
        r = eng.record_comm("svc-a")
        assert eng.get_comm(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_comm("nonexistent") is None


class TestListComms:
    def test_list_all(self):
        eng = _engine()
        eng.record_comm("svc-a")
        eng.record_comm("svc-b")
        assert len(eng.list_comms()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_comm("svc-a")
        eng.record_comm("svc-b")
        results = eng.list_comms(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_protocol(self):
        eng = _engine()
        eng.record_comm("svc-a", protocol=CommProtocol.GRPC)
        eng.record_comm("svc-b", protocol=CommProtocol.HTTP)
        results = eng.list_comms(protocol=CommProtocol.GRPC)
        assert len(results) == 1


class TestAddLink:
    def test_basic(self):
        eng = _engine()
        lnk = eng.add_link("svc-a", "svc-b", latency_ms=12.5)
        assert lnk.source_service == "svc-a"
        assert lnk.target_service == "svc-b"
        assert lnk.latency_ms == 12.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_link(f"src-{i}", f"tgt-{i}")
        assert len(eng._links) == 2


class TestAnalyzeCommPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_comm("svc-a", traffic_volume=200.0)
        eng.record_comm("svc-a", traffic_volume=400.0)
        result = eng.analyze_comm_patterns("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total"] == 2
        assert result["avg_traffic_volume"] == 300.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_comm_patterns("ghost")
        assert result["status"] == "no_data"


class TestIdentifyUnhealthyLinks:
    def test_with_unhealthy(self):
        eng = _engine()
        eng.record_comm("svc-a", health=CommHealth.FAILING)
        eng.record_comm("svc-a", health=CommHealth.FAILING)
        eng.record_comm("svc-b", health=CommHealth.HEALTHY)
        results = eng.identify_unhealthy_links()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unhealthy_links() == []


class TestRankByTrafficVolume:
    def test_with_data(self):
        eng = _engine()
        eng.record_comm("svc-a", traffic_volume=100.0)
        eng.record_comm("svc-b", traffic_volume=500.0)
        results = eng.rank_by_traffic_volume()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_traffic_volume"] == 500.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_traffic_volume() == []


class TestDetectCommAnomalies:
    def test_with_anomalies(self):
        eng = _engine()
        for i in range(5):
            eng.record_comm("svc-a", traffic_volume=float(100 + i * 50))
        results = eng.detect_comm_anomalies()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["anomaly_pattern"] == "spiking"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_comm_anomalies() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_comm("svc-a", health=CommHealth.FAILING)
        eng.record_comm("svc-b", health=CommHealth.HEALTHY)
        eng.add_link("svc-a", "svc-b")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_links == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_comm("svc-a")
        eng.add_link("svc-a", "svc-b")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._links) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_links"] == 0
        assert stats["protocol_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_comm("svc-a", protocol=CommProtocol.GRPC)
        eng.record_comm("svc-b", protocol=CommProtocol.HTTP)
        eng.add_link("svc-a", "svc-b")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_links"] == 1
        assert stats["unique_services"] == 2
