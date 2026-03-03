"""Tests for shieldops.operations.cognitive_automation_engine — CognitiveAutomationEngine."""

from __future__ import annotations

from shieldops.operations.cognitive_automation_engine import (
    CognitiveAnalysis,
    CognitiveAutomationEngine,
    CognitiveAutomationReport,
    CognitiveRecord,
    CognitiveSource,
    DecisionConfidence,
    DecisionType,
)


def _engine(**kw) -> CognitiveAutomationEngine:
    return CognitiveAutomationEngine(**kw)


class TestEnums:
    def test_decision_type_triage(self):
        assert DecisionType.TRIAGE == "triage"

    def test_decision_type_escalation(self):
        assert DecisionType.ESCALATION == "escalation"

    def test_decision_type_remediation(self):
        assert DecisionType.REMEDIATION == "remediation"

    def test_decision_type_optimization(self):
        assert DecisionType.OPTIMIZATION == "optimization"

    def test_decision_type_prediction(self):
        assert DecisionType.PREDICTION == "prediction"

    def test_cognitive_source_ml_model(self):
        assert CognitiveSource.ML_MODEL == "ml_model"

    def test_cognitive_source_rule_engine(self):
        assert CognitiveSource.RULE_ENGINE == "rule_engine"

    def test_cognitive_source_expert_system(self):
        assert CognitiveSource.EXPERT_SYSTEM == "expert_system"

    def test_cognitive_source_llm(self):
        assert CognitiveSource.LLM == "llm"

    def test_cognitive_source_hybrid(self):
        assert CognitiveSource.HYBRID == "hybrid"

    def test_decision_confidence_high(self):
        assert DecisionConfidence.HIGH == "high"

    def test_decision_confidence_medium(self):
        assert DecisionConfidence.MEDIUM == "medium"

    def test_decision_confidence_low(self):
        assert DecisionConfidence.LOW == "low"

    def test_decision_confidence_uncertain(self):
        assert DecisionConfidence.UNCERTAIN == "uncertain"

    def test_decision_confidence_override(self):
        assert DecisionConfidence.OVERRIDE == "override"


class TestModels:
    def test_record_defaults(self):
        r = CognitiveRecord()
        assert r.id
        assert r.name == ""
        assert r.decision_type == DecisionType.TRIAGE
        assert r.cognitive_source == CognitiveSource.ML_MODEL
        assert r.decision_confidence == DecisionConfidence.OVERRIDE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = CognitiveAnalysis()
        assert a.id
        assert a.name == ""
        assert a.decision_type == DecisionType.TRIAGE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = CognitiveAutomationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_decision_type == {}
        assert r.by_cognitive_source == {}
        assert r.by_decision_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            decision_type=DecisionType.TRIAGE,
            cognitive_source=CognitiveSource.RULE_ENGINE,
            decision_confidence=DecisionConfidence.HIGH,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.decision_type == DecisionType.TRIAGE
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

    def test_filter_by_decision_type(self):
        eng = _engine()
        eng.record_entry(name="a", decision_type=DecisionType.TRIAGE)
        eng.record_entry(name="b", decision_type=DecisionType.ESCALATION)
        assert len(eng.list_records(decision_type=DecisionType.TRIAGE)) == 1

    def test_filter_by_cognitive_source(self):
        eng = _engine()
        eng.record_entry(name="a", cognitive_source=CognitiveSource.ML_MODEL)
        eng.record_entry(name="b", cognitive_source=CognitiveSource.RULE_ENGINE)
        assert len(eng.list_records(cognitive_source=CognitiveSource.ML_MODEL)) == 1

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
        eng.record_entry(name="a", decision_type=DecisionType.ESCALATION, score=90.0)
        eng.record_entry(name="b", decision_type=DecisionType.ESCALATION, score=70.0)
        result = eng.analyze_distribution()
        assert "escalation" in result
        assert result["escalation"]["count"] == 2

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
