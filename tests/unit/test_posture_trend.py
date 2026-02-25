"""Tests for shieldops.security.posture_trend — SecurityPostureTrendAnalyzer."""

from __future__ import annotations

from shieldops.security.posture_trend import (
    PostureDomain,
    PostureRegression,
    PostureSnapshot,
    PostureTrend,
    PostureTrendReport,
    RegressionSeverity,
    SecurityPostureTrendAnalyzer,
)


def _engine(**kw) -> SecurityPostureTrendAnalyzer:
    return SecurityPostureTrendAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # PostureTrend (5)
    def test_trend_improving(self):
        assert PostureTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert PostureTrend.STABLE == "stable"

    def test_trend_declining(self):
        assert PostureTrend.DECLINING == "declining"

    def test_trend_volatile(self):
        assert PostureTrend.VOLATILE == "volatile"

    def test_trend_unassessed(self):
        assert PostureTrend.UNASSESSED == "unassessed"

    # PostureDomain (5)
    def test_domain_network(self):
        assert PostureDomain.NETWORK == "network"

    def test_domain_identity(self):
        assert PostureDomain.IDENTITY == "identity"

    def test_domain_data(self):
        assert PostureDomain.DATA == "data"

    def test_domain_application(self):
        assert PostureDomain.APPLICATION == "application"

    def test_domain_infrastructure(self):
        assert PostureDomain.INFRASTRUCTURE == "infrastructure"

    # RegressionSeverity (5)
    def test_severity_negligible(self):
        assert RegressionSeverity.NEGLIGIBLE == "negligible"

    def test_severity_minor(self):
        assert RegressionSeverity.MINOR == "minor"

    def test_severity_moderate(self):
        assert RegressionSeverity.MODERATE == "moderate"

    def test_severity_major(self):
        assert RegressionSeverity.MAJOR == "major"

    def test_severity_critical(self):
        assert RegressionSeverity.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_posture_snapshot_defaults(self):
        s = PostureSnapshot()
        assert s.id
        assert s.domain == PostureDomain.NETWORK
        assert s.score == 0.0
        assert s.max_score == 100.0
        assert s.findings_count == 0
        assert s.critical_findings == 0
        assert s.high_findings == 0
        assert s.scan_source == ""
        assert s.created_at > 0

    def test_posture_regression_defaults(self):
        r = PostureRegression()
        assert r.id
        assert r.domain == PostureDomain.NETWORK
        assert r.previous_score == 0.0
        assert r.current_score == 0.0
        assert r.delta == 0.0
        assert r.severity == RegressionSeverity.NEGLIGIBLE
        assert r.cause == ""
        assert r.created_at > 0

    def test_posture_trend_report_defaults(self):
        r = PostureTrendReport()
        assert r.total_snapshots == 0
        assert r.avg_score == 0.0
        assert r.by_domain == {}
        assert r.by_trend == {}
        assert r.regressions_detected == 0
        assert r.weakest_domains == []
        assert r.improvement_velocity == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_snapshot
# ---------------------------------------------------------------------------


class TestRecordSnapshot:
    def test_basic(self):
        eng = _engine()
        s = eng.record_snapshot(domain=PostureDomain.NETWORK, score=85.0)
        assert s.domain == PostureDomain.NETWORK
        assert s.score == 85.0
        assert s.max_score == 100.0

    def test_with_all_params(self):
        eng = _engine()
        s = eng.record_snapshot(
            domain=PostureDomain.IDENTITY,
            score=72.5,
            max_score=100.0,
            findings_count=10,
            critical_findings=2,
            high_findings=3,
            scan_source="nessus",
        )
        assert s.findings_count == 10
        assert s.critical_findings == 2
        assert s.high_findings == 3
        assert s.scan_source == "nessus"

    def test_unique_ids(self):
        eng = _engine()
        s1 = eng.record_snapshot(domain=PostureDomain.DATA, score=60.0)
        s2 = eng.record_snapshot(domain=PostureDomain.DATA, score=65.0)
        assert s1.id != s2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_snapshot(domain=PostureDomain.NETWORK, score=float(i * 10))
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_snapshot
# ---------------------------------------------------------------------------


class TestGetSnapshot:
    def test_found(self):
        eng = _engine()
        s = eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        result = eng.get_snapshot(s.id)
        assert result is not None
        assert result.score == 80.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_snapshot("nonexistent") is None


# ---------------------------------------------------------------------------
# list_snapshots
# ---------------------------------------------------------------------------


class TestListSnapshots:
    def test_list_all(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        eng.record_snapshot(domain=PostureDomain.IDENTITY, score=70.0)
        assert len(eng.list_snapshots()) == 2

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        eng.record_snapshot(domain=PostureDomain.IDENTITY, score=70.0)
        results = eng.list_snapshots(domain=PostureDomain.IDENTITY)
        assert len(results) == 1
        assert results[0].domain == PostureDomain.IDENTITY

    def test_with_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_snapshot(domain=PostureDomain.DATA, score=float(i))
        results = eng.list_snapshots(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# detect_regression
# ---------------------------------------------------------------------------


class TestDetectRegression:
    def test_regression_found_with_score_drop(self):
        eng = _engine(regression_threshold=5.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=90.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        reg = eng.detect_regression(PostureDomain.NETWORK)
        assert reg is not None
        assert reg.delta == 10.0
        assert reg.severity == RegressionSeverity.MODERATE

    def test_no_regression_with_stable_score(self):
        eng = _engine(regression_threshold=5.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=90.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=87.0)
        reg = eng.detect_regression(PostureDomain.NETWORK)
        assert reg is None

    def test_not_enough_data(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=90.0)
        reg = eng.detect_regression(PostureDomain.NETWORK)
        assert reg is None


# ---------------------------------------------------------------------------
# compute_trend
# ---------------------------------------------------------------------------


class TestComputeTrend:
    def test_improving(self):
        eng = _engine()
        for score in [70.0, 71.0, 72.0, 73.0, 74.0, 75.0]:
            eng.record_snapshot(domain=PostureDomain.DATA, score=score)
        result = eng.compute_trend(PostureDomain.DATA)
        assert result["trend"] == PostureTrend.IMPROVING.value

    def test_declining(self):
        eng = _engine()
        for score in [80.0, 79.0, 78.0, 77.0, 76.0, 75.0]:
            eng.record_snapshot(domain=PostureDomain.DATA, score=score)
        result = eng.compute_trend(PostureDomain.DATA)
        assert result["trend"] == PostureTrend.DECLINING.value


# ---------------------------------------------------------------------------
# calculate_improvement_velocity
# ---------------------------------------------------------------------------


class TestCalculateImprovementVelocity:
    def test_with_data(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=70.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        result = eng.calculate_improvement_velocity()
        assert result["overall_velocity"] > 0
        assert result["interpretation"] == "improving"
        assert PostureDomain.NETWORK.value in result["by_domain"]

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_improvement_velocity()
        assert result["overall_velocity"] == 0.0
        assert result["interpretation"] == "flat"
        assert result["by_domain"] == {}


# ---------------------------------------------------------------------------
# identify_weakest_domains
# ---------------------------------------------------------------------------


class TestIdentifyWeakestDomains:
    def test_has_weak(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=90.0)
        eng.record_snapshot(domain=PostureDomain.IDENTITY, score=40.0)
        result = eng.identify_weakest_domains()
        assert len(result) == 2
        assert result[0]["domain"] == PostureDomain.IDENTITY.value
        assert result[0]["avg_score"] == 40.0

    def test_all_equal(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        eng.record_snapshot(domain=PostureDomain.DATA, score=80.0)
        result = eng.identify_weakest_domains()
        assert len(result) == 2
        assert result[0]["avg_score"] == result[1]["avg_score"]


# ---------------------------------------------------------------------------
# rank_regressions_by_severity
# ---------------------------------------------------------------------------


class TestRankRegressionsBySeverity:
    def test_ranked_order(self):
        eng = _engine(regression_threshold=5.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=90.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=83.0)
        eng.detect_regression(PostureDomain.NETWORK)
        eng.record_snapshot(domain=PostureDomain.IDENTITY, score=95.0)
        eng.record_snapshot(domain=PostureDomain.IDENTITY, score=60.0)
        eng.detect_regression(PostureDomain.IDENTITY)
        ranked = eng.rank_regressions_by_severity()
        assert len(ranked) == 2
        assert ranked[0]["severity"] == RegressionSeverity.CRITICAL.value

    def test_empty(self):
        eng = _engine()
        assert eng.rank_regressions_by_severity() == []


# ---------------------------------------------------------------------------
# generate_trend_report
# ---------------------------------------------------------------------------


class TestGenerateTrendReport:
    def test_populated(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=85.0)
        eng.record_snapshot(domain=PostureDomain.IDENTITY, score=72.0)
        report = eng.generate_trend_report()
        assert isinstance(report, PostureTrendReport)
        assert report.total_snapshots == 2
        assert report.avg_score > 0
        assert len(report.by_domain) == 2
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_trend_report()
        assert report.total_snapshots == 0
        assert report.avg_score == 0.0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=70.0)
        eng.detect_regression(PostureDomain.NETWORK)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._regressions) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["total_regressions"] == 0
        assert stats["domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_snapshot(domain=PostureDomain.NETWORK, score=80.0)
        eng.record_snapshot(domain=PostureDomain.IDENTITY, score=70.0)
        stats = eng.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["regression_threshold"] == 5.0
        assert "network" in stats["domain_distribution"]
        assert "identity" in stats["domain_distribution"]
