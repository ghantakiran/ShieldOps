"""Tests for shieldops.security.alert_triage_intelligence — AlertTriageIntelligence."""

from __future__ import annotations

from shieldops.security.alert_triage_intelligence import (
    AlertTriageIntelligence,
    AlertTriageReport,
    TriageAnalysis,
    TriageDecision,
    TriagePriority,
    TriageRecord,
    TriageSource,
)


def _engine(**kw) -> AlertTriageIntelligence:
    return AlertTriageIntelligence(**kw)


class TestEnums:
    def test_triage_priority_p1_critical(self):
        assert TriagePriority.P1_CRITICAL == "p1_critical"

    def test_triage_priority_p2_high(self):
        assert TriagePriority.P2_HIGH == "p2_high"

    def test_triage_priority_p3_medium(self):
        assert TriagePriority.P3_MEDIUM == "p3_medium"

    def test_triage_priority_p4_low(self):
        assert TriagePriority.P4_LOW == "p4_low"

    def test_triage_priority_p5_informational(self):
        assert TriagePriority.P5_INFORMATIONAL == "p5_informational"

    def test_triage_source_ml_model(self):
        assert TriageSource.ML_MODEL == "ml_model"

    def test_triage_source_rule_engine(self):
        assert TriageSource.RULE_ENGINE == "rule_engine"

    def test_triage_source_analyst_feedback(self):
        assert TriageSource.ANALYST_FEEDBACK == "analyst_feedback"

    def test_triage_source_historical(self):
        assert TriageSource.HISTORICAL == "historical"

    def test_triage_source_context(self):
        assert TriageSource.CONTEXT == "context"

    def test_triage_decision_investigate(self):
        assert TriageDecision.INVESTIGATE == "investigate"

    def test_triage_decision_escalate(self):
        assert TriageDecision.ESCALATE == "escalate"

    def test_triage_decision_suppress(self):
        assert TriageDecision.SUPPRESS == "suppress"

    def test_triage_decision_auto_close(self):
        assert TriageDecision.AUTO_CLOSE == "auto_close"

    def test_triage_decision_enrich(self):
        assert TriageDecision.ENRICH == "enrich"


class TestModels:
    def test_record_defaults(self):
        r = TriageRecord()
        assert r.id
        assert r.name == ""
        assert r.triage_priority == TriagePriority.P1_CRITICAL
        assert r.triage_source == TriageSource.ML_MODEL
        assert r.triage_decision == TriageDecision.ENRICH
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = TriageAnalysis()
        assert a.id
        assert a.name == ""
        assert a.triage_priority == TriagePriority.P1_CRITICAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AlertTriageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_triage_priority == {}
        assert r.by_triage_source == {}
        assert r.by_triage_decision == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            triage_priority=TriagePriority.P1_CRITICAL,
            triage_source=TriageSource.RULE_ENGINE,
            triage_decision=TriageDecision.INVESTIGATE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.triage_priority == TriagePriority.P1_CRITICAL
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_triage_priority(self):
        eng = _engine()
        eng.record_entry(name="a", triage_priority=TriagePriority.P1_CRITICAL)
        eng.record_entry(name="b", triage_priority=TriagePriority.P2_HIGH)
        assert len(eng.list_records(triage_priority=TriagePriority.P1_CRITICAL)) == 1

    def test_filter_by_triage_source(self):
        eng = _engine()
        eng.record_entry(name="a", triage_source=TriageSource.ML_MODEL)
        eng.record_entry(name="b", triage_source=TriageSource.RULE_ENGINE)
        assert len(eng.list_records(triage_source=TriageSource.ML_MODEL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", triage_priority=TriagePriority.P2_HIGH, score=90.0)
        eng.record_entry(name="b", triage_priority=TriagePriority.P2_HIGH, score=70.0)
        result = eng.analyze_distribution()
        assert "p2_high" in result
        assert result["p2_high"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
