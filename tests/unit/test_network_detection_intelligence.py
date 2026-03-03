"""Tests for shieldops.security.network_detection_intelligence — NetworkDetectionIntelligence."""

from __future__ import annotations

from shieldops.security.network_detection_intelligence import (
    NetworkDetectionIntelligence,
    NetworkDetectionReport,
    NetworkSource,
    NetworkThreat,
    NetworkThreatAnalysis,
    NetworkThreatRecord,
    ThreatConfidence,
)


def _engine(**kw) -> NetworkDetectionIntelligence:
    return NetworkDetectionIntelligence(**kw)


class TestEnums:
    def test_network_threat_lateral_movement(self):
        assert NetworkThreat.LATERAL_MOVEMENT == "lateral_movement"

    def test_network_threat_exfiltration(self):
        assert NetworkThreat.EXFILTRATION == "exfiltration"

    def test_network_threat_c2_communication(self):
        assert NetworkThreat.C2_COMMUNICATION == "c2_communication"

    def test_network_threat_scanning(self):
        assert NetworkThreat.SCANNING == "scanning"

    def test_network_threat_anomalous_flow(self):
        assert NetworkThreat.ANOMALOUS_FLOW == "anomalous_flow"

    def test_network_source_flow_data(self):
        assert NetworkSource.FLOW_DATA == "flow_data"

    def test_network_source_packet_capture(self):
        assert NetworkSource.PACKET_CAPTURE == "packet_capture"

    def test_network_source_dns_logs(self):
        assert NetworkSource.DNS_LOGS == "dns_logs"

    def test_network_source_proxy_logs(self):
        assert NetworkSource.PROXY_LOGS == "proxy_logs"

    def test_network_source_firewall(self):
        assert NetworkSource.FIREWALL == "firewall"

    def test_threat_confidence_confirmed(self):
        assert ThreatConfidence.CONFIRMED == "confirmed"

    def test_threat_confidence_high(self):
        assert ThreatConfidence.HIGH == "high"

    def test_threat_confidence_medium(self):
        assert ThreatConfidence.MEDIUM == "medium"

    def test_threat_confidence_low(self):
        assert ThreatConfidence.LOW == "low"

    def test_threat_confidence_benign(self):
        assert ThreatConfidence.BENIGN == "benign"


class TestModels:
    def test_record_defaults(self):
        r = NetworkThreatRecord()
        assert r.id
        assert r.name == ""
        assert r.network_threat == NetworkThreat.LATERAL_MOVEMENT
        assert r.network_source == NetworkSource.FLOW_DATA
        assert r.threat_confidence == ThreatConfidence.BENIGN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = NetworkThreatAnalysis()
        assert a.id
        assert a.name == ""
        assert a.network_threat == NetworkThreat.LATERAL_MOVEMENT
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = NetworkDetectionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_network_threat == {}
        assert r.by_network_source == {}
        assert r.by_threat_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            network_threat=NetworkThreat.LATERAL_MOVEMENT,
            network_source=NetworkSource.PACKET_CAPTURE,
            threat_confidence=ThreatConfidence.CONFIRMED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.network_threat == NetworkThreat.LATERAL_MOVEMENT
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_network_threat(self):
        eng = _engine()
        eng.record_entry(name="a", network_threat=NetworkThreat.LATERAL_MOVEMENT)
        eng.record_entry(name="b", network_threat=NetworkThreat.EXFILTRATION)
        assert len(eng.list_records(network_threat=NetworkThreat.LATERAL_MOVEMENT)) == 1

    def test_filter_by_network_source(self):
        eng = _engine()
        eng.record_entry(name="a", network_source=NetworkSource.FLOW_DATA)
        eng.record_entry(name="b", network_source=NetworkSource.PACKET_CAPTURE)
        assert len(eng.list_records(network_source=NetworkSource.FLOW_DATA)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", network_threat=NetworkThreat.EXFILTRATION, score=90.0)
        eng.record_entry(name="b", network_threat=NetworkThreat.EXFILTRATION, score=70.0)
        result = eng.analyze_distribution()
        assert "exfiltration" in result
        assert result["exfiltration"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
