"""Tests for EventDrivenTopologyMapper."""

from __future__ import annotations

from shieldops.topology.event_driven_topology_mapper import (
    CentralityLevel,
    EventDrivenTopologyMapper,
    FlowPattern,
    TopologyRole,
)


def _engine(**kw) -> EventDrivenTopologyMapper:
    return EventDrivenTopologyMapper(**kw)


class TestEnums:
    def test_flow_pattern_values(self):
        for v in FlowPattern:
            assert isinstance(v.value, str)

    def test_topology_role_values(self):
        for v in TopologyRole:
            assert isinstance(v.value, str)

    def test_centrality_level_values(self):
        for v in CentralityLevel:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(service_name="svc1")
        assert r.service_name == "svc1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(service_name=f"svc-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().record_item()
        assert r.flow_pattern == (FlowPattern.POINT_TO_POINT)


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            service_name="svc1",
            connection_count=5,
        )
        a = eng.process(r.id)
        assert hasattr(a, "service_name")
        assert a.service_name == "svc1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(service_name="svc1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_hub_services(self):
        eng = _engine()
        eng.record_item(
            service_name="svc1",
            centrality_level=CentralityLevel.HUB,
        )
        rpt = eng.generate_report()
        assert len(rpt.hub_services) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(service_name="svc1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(service_name="svc1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestMapEventFlowPaths:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            service_name="svc1",
            target_service="svc2",
        )
        result = eng.map_event_flow_paths()
        assert len(result) == 1
        assert "svc2" in result[0]["targets"]

    def test_empty(self):
        assert _engine().map_event_flow_paths() == []


class TestDetectCircularEventFlows:
    def test_with_circular(self):
        eng = _engine()
        eng.record_item(
            service_name="svc1",
            target_service="svc2",
        )
        eng.record_item(
            service_name="svc2",
            target_service="svc1",
        )
        result = eng.detect_circular_event_flows()
        assert len(result) >= 1
        assert result[0]["circular"] is True

    def test_no_circular(self):
        eng = _engine()
        eng.record_item(
            service_name="svc1",
            target_service="svc2",
        )
        result = eng.detect_circular_event_flows()
        assert result == []


class TestRankServicesByEventCentrality:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            service_name="svc1",
            connection_count=10,
            event_rate=1000.0,
        )
        eng.record_item(
            service_name="svc2",
            connection_count=2,
            event_rate=100.0,
        )
        result = eng.rank_services_by_event_centrality()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_services_by_event_centrality()
        assert r == []
