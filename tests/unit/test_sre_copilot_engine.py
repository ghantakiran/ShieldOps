"""Tests for shieldops.analytics.sre_copilot_engine — SreCopilotEngine."""

from __future__ import annotations

from shieldops.analytics.sre_copilot_engine import (
    CopilotSource,
    GuidanceAnalysis,
    GuidanceConfidence,
    GuidanceRecord,
    GuidanceType,
    SreCopilotEngine,
    SreCopilotReport,
)


def _engine(**kw) -> SreCopilotEngine:
    return SreCopilotEngine(**kw)


class TestEnums:
    def test_guidance_type_incident_response(self):
        assert GuidanceType.INCIDENT_RESPONSE == "incident_response"

    def test_guidance_type_capacity_planning(self):
        assert GuidanceType.CAPACITY_PLANNING == "capacity_planning"

    def test_guidance_type_optimization(self):
        assert GuidanceType.OPTIMIZATION == "optimization"

    def test_guidance_type_troubleshooting(self):
        assert GuidanceType.TROUBLESHOOTING == "troubleshooting"

    def test_guidance_type_automation(self):
        assert GuidanceType.AUTOMATION == "automation"

    def test_copilot_source_context_analysis(self):
        assert CopilotSource.CONTEXT_ANALYSIS == "context_analysis"

    def test_copilot_source_historical_data(self):
        assert CopilotSource.HISTORICAL_DATA == "historical_data"

    def test_copilot_source_best_practice(self):
        assert CopilotSource.BEST_PRACTICE == "best_practice"

    def test_copilot_source_ml_recommendation(self):
        assert CopilotSource.ML_RECOMMENDATION == "ml_recommendation"

    def test_copilot_source_expert_system(self):
        assert CopilotSource.EXPERT_SYSTEM == "expert_system"

    def test_guidance_confidence_high(self):
        assert GuidanceConfidence.HIGH == "high"

    def test_guidance_confidence_medium(self):
        assert GuidanceConfidence.MEDIUM == "medium"

    def test_guidance_confidence_low(self):
        assert GuidanceConfidence.LOW == "low"

    def test_guidance_confidence_speculative(self):
        assert GuidanceConfidence.SPECULATIVE == "speculative"

    def test_guidance_confidence_requires_validation(self):
        assert GuidanceConfidence.REQUIRES_VALIDATION == "requires_validation"


class TestModels:
    def test_record_defaults(self):
        r = GuidanceRecord()
        assert r.id
        assert r.name == ""
        assert r.guidance_type == GuidanceType.INCIDENT_RESPONSE
        assert r.copilot_source == CopilotSource.CONTEXT_ANALYSIS
        assert r.guidance_confidence == GuidanceConfidence.REQUIRES_VALIDATION
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = GuidanceAnalysis()
        assert a.id
        assert a.name == ""
        assert a.guidance_type == GuidanceType.INCIDENT_RESPONSE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SreCopilotReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_guidance_type == {}
        assert r.by_copilot_source == {}
        assert r.by_guidance_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            guidance_type=GuidanceType.INCIDENT_RESPONSE,
            copilot_source=CopilotSource.HISTORICAL_DATA,
            guidance_confidence=GuidanceConfidence.HIGH,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.guidance_type == GuidanceType.INCIDENT_RESPONSE
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

    def test_filter_by_guidance_type(self):
        eng = _engine()
        eng.record_entry(name="a", guidance_type=GuidanceType.INCIDENT_RESPONSE)
        eng.record_entry(name="b", guidance_type=GuidanceType.CAPACITY_PLANNING)
        assert len(eng.list_records(guidance_type=GuidanceType.INCIDENT_RESPONSE)) == 1

    def test_filter_by_copilot_source(self):
        eng = _engine()
        eng.record_entry(name="a", copilot_source=CopilotSource.CONTEXT_ANALYSIS)
        eng.record_entry(name="b", copilot_source=CopilotSource.HISTORICAL_DATA)
        assert len(eng.list_records(copilot_source=CopilotSource.CONTEXT_ANALYSIS)) == 1

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
        eng.record_entry(name="a", guidance_type=GuidanceType.CAPACITY_PLANNING, score=90.0)
        eng.record_entry(name="b", guidance_type=GuidanceType.CAPACITY_PLANNING, score=70.0)
        result = eng.analyze_distribution()
        assert "capacity_planning" in result
        assert result["capacity_planning"]["count"] == 2

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
