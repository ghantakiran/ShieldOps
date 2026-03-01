"""Tests for shieldops.topology.service_communication — ServiceCommunicationAnalyzer."""

from __future__ import annotations

from shieldops.topology.service_communication import (
    CommunicationHealth,
    CommunicationIssue,
    CommunicationLink,
    CommunicationPattern,
    CommunicationRecord,
    ServiceCommunicationAnalyzer,
    ServiceCommunicationReport,
)


def _engine(**kw) -> ServiceCommunicationAnalyzer:
    return ServiceCommunicationAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_pattern_synchronous(self):
        assert CommunicationPattern.SYNCHRONOUS == "synchronous"

    def test_pattern_asynchronous(self):
        assert CommunicationPattern.ASYNCHRONOUS == "asynchronous"

    def test_pattern_event_driven(self):
        assert CommunicationPattern.EVENT_DRIVEN == "event_driven"

    def test_pattern_batch(self):
        assert CommunicationPattern.BATCH == "batch"

    def test_pattern_streaming(self):
        assert CommunicationPattern.STREAMING == "streaming"

    def test_health_healthy(self):
        assert CommunicationHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert CommunicationHealth.DEGRADED == "degraded"

    def test_health_failing(self):
        assert CommunicationHealth.FAILING == "failing"

    def test_health_timeout(self):
        assert CommunicationHealth.TIMEOUT == "timeout"

    def test_health_circuit_open(self):
        assert CommunicationHealth.CIRCUIT_OPEN == "circuit_open"

    def test_issue_high_latency(self):
        assert CommunicationIssue.HIGH_LATENCY == "high_latency"

    def test_issue_retry_storm(self):
        assert CommunicationIssue.RETRY_STORM == "retry_storm"

    def test_issue_circular_dependency(self):
        assert CommunicationIssue.CIRCULAR_DEPENDENCY == "circular_dependency"

    def test_issue_tight_coupling(self):
        assert CommunicationIssue.TIGHT_COUPLING == "tight_coupling"

    def test_issue_version_mismatch(self):
        assert CommunicationIssue.VERSION_MISMATCH == "version_mismatch"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_communication_record_defaults(self):
        r = CommunicationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.communication_pattern == CommunicationPattern.SYNCHRONOUS
        assert r.communication_health == CommunicationHealth.HEALTHY
        assert r.communication_issue == CommunicationIssue.HIGH_LATENCY
        assert r.anomaly_rate == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_communication_link_defaults(self):
        lk = CommunicationLink()
        assert lk.id
        assert lk.link_name == ""
        assert lk.communication_pattern == CommunicationPattern.SYNCHRONOUS
        assert lk.error_rate == 0.0
        assert lk.avg_latency_ms == 0.0
        assert lk.description == ""
        assert lk.created_at > 0

    def test_service_communication_report_defaults(self):
        r = ServiceCommunicationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_links == 0
        assert r.unhealthy_communications == 0
        assert r.avg_anomaly_rate == 0.0
        assert r.by_pattern == {}
        assert r.by_health == {}
        assert r.by_issue == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_communication
# ---------------------------------------------------------------------------


class TestRecordCommunication:
    def test_basic(self):
        eng = _engine()
        r = eng.record_communication(
            service_name="payment-svc",
            communication_pattern=CommunicationPattern.ASYNCHRONOUS,
            communication_health=CommunicationHealth.HEALTHY,
            communication_issue=CommunicationIssue.HIGH_LATENCY,
            anomaly_rate=2.5,
            team="payments",
        )
        assert r.service_name == "payment-svc"
        assert r.communication_pattern == CommunicationPattern.ASYNCHRONOUS
        assert r.communication_health == CommunicationHealth.HEALTHY
        assert r.communication_issue == CommunicationIssue.HIGH_LATENCY
        assert r.anomaly_rate == 2.5
        assert r.team == "payments"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_communication(service_name=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_communication
# ---------------------------------------------------------------------------


class TestGetCommunication:
    def test_found(self):
        eng = _engine()
        r = eng.record_communication(
            service_name="payment-svc",
            communication_pattern=CommunicationPattern.EVENT_DRIVEN,
        )
        result = eng.get_communication(r.id)
        assert result is not None
        assert result.communication_pattern == CommunicationPattern.EVENT_DRIVEN

    def test_not_found(self):
        eng = _engine()
        assert eng.get_communication("nonexistent") is None


# ---------------------------------------------------------------------------
# list_communications
# ---------------------------------------------------------------------------


class TestListCommunications:
    def test_list_all(self):
        eng = _engine()
        eng.record_communication(service_name="svc-1")
        eng.record_communication(service_name="svc-2")
        assert len(eng.list_communications()) == 2

    def test_filter_by_pattern(self):
        eng = _engine()
        eng.record_communication(
            service_name="svc-1",
            communication_pattern=CommunicationPattern.SYNCHRONOUS,
        )
        eng.record_communication(
            service_name="svc-2",
            communication_pattern=CommunicationPattern.STREAMING,
        )
        results = eng.list_communications(pattern=CommunicationPattern.SYNCHRONOUS)
        assert len(results) == 1

    def test_filter_by_health(self):
        eng = _engine()
        eng.record_communication(
            service_name="svc-1",
            communication_health=CommunicationHealth.HEALTHY,
        )
        eng.record_communication(
            service_name="svc-2",
            communication_health=CommunicationHealth.FAILING,
        )
        results = eng.list_communications(health=CommunicationHealth.HEALTHY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_communication(service_name="svc-1", team="payments")
        eng.record_communication(service_name="svc-2", team="platform")
        results = eng.list_communications(team="payments")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_communication(service_name=f"svc-{i}")
        assert len(eng.list_communications(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_link
# ---------------------------------------------------------------------------


class TestAddLink:
    def test_basic(self):
        eng = _engine()
        lk = eng.add_link(
            link_name="payment-to-auth",
            communication_pattern=CommunicationPattern.SYNCHRONOUS,
            error_rate=0.5,
            avg_latency_ms=120.0,
            description="Payment to auth link",
        )
        assert lk.link_name == "payment-to-auth"
        assert lk.communication_pattern == CommunicationPattern.SYNCHRONOUS
        assert lk.error_rate == 0.5
        assert lk.avg_latency_ms == 120.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_link(link_name=f"link-{i}")
        assert len(eng._links) == 2


# ---------------------------------------------------------------------------
# analyze_communication_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeCommunicationPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_communication(
            service_name="svc-1",
            communication_pattern=CommunicationPattern.ASYNCHRONOUS,
            anomaly_rate=4.0,
        )
        eng.record_communication(
            service_name="svc-2",
            communication_pattern=CommunicationPattern.ASYNCHRONOUS,
            anomaly_rate=6.0,
        )
        result = eng.analyze_communication_patterns()
        assert "asynchronous" in result
        assert result["asynchronous"]["count"] == 2
        assert result["asynchronous"]["avg_anomaly_rate"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_communication_patterns() == {}


# ---------------------------------------------------------------------------
# identify_unhealthy_links
# ---------------------------------------------------------------------------


class TestIdentifyUnhealthyLinks:
    def test_detects_failing(self):
        eng = _engine()
        eng.record_communication(
            service_name="svc-1",
            communication_health=CommunicationHealth.FAILING,
            anomaly_rate=15.0,
        )
        eng.record_communication(
            service_name="svc-2",
            communication_health=CommunicationHealth.HEALTHY,
        )
        results = eng.identify_unhealthy_links()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-1"

    def test_detects_circuit_open(self):
        eng = _engine()
        eng.record_communication(
            service_name="svc-1",
            communication_health=CommunicationHealth.CIRCUIT_OPEN,
        )
        results = eng.identify_unhealthy_links()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unhealthy_links() == []


# ---------------------------------------------------------------------------
# rank_by_reliability
# ---------------------------------------------------------------------------


class TestRankByReliability:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_communication(service_name="svc-1", team="payments", anomaly_rate=8.0)
        eng.record_communication(service_name="svc-2", team="payments", anomaly_rate=6.0)
        eng.record_communication(service_name="svc-3", team="platform", anomaly_rate=3.0)
        results = eng.rank_by_reliability()
        assert len(results) == 2
        assert results[0]["team"] == "payments"
        assert results[0]["avg_anomaly_rate"] == 7.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_reliability() == []


# ---------------------------------------------------------------------------
# detect_communication_anomalies
# ---------------------------------------------------------------------------


class TestDetectCommunicationAnomalies:
    def test_stable(self):
        eng = _engine()
        for s in [100.0, 100.0, 100.0, 100.0]:
            eng.add_link(link_name="lk", avg_latency_ms=s)
        result = eng.detect_communication_anomalies()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_link(link_name="lk", avg_latency_ms=s)
        result = eng.detect_communication_anomalies()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_communication_anomalies()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_communication(
            service_name="svc-1",
            communication_pattern=CommunicationPattern.SYNCHRONOUS,
            communication_health=CommunicationHealth.FAILING,
            anomaly_rate=8.0,
            team="payments",
        )
        report = eng.generate_report()
        assert isinstance(report, ServiceCommunicationReport)
        assert report.total_records == 1
        assert report.unhealthy_communications == 1
        assert report.avg_anomaly_rate == 8.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable limits" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_communication(service_name="svc-1")
        eng.add_link(link_name="lk1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._links) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_links"] == 0
        assert stats["pattern_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_communication(
            service_name="svc-1",
            communication_pattern=CommunicationPattern.ASYNCHRONOUS,
            team="payments",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "asynchronous" in stats["pattern_distribution"]
