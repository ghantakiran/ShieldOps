"""Tests for shieldops.security.triage_automation_engine — TriageAutomationEngine."""

from __future__ import annotations

from shieldops.security.triage_automation_engine import (
    TriageAnalysis,
    TriageAutomationEngine,
    TriageCategory,
    TriageConfidence,
    TriageDecision,
    TriageRecord,
    TriageReport,
)


def _engine(**kw) -> TriageAutomationEngine:
    return TriageAutomationEngine(**kw)


class TestEnums:
    def test_triagedecision_val1(self):
        assert TriageDecision.ESCALATE == "escalate"

    def test_triagedecision_val2(self):
        assert TriageDecision.INVESTIGATE == "investigate"

    def test_triagedecision_val3(self):
        assert TriageDecision.SUPPRESS == "suppress"

    def test_triagedecision_val4(self):
        assert TriageDecision.AUTO_RESOLVE == "auto_resolve"

    def test_triagedecision_val5(self):
        assert TriageDecision.DEFER == "defer"

    def test_triageconfidence_val1(self):
        assert TriageConfidence.HIGH == "high"

    def test_triageconfidence_val2(self):
        assert TriageConfidence.MEDIUM == "medium"

    def test_triageconfidence_val3(self):
        assert TriageConfidence.LOW == "low"

    def test_triageconfidence_val4(self):
        assert TriageConfidence.UNCERTAIN == "uncertain"

    def test_triageconfidence_val5(self):
        assert TriageConfidence.MANUAL_REQUIRED == "manual_required"

    def test_triagecategory_val1(self):
        assert TriageCategory.TRUE_POSITIVE == "true_positive"

    def test_triagecategory_val2(self):
        assert TriageCategory.FALSE_POSITIVE == "false_positive"

    def test_triagecategory_val3(self):
        assert TriageCategory.BENIGN == "benign"

    def test_triagecategory_val4(self):
        assert TriageCategory.SUSPICIOUS == "suspicious"

    def test_triagecategory_val5(self):
        assert TriageCategory.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = TriageRecord()
        assert r.id
        assert r.alert_name == ""

    def test_analysis_defaults(self):
        a = TriageAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = TriageReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_triage(
            alert_name="test",
            triage_decision=TriageDecision.INVESTIGATE,
            triage_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.alert_name == "test"
        assert r.triage_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_triage(alert_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_triage(alert_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_triage(alert_name="a")
        eng.record_triage(alert_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_triage(alert_name="a", triage_decision=TriageDecision.ESCALATE)
        eng.record_triage(alert_name="b", triage_decision=TriageDecision.INVESTIGATE)
        assert len(eng.list_records(triage_decision=TriageDecision.ESCALATE)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_triage(alert_name="a", triage_confidence=TriageConfidence.HIGH)
        eng.record_triage(alert_name="b", triage_confidence=TriageConfidence.MEDIUM)
        assert len(eng.list_records(triage_confidence=TriageConfidence.HIGH)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_triage(alert_name="a", team="sec")
        eng.record_triage(alert_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_triage(alert_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            alert_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(alert_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_triage(
            alert_name="a", triage_decision=TriageDecision.ESCALATE, triage_score=90.0
        )
        eng.record_triage(
            alert_name="b", triage_decision=TriageDecision.ESCALATE, triage_score=70.0
        )
        result = eng.analyze_distribution()
        assert TriageDecision.ESCALATE.value in result
        assert result[TriageDecision.ESCALATE.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_triage(alert_name="a", triage_score=60.0)
        eng.record_triage(alert_name="b", triage_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_triage(alert_name="a", triage_score=50.0)
        eng.record_triage(alert_name="b", triage_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["triage_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_triage(alert_name="a", service="auth", triage_score=90.0)
        eng.record_triage(alert_name="b", service="api", triage_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(alert_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(alert_name="a", analysis_score=20.0)
        eng.add_analysis(alert_name="b", analysis_score=20.0)
        eng.add_analysis(alert_name="c", analysis_score=80.0)
        eng.add_analysis(alert_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_triage(alert_name="test", triage_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_triage(alert_name="test")
        eng.add_analysis(alert_name="test")
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
        eng.record_triage(alert_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
