"""Tests for shieldops.security.transitive_dependency_scanner."""

from __future__ import annotations

from shieldops.security.transitive_dependency_scanner import (
    DependencyDepth,
    DependencyScan,
    DependencyScanReport,
    RiskLevel,
    ScanAnalysis,
    ScanScope,
    TransitiveDependencyScanner,
)


def _engine(**kw) -> TransitiveDependencyScanner:
    return TransitiveDependencyScanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_depth_direct(self):
        assert DependencyDepth.DIRECT == "direct"

    def test_depth_first_level(self):
        assert DependencyDepth.FIRST_LEVEL == "first_level"

    def test_depth_second_level(self):
        assert DependencyDepth.SECOND_LEVEL == "second_level"

    def test_depth_deep(self):
        assert DependencyDepth.DEEP == "deep"

    def test_depth_unknown(self):
        assert DependencyDepth.UNKNOWN == "unknown"

    def test_risk_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_none(self):
        assert RiskLevel.NONE == "none"

    def test_scope_production(self):
        assert ScanScope.PRODUCTION == "production"

    def test_scope_development(self):
        assert ScanScope.DEVELOPMENT == "development"

    def test_scope_test(self):
        assert ScanScope.TEST == "test"

    def test_scope_build(self):
        assert ScanScope.BUILD == "build"

    def test_scope_all(self):
        assert ScanScope.ALL == "all"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_scan_defaults(self):
        r = DependencyScan()
        assert r.id
        assert r.package_name == ""
        assert r.dependency_depth == DependencyDepth.DIRECT
        assert r.risk_level == RiskLevel.NONE
        assert r.scan_scope == ScanScope.ALL
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_scan_analysis_defaults(self):
        c = ScanAnalysis()
        assert c.id
        assert c.package_name == ""
        assert c.dependency_depth == DependencyDepth.DIRECT
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_dependency_scan_report_defaults(self):
        r = DependencyScanReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_depth == {}
        assert r.by_risk == {}
        assert r.by_scope == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_scan / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scan(
            package_name="lodash",
            dependency_depth=DependencyDepth.DEEP,
            risk_level=RiskLevel.HIGH,
            scan_scope=ScanScope.PRODUCTION,
            risk_score=85.0,
            service="frontend",
            team="platform",
        )
        assert r.package_name == "lodash"
        assert r.dependency_depth == DependencyDepth.DEEP
        assert r.risk_level == RiskLevel.HIGH
        assert r.risk_score == 85.0
        assert r.service == "frontend"
        assert r.team == "platform"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_scan(package_name="numpy", risk_score=40.0)
        result = eng.get_scan(r.id)
        assert result is not None
        assert result.risk_score == 40.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_scan("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scan(package_name=f"pkg-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_scans
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_scan(package_name="a")
        eng.record_scan(package_name="b")
        assert len(eng.list_scans()) == 2

    def test_filter_by_depth(self):
        eng = _engine()
        eng.record_scan(package_name="a", dependency_depth=DependencyDepth.DIRECT)
        eng.record_scan(package_name="b", dependency_depth=DependencyDepth.DEEP)
        results = eng.list_scans(dependency_depth=DependencyDepth.DIRECT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_scan(package_name="a", team="security")
        eng.record_scan(package_name="b", team="platform")
        results = eng.list_scans(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_scan(package_name=f"pkg-{i}")
        assert len(eng.list_scans(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            package_name="lodash",
            dependency_depth=DependencyDepth.DEEP,
            analysis_score=88.0,
            threshold=80.0,
            breached=True,
            description="deep risk detected",
        )
        assert a.package_name == "lodash"
        assert a.dependency_depth == DependencyDepth.DEEP
        assert a.analysis_score == 88.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(package_name=f"pkg-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_risk_level(self):
        eng = _engine()
        eng.record_scan(package_name="a", risk_level=RiskLevel.HIGH)
        eng.record_scan(package_name="b", risk_level=RiskLevel.LOW)
        results = eng.list_scans(risk_level=RiskLevel.HIGH)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_depth_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_scan(package_name="a", dependency_depth=DependencyDepth.DIRECT, risk_score=80.0)
        eng.record_scan(package_name="b", dependency_depth=DependencyDepth.DIRECT, risk_score=60.0)
        result = eng.analyze_depth_distribution()
        assert "direct" in result
        assert result["direct"]["count"] == 2
        assert result["direct"]["avg_risk_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_depth_distribution() == {}


# ---------------------------------------------------------------------------
# identify_risk_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(risk_gap_threshold=70.0)
        eng.record_scan(package_name="a", risk_score=80.0)
        eng.record_scan(package_name="b", risk_score=40.0)
        results = eng.identify_risk_gaps()
        assert len(results) == 1
        assert results[0]["package_name"] == "a"

    def test_sorted_descending(self):
        eng = _engine(risk_gap_threshold=50.0)
        eng.record_scan(package_name="a", risk_score=90.0)
        eng.record_scan(package_name="b", risk_score=70.0)
        results = eng.identify_risk_gaps()
        assert len(results) == 2
        assert results[0]["risk_score"] == 90.0


# ---------------------------------------------------------------------------
# rank_by_risk
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_scan(package_name="a", service="auth-svc", risk_score=30.0)
        eng.record_scan(package_name="b", service="api-gw", risk_score=90.0)
        results = eng.rank_by_risk()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(package_name="pkg", analysis_score=50.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_risk_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(risk_gap_threshold=50.0)
        eng.record_scan(
            package_name="lodash",
            dependency_depth=DependencyDepth.DEEP,
            risk_level=RiskLevel.HIGH,
            risk_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DependencyScanReport)
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


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_scan(package_name="pkg")
        eng.add_analysis(package_name="pkg")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_scan(
            package_name="pkg",
            dependency_depth=DependencyDepth.DIRECT,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "direct" in stats["depth_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_scan(package_name=f"pkg-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].package_name == "pkg-4"
