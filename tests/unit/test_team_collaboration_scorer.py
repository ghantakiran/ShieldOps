"""Tests for shieldops.analytics.team_collaboration_scorer."""

from __future__ import annotations

from shieldops.analytics.team_collaboration_scorer import (
    CollaborationAnalysis,
    CollaborationDimension,
    CollaborationRecord,
    CollaborationReport,
    HealthStatus,
    InteractionType,
    TeamCollaborationScorer,
)


def _engine(**kw) -> TeamCollaborationScorer:
    return TeamCollaborationScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimension_communication(self):
        assert CollaborationDimension.COMMUNICATION == "communication"

    def test_dimension_code_review(self):
        assert CollaborationDimension.CODE_REVIEW == "code_review"

    def test_dimension_incident_response(self):
        assert CollaborationDimension.INCIDENT_RESPONSE == "incident_response"

    def test_dimension_knowledge_sharing(self):
        assert CollaborationDimension.KNOWLEDGE_SHARING == "knowledge_sharing"

    def test_dimension_planning(self):
        assert CollaborationDimension.PLANNING == "planning"

    def test_health_thriving(self):
        assert HealthStatus.THRIVING == "thriving"

    def test_health_healthy(self):
        assert HealthStatus.HEALTHY == "healthy"

    def test_health_developing(self):
        assert HealthStatus.DEVELOPING == "developing"

    def test_health_struggling(self):
        assert HealthStatus.STRUGGLING == "struggling"

    def test_health_dysfunctional(self):
        assert HealthStatus.DYSFUNCTIONAL == "dysfunctional"

    def test_interaction_sync(self):
        assert InteractionType.SYNC == "sync"

    def test_interaction_async(self):
        assert InteractionType.ASYNC == "async"

    def test_interaction_pairing(self):
        assert InteractionType.PAIRING == "pairing"

    def test_interaction_review(self):
        assert InteractionType.REVIEW == "review"

    def test_interaction_handoff(self):
        assert InteractionType.HANDOFF == "handoff"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_collaboration_record_defaults(self):
        r = CollaborationRecord()
        assert r.id
        assert r.team == ""
        assert r.participant == ""
        assert r.dimension == CollaborationDimension.COMMUNICATION
        assert r.health_status == HealthStatus.HEALTHY
        assert r.interaction_type == InteractionType.SYNC
        assert r.collaboration_score == 0.0
        assert r.interaction_count == 0
        assert r.created_at > 0

    def test_collaboration_analysis_defaults(self):
        a = CollaborationAnalysis()
        assert a.id
        assert a.team == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_collaboration_report_defaults(self):
        r = CollaborationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_collaboration_score == 0.0
        assert r.by_dimension == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_collaboration / get_collaboration
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_collaboration(
            team="sre",
            participant="alice",
            dimension=CollaborationDimension.CODE_REVIEW,
            health_status=HealthStatus.THRIVING,
            interaction_type=InteractionType.PAIRING,
            collaboration_score=90.0,
            interaction_count=20,
        )
        assert r.team == "sre"
        assert r.dimension == CollaborationDimension.CODE_REVIEW
        assert r.collaboration_score == 90.0
        assert r.interaction_count == 20

    def test_get_found(self):
        eng = _engine()
        r = eng.record_collaboration(team="platform", collaboration_score=70.0)
        found = eng.get_collaboration(r.id)
        assert found is not None
        assert found.collaboration_score == 70.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_collaboration("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_collaboration(team=f"team-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_collaborations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_collaboration(team="sre")
        eng.record_collaboration(team="platform")
        assert len(eng.list_collaborations()) == 2

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_collaboration(team="sre", dimension=CollaborationDimension.COMMUNICATION)
        eng.record_collaboration(team="noc", dimension=CollaborationDimension.PLANNING)
        results = eng.list_collaborations(dimension=CollaborationDimension.COMMUNICATION)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_collaboration(team="sre")
        eng.record_collaboration(team="platform")
        results = eng.list_collaborations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_collaboration(team=f"team-{i}")
        assert len(eng.list_collaborations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            team="sre",
            dimension=CollaborationDimension.KNOWLEDGE_SHARING,
            analysis_score=40.0,
            threshold=50.0,
            breached=True,
            description="low knowledge sharing",
        )
        assert a.team == "sre"
        assert a.analysis_score == 40.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(team=f"team-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(team="sre")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_collaboration(
            team="sre",
            dimension=CollaborationDimension.COMMUNICATION,
            collaboration_score=80.0,
        )
        eng.record_collaboration(
            team="noc",
            dimension=CollaborationDimension.COMMUNICATION,
            collaboration_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "communication" in result
        assert result["communication"]["count"] == 2
        assert result["communication"]["avg_collaboration_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_collaboration_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_collaboration(team="sre", collaboration_score=40.0)
        eng.record_collaboration(team="platform", collaboration_score=80.0)
        results = eng.identify_collaboration_gaps()
        assert len(results) == 1
        assert results[0]["team"] == "sre"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_collaboration(team="a", collaboration_score=50.0)
        eng.record_collaboration(team="b", collaboration_score=30.0)
        results = eng.identify_collaboration_gaps()
        assert results[0]["collaboration_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_collaboration
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_collaboration(team="alpha", collaboration_score=90.0)
        eng.record_collaboration(team="beta", collaboration_score=40.0)
        results = eng.rank_by_collaboration()
        assert results[0]["team"] == "beta"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_collaboration() == []


# ---------------------------------------------------------------------------
# detect_collaboration_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(team="sre", analysis_score=50.0)
        result = eng.detect_collaboration_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(team="a", analysis_score=20.0)
        eng.add_analysis(team="b", analysis_score=20.0)
        eng.add_analysis(team="c", analysis_score=80.0)
        eng.add_analysis(team="d", analysis_score=80.0)
        result = eng.detect_collaboration_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_collaboration_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_collaboration(
            team="sre",
            dimension=CollaborationDimension.PLANNING,
            health_status=HealthStatus.STRUGGLING,
            collaboration_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CollaborationReport)
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
        eng.record_collaboration(team="sre")
        eng.add_analysis(team="sre")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_collaboration(team="sre", dimension=CollaborationDimension.COMMUNICATION)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "communication" in stats["dimension_distribution"]
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(team=f"team-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
