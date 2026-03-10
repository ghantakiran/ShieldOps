"""Tests for service_readiness_engine — ServiceReadinessEngine."""

from __future__ import annotations

from shieldops.changes.service_readiness_engine import (
    GateDecision,
    ReadinessCategory,
    ReadinessLevel,
    ServiceReadinessEngine,
)


def _engine(**kw) -> ServiceReadinessEngine:
    return ServiceReadinessEngine(**kw)


class TestEnums:
    def test_readinesscategory_observability(self):
        assert ReadinessCategory.OBSERVABILITY == "observability"

    def test_readinesscategory_security(self):
        assert ReadinessCategory.SECURITY == "security"

    def test_readinesscategory_reliability(self):
        assert ReadinessCategory.RELIABILITY == "reliability"

    def test_readinesscategory_documentation(self):
        assert ReadinessCategory.DOCUMENTATION == "documentation"

    def test_readinesscategory_testing(self):
        assert ReadinessCategory.TESTING == "testing"

    def test_readinesslevel_production_ready(self):
        assert ReadinessLevel.PRODUCTION_READY == "production_ready"

    def test_readinesslevel_nearly_ready(self):
        assert ReadinessLevel.NEARLY_READY == "nearly_ready"

    def test_readinesslevel_in_progress(self):
        assert ReadinessLevel.IN_PROGRESS == "in_progress"

    def test_readinesslevel_not_started(self):
        assert ReadinessLevel.NOT_STARTED == "not_started"

    def test_readinesslevel_blocked(self):
        assert ReadinessLevel.BLOCKED == "blocked"

    def test_gatedecision_approved(self):
        assert GateDecision.APPROVED == "approved"

    def test_gatedecision_conditional(self):
        assert GateDecision.CONDITIONAL == "conditional"

    def test_gatedecision_deferred(self):
        assert GateDecision.DEFERRED == "deferred"

    def test_gatedecision_rejected(self):
        assert GateDecision.REJECTED == "rejected"

    def test_gatedecision_pending(self):
        assert GateDecision.PENDING == "pending"


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            readiness_category=ReadinessCategory.OBSERVABILITY,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.readiness_category == ReadinessCategory.OBSERVABILITY
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_readiness_category(self):
        eng = _engine()
        eng.record_item(
            name="a",
            readiness_category=ReadinessCategory.OBSERVABILITY,
        )
        eng.record_item(
            name="b",
            readiness_category=ReadinessCategory.SECURITY,
        )
        result = eng.list_records(
            readiness_category=ReadinessCategory.OBSERVABILITY,
        )
        assert len(result) == 1

    def test_filter_by_readiness_level(self):
        eng = _engine()
        eng.record_item(
            name="a",
            readiness_level=ReadinessLevel.PRODUCTION_READY,
        )
        eng.record_item(
            name="b",
            readiness_level=ReadinessLevel.IN_PROGRESS,
        )
        result = eng.list_records(
            readiness_level=ReadinessLevel.PRODUCTION_READY,
        )
        assert len(result) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
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
        eng.record_item(
            name="a",
            readiness_category=ReadinessCategory.OBSERVABILITY,
            score=90.0,
        )
        eng.record_item(
            name="b",
            readiness_category=ReadinessCategory.OBSERVABILITY,
            score=70.0,
        )
        result = eng.analyze_distribution()
        assert "observability" in result
        assert result["observability"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(
            name="a",
            service="auth",
            score=90.0,
        )
        eng.record_item(
            name="b",
            service="api",
            score=50.0,
        )
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                name="t",
                analysis_score=50.0,
            )
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(
            name="a",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="b",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="c",
            analysis_score=80.0,
        )
        eng.add_analysis(
            name="d",
            analysis_score=80.0,
        )
        result = eng.detect_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(
            name="test",
            service="auth",
            team="sec",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
