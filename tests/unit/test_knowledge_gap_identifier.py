"""Tests for shieldops.knowledge.knowledge_gap_identifier."""

from __future__ import annotations

from shieldops.knowledge.knowledge_gap_identifier import (
    GapAnalysis,
    GapSeverity,
    KnowledgeDomain,
    KnowledgeGapIdentifier,
    KnowledgeGapRecord,
    KnowledgeGapReport,
    LearningPath,
)


def _engine(**kw) -> KnowledgeGapIdentifier:
    return KnowledgeGapIdentifier(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_domain_infrastructure(self):
        assert KnowledgeDomain.INFRASTRUCTURE == "infrastructure"

    def test_domain_security(self):
        assert KnowledgeDomain.SECURITY == "security"

    def test_domain_observability(self):
        assert KnowledgeDomain.OBSERVABILITY == "observability"

    def test_domain_application(self):
        assert KnowledgeDomain.APPLICATION == "application"

    def test_domain_architecture(self):
        assert KnowledgeDomain.ARCHITECTURE == "architecture"

    def test_severity_critical(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert GapSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert GapSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert GapSeverity.LOW == "low"

    def test_severity_none(self):
        assert GapSeverity.NONE == "none"

    def test_path_documentation(self):
        assert LearningPath.DOCUMENTATION == "documentation"

    def test_path_mentoring(self):
        assert LearningPath.MENTORING == "mentoring"

    def test_path_training(self):
        assert LearningPath.TRAINING == "training"

    def test_path_shadowing(self):
        assert LearningPath.SHADOWING == "shadowing"

    def test_path_certification(self):
        assert LearningPath.CERTIFICATION == "certification"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_knowledge_gap_record_defaults(self):
        r = KnowledgeGapRecord()
        assert r.id
        assert r.engineer == ""
        assert r.team == ""
        assert r.domain == KnowledgeDomain.INFRASTRUCTURE
        assert r.gap_severity == GapSeverity.NONE
        assert r.learning_path == LearningPath.DOCUMENTATION
        assert r.gap_score == 0.0
        assert r.coverage_pct == 0.0
        assert r.created_at > 0

    def test_gap_analysis_defaults(self):
        a = GapAnalysis()
        assert a.id
        assert a.engineer == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_knowledge_gap_report_defaults(self):
        r = KnowledgeGapReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_gap_score == 0.0
        assert r.by_domain == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_gap / get_gap
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_gap(
            engineer="alice",
            team="sre",
            domain=KnowledgeDomain.SECURITY,
            gap_severity=GapSeverity.HIGH,
            learning_path=LearningPath.CERTIFICATION,
            gap_score=75.0,
            coverage_pct=30.0,
        )
        assert r.engineer == "alice"
        assert r.domain == KnowledgeDomain.SECURITY
        assert r.gap_score == 75.0
        assert r.coverage_pct == 30.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_gap(engineer="bob", gap_score=60.0)
        found = eng.get_gap(r.id)
        assert found is not None
        assert found.gap_score == 60.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_gap("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(engineer=f"eng-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_gaps
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_gap(engineer="alice")
        eng.record_gap(engineer="bob")
        assert len(eng.list_gaps()) == 2

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_gap(engineer="alice", domain=KnowledgeDomain.INFRASTRUCTURE)
        eng.record_gap(engineer="bob", domain=KnowledgeDomain.SECURITY)
        results = eng.list_gaps(domain=KnowledgeDomain.INFRASTRUCTURE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_gap(engineer="alice", team="sre")
        eng.record_gap(engineer="bob", team="platform")
        results = eng.list_gaps(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_gap(engineer=f"eng-{i}")
        assert len(eng.list_gaps(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            engineer="alice",
            domain=KnowledgeDomain.SECURITY,
            analysis_score=80.0,
            threshold=50.0,
            breached=True,
            description="security knowledge gap",
        )
        assert a.engineer == "alice"
        assert a.analysis_score == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(engineer=f"eng-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(engineer="alice")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap(
            engineer="alice",
            domain=KnowledgeDomain.SECURITY,
            gap_score=80.0,
        )
        eng.record_gap(
            engineer="bob",
            domain=KnowledgeDomain.SECURITY,
            gap_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "security" in result
        assert result["security"]["count"] == 2
        assert result["security"]["avg_gap_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_knowledge_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_gap(engineer="alice", gap_score=80.0)
        eng.record_gap(engineer="bob", gap_score=40.0)
        results = eng.identify_knowledge_gaps()
        assert len(results) == 1
        assert results[0]["engineer"] == "alice"

    def test_sorted_descending(self):
        eng = _engine(threshold=50.0)
        eng.record_gap(engineer="alice", gap_score=90.0)
        eng.record_gap(engineer="bob", gap_score=70.0)
        results = eng.identify_knowledge_gaps()
        assert results[0]["gap_score"] == 90.0


# ---------------------------------------------------------------------------
# rank_by_gap
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_gap(engineer="alice", gap_score=30.0)
        eng.record_gap(engineer="bob", gap_score=80.0)
        results = eng.rank_by_gap()
        assert results[0]["engineer"] == "bob"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_gap() == []


# ---------------------------------------------------------------------------
# detect_gap_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(engineer="alice", analysis_score=50.0)
        result = eng.detect_gap_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(engineer="a", analysis_score=20.0)
        eng.add_analysis(engineer="b", analysis_score=20.0)
        eng.add_analysis(engineer="c", analysis_score=80.0)
        eng.add_analysis(engineer="d", analysis_score=80.0)
        result = eng.detect_gap_trends()
        assert result["trend"] == "worsening"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_gap_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_gap(
            engineer="alice",
            domain=KnowledgeDomain.SECURITY,
            gap_severity=GapSeverity.CRITICAL,
            gap_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeGapReport)
        assert report.total_records == 1
        assert report.gap_count == 1
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
        eng.record_gap(engineer="alice")
        eng.add_analysis(engineer="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_gap(engineer="alice", team="sre", domain=KnowledgeDomain.SECURITY)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "security" in stats["domain_distribution"]
        assert stats["unique_engineers"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(engineer=f"eng-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
