"""Tests for adversary_infrastructure_tracker — AdversaryInfrastructureTracker."""

from __future__ import annotations

from shieldops.security.adversary_infrastructure_tracker import (
    AdversaryInfrastructureTracker,
    InfraAnalysis,
    InfraRecord,
    InfraStatus,
    InfraTrackingReport,
    InfraType,
    TrackingPriority,
)


def _engine(**kw) -> AdversaryInfrastructureTracker:
    return AdversaryInfrastructureTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_infratype_val1(self):
        assert InfraType.C2_SERVER == "c2_server"

    def test_infratype_val2(self):
        assert InfraType.PHISHING_DOMAIN == "phishing_domain"

    def test_infratype_val3(self):
        assert InfraType.MALWARE_HOST == "malware_host"

    def test_infratype_val4(self):
        assert InfraType.PROXY_NODE == "proxy_node"

    def test_infratype_val5(self):
        assert InfraType.EXFIL_POINT == "exfil_point"

    def test_infrastatus_val1(self):
        assert InfraStatus.ACTIVE == "active"

    def test_infrastatus_val2(self):
        assert InfraStatus.INACTIVE == "inactive"

    def test_infrastatus_val3(self):
        assert InfraStatus.SEIZED == "seized"

    def test_infrastatus_val4(self):
        assert InfraStatus.SINKHOLED == "sinkholed"

    def test_infrastatus_val5(self):
        assert InfraStatus.UNKNOWN == "unknown"

    def test_trackingpriority_val1(self):
        assert TrackingPriority.CRITICAL == "critical"

    def test_trackingpriority_val2(self):
        assert TrackingPriority.HIGH == "high"

    def test_trackingpriority_val3(self):
        assert TrackingPriority.MEDIUM == "medium"

    def test_trackingpriority_val4(self):
        assert TrackingPriority.LOW == "low"

    def test_trackingpriority_val5(self):
        assert TrackingPriority.MONITORING == "monitoring"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = InfraRecord()
        assert r.id
        assert r.infra_name == ""
        assert r.infra_type == InfraType.C2_SERVER
        assert r.threat_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = InfraAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = InfraTrackingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_threat_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_priority == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_infrastructure(
            infra_name="test",
            infra_type=InfraType.PHISHING_DOMAIN,
            threat_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.infra_name == "test"
        assert r.infra_type == InfraType.PHISHING_DOMAIN
        assert r.threat_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_infrastructure(infra_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_infrastructure(infra_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_infrastructure(infra_name="a")
        eng.record_infrastructure(infra_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_infrastructure(infra_name="a", infra_type=InfraType.C2_SERVER)
        eng.record_infrastructure(infra_name="b", infra_type=InfraType.PHISHING_DOMAIN)
        results = eng.list_records(infra_type=InfraType.C2_SERVER)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_infrastructure(infra_name="a", infra_status=InfraStatus.ACTIVE)
        eng.record_infrastructure(infra_name="b", infra_status=InfraStatus.INACTIVE)
        results = eng.list_records(infra_status=InfraStatus.ACTIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_infrastructure(infra_name="a", team="sec")
        eng.record_infrastructure(infra_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_infrastructure(infra_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            infra_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(infra_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_infrastructure(
            infra_name="a",
            infra_type=InfraType.C2_SERVER,
            threat_score=90.0,
        )
        eng.record_infrastructure(
            infra_name="b",
            infra_type=InfraType.C2_SERVER,
            threat_score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "c2_server" in result
        assert result["c2_server"]["count"] == 2
        assert result["c2_server"]["avg_threat_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_infrastructure(infra_name="a", threat_score=60.0)
        eng.record_infrastructure(infra_name="b", threat_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["infra_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_infrastructure(infra_name="a", threat_score=50.0)
        eng.record_infrastructure(infra_name="b", threat_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["threat_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_infrastructure(infra_name="a", service="auth-svc", threat_score=90.0)
        eng.record_infrastructure(infra_name="b", service="api-gw", threat_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_threat_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(infra_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(infra_name="t1", analysis_score=20.0)
        eng.add_analysis(infra_name="t2", analysis_score=20.0)
        eng.add_analysis(infra_name="t3", analysis_score=80.0)
        eng.add_analysis(infra_name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_infrastructure(
            infra_name="test",
            infra_type=InfraType.PHISHING_DOMAIN,
            threat_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, InfraTrackingReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
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
        eng.record_infrastructure(infra_name="test")
        eng.add_analysis(infra_name="test")
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
        eng.record_infrastructure(
            infra_name="test",
            infra_type=InfraType.C2_SERVER,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "c2_server" in stats["type_distribution"]
