"""Tests for shieldops.security.security_alert_dedup_engine — SecurityAlertDedupEngine."""

from __future__ import annotations

from shieldops.security.security_alert_dedup_engine import (
    AlertSource,
    DedupAnalysis,
    DedupRecord,
    DedupReport,
    DedupResult,
    DedupStrategy,
    SecurityAlertDedupEngine,
)


def _engine(**kw) -> SecurityAlertDedupEngine:
    return SecurityAlertDedupEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_strategy_exact_match(self):
        assert DedupStrategy.EXACT_MATCH == "exact_match"

    def test_strategy_fuzzy_match(self):
        assert DedupStrategy.FUZZY_MATCH == "fuzzy_match"

    def test_strategy_time_window(self):
        assert DedupStrategy.TIME_WINDOW == "time_window"

    def test_strategy_content_hash(self):
        assert DedupStrategy.CONTENT_HASH == "content_hash"

    def test_strategy_behavioral(self):
        assert DedupStrategy.BEHAVIORAL == "behavioral"

    def test_source_siem(self):
        assert AlertSource.SIEM == "siem"

    def test_source_ids(self):
        assert AlertSource.IDS == "ids"

    def test_source_edr(self):
        assert AlertSource.EDR == "edr"

    def test_source_cloud_security(self):
        assert AlertSource.CLOUD_SECURITY == "cloud_security"

    def test_source_custom(self):
        assert AlertSource.CUSTOM == "custom"

    def test_result_duplicate(self):
        assert DedupResult.DUPLICATE == "duplicate"

    def test_result_unique(self):
        assert DedupResult.UNIQUE == "unique"

    def test_result_near_duplicate(self):
        assert DedupResult.NEAR_DUPLICATE == "near_duplicate"

    def test_result_cluster_member(self):
        assert DedupResult.CLUSTER_MEMBER == "cluster_member"

    def test_result_ambiguous(self):
        assert DedupResult.AMBIGUOUS == "ambiguous"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dedup_record_defaults(self):
        r = DedupRecord()
        assert r.id
        assert r.alert_fingerprint == ""
        assert r.dedup_strategy == DedupStrategy.EXACT_MATCH
        assert r.alert_source == AlertSource.SIEM
        assert r.dedup_result == DedupResult.DUPLICATE
        assert r.dedup_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_dedup_analysis_defaults(self):
        c = DedupAnalysis()
        assert c.id
        assert c.alert_fingerprint == ""
        assert c.dedup_strategy == DedupStrategy.EXACT_MATCH
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_dedup_report_defaults(self):
        r = DedupReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_dedup_count == 0
        assert r.avg_dedup_score == 0.0
        assert r.by_strategy == {}
        assert r.by_source == {}
        assert r.by_result == {}
        assert r.top_low_dedup == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_dedup
# ---------------------------------------------------------------------------


class TestRecordDedup:
    def test_basic(self):
        eng = _engine()
        r = eng.record_dedup(
            alert_fingerprint="fp-001",
            dedup_strategy=DedupStrategy.FUZZY_MATCH,
            alert_source=AlertSource.EDR,
            dedup_result=DedupResult.UNIQUE,
            dedup_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.alert_fingerprint == "fp-001"
        assert r.dedup_strategy == DedupStrategy.FUZZY_MATCH
        assert r.alert_source == AlertSource.EDR
        assert r.dedup_result == DedupResult.UNIQUE
        assert r.dedup_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dedup(alert_fingerprint=f"fp-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_dedup
# ---------------------------------------------------------------------------


class TestGetDedup:
    def test_found(self):
        eng = _engine()
        r = eng.record_dedup(
            alert_fingerprint="fp-001",
            dedup_result=DedupResult.DUPLICATE,
        )
        result = eng.get_dedup(r.id)
        assert result is not None
        assert result.dedup_result == DedupResult.DUPLICATE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dedup("nonexistent") is None


# ---------------------------------------------------------------------------
# list_dedups
# ---------------------------------------------------------------------------


class TestListDedups:
    def test_list_all(self):
        eng = _engine()
        eng.record_dedup(alert_fingerprint="fp-001")
        eng.record_dedup(alert_fingerprint="fp-002")
        assert len(eng.list_dedups()) == 2

    def test_filter_by_dedup_strategy(self):
        eng = _engine()
        eng.record_dedup(
            alert_fingerprint="fp-001",
            dedup_strategy=DedupStrategy.EXACT_MATCH,
        )
        eng.record_dedup(
            alert_fingerprint="fp-002",
            dedup_strategy=DedupStrategy.FUZZY_MATCH,
        )
        results = eng.list_dedups(dedup_strategy=DedupStrategy.EXACT_MATCH)
        assert len(results) == 1

    def test_filter_by_alert_source(self):
        eng = _engine()
        eng.record_dedup(
            alert_fingerprint="fp-001",
            alert_source=AlertSource.SIEM,
        )
        eng.record_dedup(
            alert_fingerprint="fp-002",
            alert_source=AlertSource.EDR,
        )
        results = eng.list_dedups(alert_source=AlertSource.SIEM)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_dedup(alert_fingerprint="fp-001", team="security")
        eng.record_dedup(alert_fingerprint="fp-002", team="platform")
        results = eng.list_dedups(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_dedup(alert_fingerprint=f"fp-{i}")
        assert len(eng.list_dedups(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            alert_fingerprint="fp-001",
            dedup_strategy=DedupStrategy.FUZZY_MATCH,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low dedup detected",
        )
        assert a.alert_fingerprint == "fp-001"
        assert a.dedup_strategy == DedupStrategy.FUZZY_MATCH
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(alert_fingerprint=f"fp-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_dedup_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_dedup(
            alert_fingerprint="fp-001",
            dedup_strategy=DedupStrategy.EXACT_MATCH,
            dedup_score=90.0,
        )
        eng.record_dedup(
            alert_fingerprint="fp-002",
            dedup_strategy=DedupStrategy.EXACT_MATCH,
            dedup_score=70.0,
        )
        result = eng.analyze_dedup_distribution()
        assert "exact_match" in result
        assert result["exact_match"]["count"] == 2
        assert result["exact_match"]["avg_dedup_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_dedup_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_dedup_alerts
# ---------------------------------------------------------------------------


class TestIdentifyLowDedupAlerts:
    def test_detects_below_threshold(self):
        eng = _engine(dedup_effectiveness_threshold=80.0)
        eng.record_dedup(alert_fingerprint="fp-001", dedup_score=60.0)
        eng.record_dedup(alert_fingerprint="fp-002", dedup_score=90.0)
        results = eng.identify_low_dedup_alerts()
        assert len(results) == 1
        assert results[0]["alert_fingerprint"] == "fp-001"

    def test_sorted_ascending(self):
        eng = _engine(dedup_effectiveness_threshold=80.0)
        eng.record_dedup(alert_fingerprint="fp-001", dedup_score=50.0)
        eng.record_dedup(alert_fingerprint="fp-002", dedup_score=30.0)
        results = eng.identify_low_dedup_alerts()
        assert len(results) == 2
        assert results[0]["dedup_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_dedup_alerts() == []


# ---------------------------------------------------------------------------
# rank_by_dedup
# ---------------------------------------------------------------------------


class TestRankByDedup:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_dedup(alert_fingerprint="fp-001", service="auth-svc", dedup_score=90.0)
        eng.record_dedup(alert_fingerprint="fp-002", service="api-gw", dedup_score=50.0)
        results = eng.rank_by_dedup()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_dedup_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_dedup() == []


# ---------------------------------------------------------------------------
# detect_dedup_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(alert_fingerprint="fp-001", analysis_score=50.0)
        result = eng.detect_dedup_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(alert_fingerprint="fp-001", analysis_score=20.0)
        eng.add_analysis(alert_fingerprint="fp-002", analysis_score=20.0)
        eng.add_analysis(alert_fingerprint="fp-003", analysis_score=80.0)
        eng.add_analysis(alert_fingerprint="fp-004", analysis_score=80.0)
        result = eng.detect_dedup_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_dedup_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(dedup_effectiveness_threshold=80.0)
        eng.record_dedup(
            alert_fingerprint="fp-001",
            dedup_strategy=DedupStrategy.FUZZY_MATCH,
            alert_source=AlertSource.EDR,
            dedup_result=DedupResult.UNIQUE,
            dedup_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DedupReport)
        assert report.total_records == 1
        assert report.low_dedup_count == 1
        assert len(report.top_low_dedup) == 1
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
        eng.record_dedup(alert_fingerprint="fp-001")
        eng.add_analysis(alert_fingerprint="fp-001")
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
        assert stats["strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_dedup(
            alert_fingerprint="fp-001",
            dedup_strategy=DedupStrategy.EXACT_MATCH,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "exact_match" in stats["strategy_distribution"]
