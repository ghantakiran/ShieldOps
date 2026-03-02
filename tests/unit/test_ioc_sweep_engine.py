"""Tests for shieldops.security.ioc_sweep_engine — IOCSweepEngine."""

from __future__ import annotations

from shieldops.security.ioc_sweep_engine import (
    IOCSeverity,
    IOCSweepEngine,
    SweepAnalysis,
    SweepRecord,
    SweepReport,
    SweepResult,
    SweepScope,
)


def _engine(**kw) -> IOCSweepEngine:
    return IOCSweepEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_scope_full_infrastructure(self):
        assert SweepScope.FULL_INFRASTRUCTURE == "full_infrastructure"

    def test_scope_network_only(self):
        assert SweepScope.NETWORK_ONLY == "network_only"

    def test_scope_endpoints_only(self):
        assert SweepScope.ENDPOINTS_ONLY == "endpoints_only"

    def test_scope_cloud_only(self):
        assert SweepScope.CLOUD_ONLY == "cloud_only"

    def test_scope_critical_assets(self):
        assert SweepScope.CRITICAL_ASSETS == "critical_assets"

    def test_result_match_found(self):
        assert SweepResult.MATCH_FOUND == "match_found"

    def test_result_no_match(self):
        assert SweepResult.NO_MATCH == "no_match"

    def test_result_partial_match(self):
        assert SweepResult.PARTIAL_MATCH == "partial_match"

    def test_result_error(self):
        assert SweepResult.ERROR == "error"

    def test_result_timeout(self):
        assert SweepResult.TIMEOUT == "timeout"

    def test_severity_critical(self):
        assert IOCSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert IOCSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert IOCSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert IOCSeverity.LOW == "low"

    def test_severity_informational(self):
        assert IOCSeverity.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_sweep_record_defaults(self):
        r = SweepRecord()
        assert r.id
        assert r.sweep_name == ""
        assert r.sweep_scope == SweepScope.FULL_INFRASTRUCTURE
        assert r.sweep_result == SweepResult.MATCH_FOUND
        assert r.ioc_severity == IOCSeverity.CRITICAL
        assert r.match_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_sweep_analysis_defaults(self):
        c = SweepAnalysis()
        assert c.id
        assert c.sweep_name == ""
        assert c.sweep_scope == SweepScope.FULL_INFRASTRUCTURE
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_sweep_report_defaults(self):
        r = SweepReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_match_count == 0
        assert r.avg_match_score == 0.0
        assert r.by_scope == {}
        assert r.by_result == {}
        assert r.by_severity == {}
        assert r.top_high_match == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_sweep
# ---------------------------------------------------------------------------


class TestRecordSweep:
    def test_basic(self):
        eng = _engine()
        r = eng.record_sweep(
            sweep_name="malware-hash-sweep",
            sweep_scope=SweepScope.ENDPOINTS_ONLY,
            sweep_result=SweepResult.MATCH_FOUND,
            ioc_severity=IOCSeverity.HIGH,
            match_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.sweep_name == "malware-hash-sweep"
        assert r.sweep_scope == SweepScope.ENDPOINTS_ONLY
        assert r.sweep_result == SweepResult.MATCH_FOUND
        assert r.ioc_severity == IOCSeverity.HIGH
        assert r.match_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_sweep(sweep_name=f"SWEEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_sweep
# ---------------------------------------------------------------------------


class TestGetSweep:
    def test_found(self):
        eng = _engine()
        r = eng.record_sweep(
            sweep_name="malware-hash-sweep",
            ioc_severity=IOCSeverity.CRITICAL,
        )
        result = eng.get_sweep(r.id)
        assert result is not None
        assert result.ioc_severity == IOCSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_sweep("nonexistent") is None


# ---------------------------------------------------------------------------
# list_sweeps
# ---------------------------------------------------------------------------


class TestListSweeps:
    def test_list_all(self):
        eng = _engine()
        eng.record_sweep(sweep_name="SWEEP-001")
        eng.record_sweep(sweep_name="SWEEP-002")
        assert len(eng.list_sweeps()) == 2

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_sweep(
            sweep_name="SWEEP-001",
            sweep_scope=SweepScope.FULL_INFRASTRUCTURE,
        )
        eng.record_sweep(
            sweep_name="SWEEP-002",
            sweep_scope=SweepScope.CLOUD_ONLY,
        )
        results = eng.list_sweeps(sweep_scope=SweepScope.FULL_INFRASTRUCTURE)
        assert len(results) == 1

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_sweep(
            sweep_name="SWEEP-001",
            sweep_result=SweepResult.MATCH_FOUND,
        )
        eng.record_sweep(
            sweep_name="SWEEP-002",
            sweep_result=SweepResult.NO_MATCH,
        )
        results = eng.list_sweeps(
            sweep_result=SweepResult.MATCH_FOUND,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_sweep(sweep_name="SWEEP-001", team="security")
        eng.record_sweep(sweep_name="SWEEP-002", team="platform")
        results = eng.list_sweeps(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_sweep(sweep_name=f"SWEEP-{i}")
        assert len(eng.list_sweeps(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        c = eng.add_analysis(
            sweep_name="malware-hash-sweep",
            sweep_scope=SweepScope.CRITICAL_ASSETS,
            analysis_score=88.5,
        )
        assert c.sweep_name == "malware-hash-sweep"
        assert c.sweep_scope == SweepScope.CRITICAL_ASSETS
        assert c.analysis_score == 88.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(sweep_name=f"SWEEP-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_sweep_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_sweep(
            sweep_name="SWEEP-001",
            sweep_scope=SweepScope.FULL_INFRASTRUCTURE,
            match_score=90.0,
        )
        eng.record_sweep(
            sweep_name="SWEEP-002",
            sweep_scope=SweepScope.FULL_INFRASTRUCTURE,
            match_score=70.0,
        )
        result = eng.analyze_sweep_distribution()
        assert "full_infrastructure" in result
        assert result["full_infrastructure"]["count"] == 2
        assert result["full_infrastructure"]["avg_match_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_sweep_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_match_sweeps
# ---------------------------------------------------------------------------


class TestIdentifyHighMatchSweeps:
    def test_detects_above_threshold(self):
        eng = _engine(match_score_threshold=65.0)
        eng.record_sweep(sweep_name="SWEEP-001", match_score=90.0)
        eng.record_sweep(sweep_name="SWEEP-002", match_score=40.0)
        results = eng.identify_high_match_sweeps()
        assert len(results) == 1
        assert results[0]["sweep_name"] == "SWEEP-001"

    def test_sorted_descending(self):
        eng = _engine(match_score_threshold=65.0)
        eng.record_sweep(sweep_name="SWEEP-001", match_score=80.0)
        eng.record_sweep(sweep_name="SWEEP-002", match_score=95.0)
        results = eng.identify_high_match_sweeps()
        assert len(results) == 2
        assert results[0]["match_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_match_sweeps() == []


# ---------------------------------------------------------------------------
# rank_by_match
# ---------------------------------------------------------------------------


class TestRankByMatch:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_sweep(sweep_name="SWEEP-001", service="auth-svc", match_score=50.0)
        eng.record_sweep(sweep_name="SWEEP-002", service="api-gw", match_score=90.0)
        results = eng.rank_by_match()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_match_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_match() == []


# ---------------------------------------------------------------------------
# detect_sweep_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(sweep_name="SWEEP-001", analysis_score=50.0)
        result = eng.detect_sweep_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(sweep_name="SWEEP-001", analysis_score=20.0)
        eng.add_analysis(sweep_name="SWEEP-002", analysis_score=20.0)
        eng.add_analysis(sweep_name="SWEEP-003", analysis_score=80.0)
        eng.add_analysis(sweep_name="SWEEP-004", analysis_score=80.0)
        result = eng.detect_sweep_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_sweep_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(match_score_threshold=50.0)
        eng.record_sweep(
            sweep_name="malware-hash-sweep",
            sweep_scope=SweepScope.ENDPOINTS_ONLY,
            sweep_result=SweepResult.MATCH_FOUND,
            ioc_severity=IOCSeverity.HIGH,
            match_score=85.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SweepReport)
        assert report.total_records == 1
        assert report.high_match_count == 1
        assert len(report.top_high_match) == 1
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
        eng.record_sweep(sweep_name="SWEEP-001")
        eng.add_analysis(sweep_name="SWEEP-001")
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
        assert stats["scope_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_sweep(
            sweep_name="SWEEP-001",
            sweep_scope=SweepScope.FULL_INFRASTRUCTURE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "full_infrastructure" in stats["scope_distribution"]
