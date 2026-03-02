"""Tests for shieldops.security.network_flow_analyzer — NetworkFlowAnalyzer."""

from __future__ import annotations

from shieldops.security.network_flow_analyzer import (
    AnalysisMethod,
    FlowAnalysis,
    FlowRecord,
    FlowReport,
    FlowSeverity,
    FlowType,
    NetworkFlowAnalyzer,
)


def _engine(**kw) -> NetworkFlowAnalyzer:
    return NetworkFlowAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_c2_beaconing(self):
        assert FlowType.C2_BEACONING == "c2_beaconing"

    def test_type_dns_tunneling(self):
        assert FlowType.DNS_TUNNELING == "dns_tunneling"

    def test_type_data_exfiltration(self):
        assert FlowType.DATA_EXFILTRATION == "data_exfiltration"

    def test_type_lateral_movement(self):
        assert FlowType.LATERAL_MOVEMENT == "lateral_movement"

    def test_type_port_scanning(self):
        assert FlowType.PORT_SCANNING == "port_scanning"

    def test_severity_critical(self):
        assert FlowSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert FlowSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert FlowSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert FlowSeverity.LOW == "low"

    def test_severity_benign(self):
        assert FlowSeverity.BENIGN == "benign"

    def test_method_pattern_matching(self):
        assert AnalysisMethod.PATTERN_MATCHING == "pattern_matching"

    def test_method_frequency_analysis(self):
        assert AnalysisMethod.FREQUENCY_ANALYSIS == "frequency_analysis"

    def test_method_volume_analysis(self):
        assert AnalysisMethod.VOLUME_ANALYSIS == "volume_analysis"

    def test_method_protocol_analysis(self):
        assert AnalysisMethod.PROTOCOL_ANALYSIS == "protocol_analysis"

    def test_method_behavioral(self):
        assert AnalysisMethod.BEHAVIORAL == "behavioral"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_flow_record_defaults(self):
        r = FlowRecord()
        assert r.id
        assert r.flow_name == ""
        assert r.flow_type == FlowType.C2_BEACONING
        assert r.flow_severity == FlowSeverity.CRITICAL
        assert r.analysis_method == AnalysisMethod.PATTERN_MATCHING
        assert r.suspicion_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_flow_analysis_defaults(self):
        c = FlowAnalysis()
        assert c.id
        assert c.flow_name == ""
        assert c.flow_type == FlowType.C2_BEACONING
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_flow_report_defaults(self):
        r = FlowReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_suspicion_count == 0
        assert r.avg_suspicion_score == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.by_method == {}
        assert r.top_high_suspicion == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_flow
# ---------------------------------------------------------------------------


class TestRecordFlow:
    def test_basic(self):
        eng = _engine()
        r = eng.record_flow(
            flow_name="flow-001",
            flow_type=FlowType.DNS_TUNNELING,
            flow_severity=FlowSeverity.HIGH,
            analysis_method=AnalysisMethod.FREQUENCY_ANALYSIS,
            suspicion_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.flow_name == "flow-001"
        assert r.flow_type == FlowType.DNS_TUNNELING
        assert r.flow_severity == FlowSeverity.HIGH
        assert r.analysis_method == AnalysisMethod.FREQUENCY_ANALYSIS
        assert r.suspicion_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_flow(flow_name=f"flow-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_flow
# ---------------------------------------------------------------------------


class TestGetFlow:
    def test_found(self):
        eng = _engine()
        r = eng.record_flow(
            flow_name="flow-001",
            flow_severity=FlowSeverity.CRITICAL,
        )
        result = eng.get_flow(r.id)
        assert result is not None
        assert result.flow_severity == FlowSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_flow("nonexistent") is None


# ---------------------------------------------------------------------------
# list_flows
# ---------------------------------------------------------------------------


class TestListFlows:
    def test_list_all(self):
        eng = _engine()
        eng.record_flow(flow_name="flow-001")
        eng.record_flow(flow_name="flow-002")
        assert len(eng.list_flows()) == 2

    def test_filter_by_flow_type(self):
        eng = _engine()
        eng.record_flow(
            flow_name="flow-001",
            flow_type=FlowType.C2_BEACONING,
        )
        eng.record_flow(
            flow_name="flow-002",
            flow_type=FlowType.DNS_TUNNELING,
        )
        results = eng.list_flows(flow_type=FlowType.C2_BEACONING)
        assert len(results) == 1

    def test_filter_by_flow_severity(self):
        eng = _engine()
        eng.record_flow(
            flow_name="flow-001",
            flow_severity=FlowSeverity.CRITICAL,
        )
        eng.record_flow(
            flow_name="flow-002",
            flow_severity=FlowSeverity.LOW,
        )
        results = eng.list_flows(flow_severity=FlowSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_flow(flow_name="flow-001", team="security")
        eng.record_flow(flow_name="flow-002", team="platform")
        results = eng.list_flows(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_flow(flow_name=f"flow-{i}")
        assert len(eng.list_flows(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            flow_name="flow-001",
            flow_type=FlowType.DNS_TUNNELING,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="high suspicion detected",
        )
        assert a.flow_name == "flow-001"
        assert a.flow_type == FlowType.DNS_TUNNELING
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(flow_name=f"flow-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_flow_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_flow(
            flow_name="flow-001",
            flow_type=FlowType.C2_BEACONING,
            suspicion_score=90.0,
        )
        eng.record_flow(
            flow_name="flow-002",
            flow_type=FlowType.C2_BEACONING,
            suspicion_score=70.0,
        )
        result = eng.analyze_flow_distribution()
        assert "c2_beaconing" in result
        assert result["c2_beaconing"]["count"] == 2
        assert result["c2_beaconing"]["avg_suspicion_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_flow_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_suspicion_flows
# ---------------------------------------------------------------------------


class TestIdentifyHighSuspicionFlows:
    def test_detects_above_threshold(self):
        eng = _engine(suspicion_score_threshold=80.0)
        eng.record_flow(flow_name="flow-001", suspicion_score=90.0)
        eng.record_flow(flow_name="flow-002", suspicion_score=60.0)
        results = eng.identify_high_suspicion_flows()
        assert len(results) == 1
        assert results[0]["flow_name"] == "flow-001"

    def test_sorted_descending(self):
        eng = _engine(suspicion_score_threshold=50.0)
        eng.record_flow(flow_name="flow-001", suspicion_score=80.0)
        eng.record_flow(flow_name="flow-002", suspicion_score=95.0)
        results = eng.identify_high_suspicion_flows()
        assert len(results) == 2
        assert results[0]["suspicion_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_suspicion_flows() == []


# ---------------------------------------------------------------------------
# rank_by_suspicion
# ---------------------------------------------------------------------------


class TestRankBySuspicion:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_flow(flow_name="flow-001", service="auth-svc", suspicion_score=50.0)
        eng.record_flow(flow_name="flow-002", service="api-gw", suspicion_score=90.0)
        results = eng.rank_by_suspicion()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_suspicion_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_suspicion() == []


# ---------------------------------------------------------------------------
# detect_flow_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(flow_name="flow-001", analysis_score=50.0)
        result = eng.detect_flow_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(flow_name="flow-001", analysis_score=20.0)
        eng.add_analysis(flow_name="flow-002", analysis_score=20.0)
        eng.add_analysis(flow_name="flow-003", analysis_score=80.0)
        eng.add_analysis(flow_name="flow-004", analysis_score=80.0)
        result = eng.detect_flow_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_flow_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(suspicion_score_threshold=80.0)
        eng.record_flow(
            flow_name="flow-001",
            flow_type=FlowType.DNS_TUNNELING,
            flow_severity=FlowSeverity.HIGH,
            analysis_method=AnalysisMethod.FREQUENCY_ANALYSIS,
            suspicion_score=95.0,
        )
        report = eng.generate_report()
        assert isinstance(report, FlowReport)
        assert report.total_records == 1
        assert report.high_suspicion_count == 1
        assert len(report.top_high_suspicion) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_flow(flow_name="flow-001")
        eng.add_analysis(flow_name="flow-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_flow(
            flow_name="flow-001",
            flow_type=FlowType.C2_BEACONING,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "c2_beaconing" in stats["type_distribution"]
