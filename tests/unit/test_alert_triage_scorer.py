"""Tests for shieldops.analytics.alert_triage_scorer — AlertTriageScorer."""

from __future__ import annotations

from shieldops.analytics.alert_triage_scorer import (
    AlertCategory,
    AlertPriority,
    AlertTriageReport,
    AlertTriageScorer,
    TriageAnalysis,
    TriageDecision,
    TriageRecord,
)


def _engine(**kw) -> AlertTriageScorer:
    return AlertTriageScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_priority_critical(self):
        assert AlertPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert AlertPriority.HIGH == "high"

    def test_priority_medium(self):
        assert AlertPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert AlertPriority.LOW == "low"

    def test_priority_informational(self):
        assert AlertPriority.INFORMATIONAL == "informational"

    def test_decision_escalate(self):
        assert TriageDecision.ESCALATE == "escalate"

    def test_decision_investigate(self):
        assert TriageDecision.INVESTIGATE == "investigate"

    def test_decision_suppress(self):
        assert TriageDecision.SUPPRESS == "suppress"

    def test_decision_auto_resolve(self):
        assert TriageDecision.AUTO_RESOLVE == "auto_resolve"

    def test_decision_defer(self):
        assert TriageDecision.DEFER == "defer"

    def test_category_security(self):
        assert AlertCategory.SECURITY == "security"

    def test_category_performance(self):
        assert AlertCategory.PERFORMANCE == "performance"

    def test_category_availability(self):
        assert AlertCategory.AVAILABILITY == "availability"

    def test_category_compliance(self):
        assert AlertCategory.COMPLIANCE == "compliance"

    def test_category_configuration(self):
        assert AlertCategory.CONFIGURATION == "configuration"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_triage_record_defaults(self):
        r = TriageRecord()
        assert r.id
        assert r.alert_name == ""
        assert r.alert_priority == AlertPriority.CRITICAL
        assert r.triage_decision == TriageDecision.ESCALATE
        assert r.alert_category == AlertCategory.SECURITY
        assert r.triage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_triage_analysis_defaults(self):
        c = TriageAnalysis()
        assert c.id
        assert c.alert_name == ""
        assert c.alert_priority == AlertPriority.CRITICAL
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_alert_triage_report_defaults(self):
        r = AlertTriageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_score_count == 0
        assert r.avg_triage_score == 0.0
        assert r.by_priority == {}
        assert r.by_decision == {}
        assert r.by_category == {}
        assert r.top_low_score == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_triage
# ---------------------------------------------------------------------------


class TestRecordTriage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_triage(
            alert_name="high-cpu-alert",
            alert_priority=AlertPriority.HIGH,
            triage_decision=TriageDecision.INVESTIGATE,
            alert_category=AlertCategory.PERFORMANCE,
            triage_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.alert_name == "high-cpu-alert"
        assert r.alert_priority == AlertPriority.HIGH
        assert r.triage_decision == TriageDecision.INVESTIGATE
        assert r.alert_category == AlertCategory.PERFORMANCE
        assert r.triage_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_triage(alert_name=f"ALERT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_triage
# ---------------------------------------------------------------------------


class TestGetTriage:
    def test_found(self):
        eng = _engine()
        r = eng.record_triage(
            alert_name="high-cpu-alert",
            alert_category=AlertCategory.SECURITY,
        )
        result = eng.get_triage(r.id)
        assert result is not None
        assert result.alert_category == AlertCategory.SECURITY

    def test_not_found(self):
        eng = _engine()
        assert eng.get_triage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_triages
# ---------------------------------------------------------------------------


class TestListTriages:
    def test_list_all(self):
        eng = _engine()
        eng.record_triage(alert_name="ALERT-001")
        eng.record_triage(alert_name="ALERT-002")
        assert len(eng.list_triages()) == 2

    def test_filter_by_alert_priority(self):
        eng = _engine()
        eng.record_triage(
            alert_name="ALERT-001",
            alert_priority=AlertPriority.CRITICAL,
        )
        eng.record_triage(
            alert_name="ALERT-002",
            alert_priority=AlertPriority.LOW,
        )
        results = eng.list_triages(alert_priority=AlertPriority.CRITICAL)
        assert len(results) == 1

    def test_filter_by_triage_decision(self):
        eng = _engine()
        eng.record_triage(
            alert_name="ALERT-001",
            triage_decision=TriageDecision.ESCALATE,
        )
        eng.record_triage(
            alert_name="ALERT-002",
            triage_decision=TriageDecision.SUPPRESS,
        )
        results = eng.list_triages(
            triage_decision=TriageDecision.ESCALATE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_triage(alert_name="ALERT-001", team="security")
        eng.record_triage(alert_name="ALERT-002", team="platform")
        results = eng.list_triages(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_triage(alert_name=f"ALERT-{i}")
        assert len(eng.list_triages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            alert_name="high-cpu-alert",
            alert_priority=AlertPriority.HIGH,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low triage score detected",
        )
        assert a.alert_name == "high-cpu-alert"
        assert a.alert_priority == AlertPriority.HIGH
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(alert_name=f"ALERT-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_triage_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeTriageDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_triage(
            alert_name="ALERT-001",
            alert_priority=AlertPriority.CRITICAL,
            triage_score=90.0,
        )
        eng.record_triage(
            alert_name="ALERT-002",
            alert_priority=AlertPriority.CRITICAL,
            triage_score=70.0,
        )
        result = eng.analyze_triage_distribution()
        assert "critical" in result
        assert result["critical"]["count"] == 2
        assert result["critical"]["avg_triage_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_triage_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_score_triages
# ---------------------------------------------------------------------------


class TestIdentifyLowScoreTriages:
    def test_detects_below_threshold(self):
        eng = _engine(triage_score_threshold=80.0)
        eng.record_triage(alert_name="ALERT-001", triage_score=60.0)
        eng.record_triage(alert_name="ALERT-002", triage_score=90.0)
        results = eng.identify_low_score_triages()
        assert len(results) == 1
        assert results[0]["alert_name"] == "ALERT-001"

    def test_sorted_ascending(self):
        eng = _engine(triage_score_threshold=80.0)
        eng.record_triage(alert_name="ALERT-001", triage_score=50.0)
        eng.record_triage(alert_name="ALERT-002", triage_score=30.0)
        results = eng.identify_low_score_triages()
        assert len(results) == 2
        assert results[0]["triage_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_score_triages() == []


# ---------------------------------------------------------------------------
# rank_by_triage_score
# ---------------------------------------------------------------------------


class TestRankByTriageScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_triage(alert_name="ALERT-001", service="auth-svc", triage_score=90.0)
        eng.record_triage(alert_name="ALERT-002", service="api-gw", triage_score=50.0)
        results = eng.rank_by_triage_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_triage_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_triage_score() == []


# ---------------------------------------------------------------------------
# detect_triage_trends
# ---------------------------------------------------------------------------


class TestDetectTriageTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(alert_name="ALERT-001", analysis_score=50.0)
        result = eng.detect_triage_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(alert_name="ALERT-001", analysis_score=20.0)
        eng.add_analysis(alert_name="ALERT-002", analysis_score=20.0)
        eng.add_analysis(alert_name="ALERT-003", analysis_score=80.0)
        eng.add_analysis(alert_name="ALERT-004", analysis_score=80.0)
        result = eng.detect_triage_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_triage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(triage_score_threshold=80.0)
        eng.record_triage(
            alert_name="high-cpu-alert",
            alert_priority=AlertPriority.HIGH,
            triage_decision=TriageDecision.INVESTIGATE,
            alert_category=AlertCategory.PERFORMANCE,
            triage_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AlertTriageReport)
        assert report.total_records == 1
        assert report.low_score_count == 1
        assert len(report.top_low_score) == 1
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
        eng.record_triage(alert_name="ALERT-001")
        eng.add_analysis(alert_name="ALERT-001")
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
        assert stats["priority_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_triage(
            alert_name="ALERT-001",
            alert_priority=AlertPriority.CRITICAL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "critical" in stats["priority_distribution"]
