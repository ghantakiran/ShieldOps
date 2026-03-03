"""Tests for shieldops.sla.organizational_sla_tracker."""

from __future__ import annotations

from shieldops.sla.organizational_sla_tracker import (
    ComplianceStatus,
    OrganizationalSLATracker,
    SLAAnalysis,
    SLARecord,
    SLAReport,
    SLAType,
    StakeholderLevel,
)


def _engine(**kw) -> OrganizationalSLATracker:
    return OrganizationalSLATracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_availability(self):
        assert SLAType.AVAILABILITY == "availability"

    def test_type_response_time(self):
        assert SLAType.RESPONSE_TIME == "response_time"

    def test_type_resolution_time(self):
        assert SLAType.RESOLUTION_TIME == "resolution_time"

    def test_type_throughput(self):
        assert SLAType.THROUGHPUT == "throughput"

    def test_type_error_rate(self):
        assert SLAType.ERROR_RATE == "error_rate"

    def test_status_meeting(self):
        assert ComplianceStatus.MEETING == "meeting"

    def test_status_at_risk(self):
        assert ComplianceStatus.AT_RISK == "at_risk"

    def test_status_breaching(self):
        assert ComplianceStatus.BREACHING == "breaching"

    def test_status_breached(self):
        assert ComplianceStatus.BREACHED == "breached"

    def test_status_exempt(self):
        assert ComplianceStatus.EXEMPT == "exempt"

    def test_stakeholder_executive(self):
        assert StakeholderLevel.EXECUTIVE == "executive"

    def test_stakeholder_director(self):
        assert StakeholderLevel.DIRECTOR == "director"

    def test_stakeholder_manager(self):
        assert StakeholderLevel.MANAGER == "manager"

    def test_stakeholder_team(self):
        assert StakeholderLevel.TEAM == "team"

    def test_stakeholder_individual(self):
        assert StakeholderLevel.INDIVIDUAL == "individual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_sla_record_defaults(self):
        r = SLARecord()
        assert r.id
        assert r.service == ""
        assert r.team == ""
        assert r.sla_type == SLAType.AVAILABILITY
        assert r.compliance_status == ComplianceStatus.MEETING
        assert r.stakeholder_level == StakeholderLevel.TEAM
        assert r.compliance_score == 0.0
        assert r.target_pct == 0.0
        assert r.created_at > 0

    def test_sla_analysis_defaults(self):
        a = SLAAnalysis()
        assert a.id
        assert a.service == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_sla_report_defaults(self):
        r = SLAReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_sla_type == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_sla / get_sla
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_sla(
            service="auth-svc",
            team="platform",
            sla_type=SLAType.RESPONSE_TIME,
            compliance_status=ComplianceStatus.AT_RISK,
            stakeholder_level=StakeholderLevel.EXECUTIVE,
            compliance_score=45.0,
            target_pct=99.9,
        )
        assert r.service == "auth-svc"
        assert r.sla_type == SLAType.RESPONSE_TIME
        assert r.compliance_score == 45.0
        assert r.target_pct == 99.9

    def test_get_found(self):
        eng = _engine()
        r = eng.record_sla(service="api-gw", compliance_score=80.0)
        found = eng.get_sla(r.id)
        assert found is not None
        assert found.compliance_score == 80.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_sla("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_sla(service=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_slas
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_sla(service="auth-svc")
        eng.record_sla(service="api-gw")
        assert len(eng.list_slas()) == 2

    def test_filter_by_sla_type(self):
        eng = _engine()
        eng.record_sla(service="auth-svc", sla_type=SLAType.AVAILABILITY)
        eng.record_sla(service="api-gw", sla_type=SLAType.ERROR_RATE)
        results = eng.list_slas(sla_type=SLAType.AVAILABILITY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_sla(service="auth-svc", team="platform")
        eng.record_sla(service="api-gw", team="sre")
        results = eng.list_slas(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_sla(service=f"svc-{i}")
        assert len(eng.list_slas(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            service="auth-svc",
            sla_type=SLAType.AVAILABILITY,
            analysis_score=40.0,
            threshold=50.0,
            breached=True,
            description="availability breach",
        )
        assert a.service == "auth-svc"
        assert a.analysis_score == 40.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(service=f"svc-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(service="auth-svc")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_sla(
            service="auth-svc",
            sla_type=SLAType.AVAILABILITY,
            compliance_score=80.0,
        )
        eng.record_sla(
            service="api-gw",
            sla_type=SLAType.AVAILABILITY,
            compliance_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "availability" in result
        assert result["availability"]["count"] == 2
        assert result["availability"]["avg_compliance_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_sla_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_sla(service="auth-svc", compliance_score=30.0)
        eng.record_sla(service="api-gw", compliance_score=80.0)
        results = eng.identify_sla_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "auth-svc"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_sla(service="auth-svc", compliance_score=50.0)
        eng.record_sla(service="api-gw", compliance_score=30.0)
        results = eng.identify_sla_gaps()
        assert results[0]["compliance_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_sla(service="auth-svc", compliance_score=90.0)
        eng.record_sla(service="api-gw", compliance_score=40.0)
        results = eng.rank_by_compliance()
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_sla_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(service="auth-svc", analysis_score=50.0)
        result = eng.detect_sla_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(service="a", analysis_score=20.0)
        eng.add_analysis(service="b", analysis_score=20.0)
        eng.add_analysis(service="c", analysis_score=80.0)
        eng.add_analysis(service="d", analysis_score=80.0)
        result = eng.detect_sla_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_sla_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_sla(
            service="auth-svc",
            sla_type=SLAType.AVAILABILITY,
            compliance_status=ComplianceStatus.BREACHED,
            compliance_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SLAReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_sla(service="auth-svc")
        eng.add_analysis(service="auth-svc")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_sla(service="auth-svc", team="platform", sla_type=SLAType.AVAILABILITY)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "availability" in stats["sla_type_distribution"]
        assert stats["unique_services"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(service=f"svc-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
