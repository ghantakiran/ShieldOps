"""Tests for shieldops.knowledge.operational_knowledge_synthesizer

OperationalKnowledgeSynthesizer.
"""

from __future__ import annotations

from shieldops.knowledge.operational_knowledge_synthesizer import (
    KnowledgeAnalysis,
    KnowledgeMaturity,
    KnowledgeRecord,
    KnowledgeType,
    OperationalKnowledgeReport,
    OperationalKnowledgeSynthesizer,
    SynthesisSource,
)


def _engine(**kw) -> OperationalKnowledgeSynthesizer:
    return OperationalKnowledgeSynthesizer(**kw)


class TestEnums:
    def test_knowledge_type_pattern(self):
        assert KnowledgeType.PATTERN == "pattern"

    def test_knowledge_type_root_cause(self):
        assert KnowledgeType.ROOT_CAUSE == "root_cause"

    def test_knowledge_type_solution(self):
        assert KnowledgeType.SOLUTION == "solution"

    def test_knowledge_type_best_practice(self):
        assert KnowledgeType.BEST_PRACTICE == "best_practice"

    def test_knowledge_type_lesson_learned(self):
        assert KnowledgeType.LESSON_LEARNED == "lesson_learned"

    def test_synthesis_source_incident_review(self):
        assert SynthesisSource.INCIDENT_REVIEW == "incident_review"

    def test_synthesis_source_runbook_execution(self):
        assert SynthesisSource.RUNBOOK_EXECUTION == "runbook_execution"

    def test_synthesis_source_expert_input(self):
        assert SynthesisSource.EXPERT_INPUT == "expert_input"

    def test_synthesis_source_ml_extraction(self):
        assert SynthesisSource.ML_EXTRACTION == "ml_extraction"

    def test_synthesis_source_documentation(self):
        assert SynthesisSource.DOCUMENTATION == "documentation"

    def test_knowledge_maturity_validated(self):
        assert KnowledgeMaturity.VALIDATED == "validated"

    def test_knowledge_maturity_reviewed(self):
        assert KnowledgeMaturity.REVIEWED == "reviewed"

    def test_knowledge_maturity_draft(self):
        assert KnowledgeMaturity.DRAFT == "draft"

    def test_knowledge_maturity_candidate(self):
        assert KnowledgeMaturity.CANDIDATE == "candidate"

    def test_knowledge_maturity_deprecated(self):
        assert KnowledgeMaturity.DEPRECATED == "deprecated"


class TestModels:
    def test_record_defaults(self):
        r = KnowledgeRecord()
        assert r.id
        assert r.name == ""
        assert r.knowledge_type == KnowledgeType.PATTERN
        assert r.synthesis_source == SynthesisSource.INCIDENT_REVIEW
        assert r.knowledge_maturity == KnowledgeMaturity.DEPRECATED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = KnowledgeAnalysis()
        assert a.id
        assert a.name == ""
        assert a.knowledge_type == KnowledgeType.PATTERN
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = OperationalKnowledgeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_knowledge_type == {}
        assert r.by_synthesis_source == {}
        assert r.by_knowledge_maturity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            knowledge_type=KnowledgeType.PATTERN,
            synthesis_source=SynthesisSource.RUNBOOK_EXECUTION,
            knowledge_maturity=KnowledgeMaturity.VALIDATED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.knowledge_type == KnowledgeType.PATTERN
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

    def test_filter_by_knowledge_type(self):
        eng = _engine()
        eng.record_entry(name="a", knowledge_type=KnowledgeType.PATTERN)
        eng.record_entry(name="b", knowledge_type=KnowledgeType.ROOT_CAUSE)
        assert len(eng.list_records(knowledge_type=KnowledgeType.PATTERN)) == 1

    def test_filter_by_synthesis_source(self):
        eng = _engine()
        eng.record_entry(name="a", synthesis_source=SynthesisSource.INCIDENT_REVIEW)
        eng.record_entry(name="b", synthesis_source=SynthesisSource.RUNBOOK_EXECUTION)
        assert len(eng.list_records(synthesis_source=SynthesisSource.INCIDENT_REVIEW)) == 1

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
        eng.record_entry(name="a", knowledge_type=KnowledgeType.ROOT_CAUSE, score=90.0)
        eng.record_entry(name="b", knowledge_type=KnowledgeType.ROOT_CAUSE, score=70.0)
        result = eng.analyze_distribution()
        assert "root_cause" in result
        assert result["root_cause"]["count"] == 2

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
