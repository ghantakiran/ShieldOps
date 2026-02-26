"""Tests for shieldops.analytics.collaboration_scorer — CrossTeamCollaborationScorer."""

from __future__ import annotations

from shieldops.analytics.collaboration_scorer import (
    CollaborationFrequency,
    CollaborationMetric,
    CollaborationQuality,
    CollaborationRecord,
    CollaborationScorerReport,
    CollaborationType,
    CrossTeamCollaborationScorer,
)


def _engine(**kw) -> CrossTeamCollaborationScorer:
    return CrossTeamCollaborationScorer(**kw)


class TestEnums:
    def test_type_incident_response(self):
        assert CollaborationType.INCIDENT_RESPONSE == "incident_response"

    def test_type_deployment_support(self):
        assert CollaborationType.DEPLOYMENT_SUPPORT == "deployment_support"

    def test_type_knowledge_sharing(self):
        assert CollaborationType.KNOWLEDGE_SHARING == "knowledge_sharing"

    def test_type_code_review(self):
        assert CollaborationType.CODE_REVIEW == "code_review"

    def test_type_joint_planning(self):
        assert CollaborationType.JOINT_PLANNING == "joint_planning"

    def test_quality_excellent(self):
        assert CollaborationQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert CollaborationQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert CollaborationQuality.ADEQUATE == "adequate"

    def test_quality_poor(self):
        assert CollaborationQuality.POOR == "poor"

    def test_quality_none(self):
        assert CollaborationQuality.NONE == "none"

    def test_frequency_daily(self):
        assert CollaborationFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert CollaborationFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert CollaborationFrequency.MONTHLY == "monthly"

    def test_frequency_quarterly(self):
        assert CollaborationFrequency.QUARTERLY == "quarterly"

    def test_frequency_rare(self):
        assert CollaborationFrequency.RARE == "rare"


class TestModels:
    def test_collaboration_record_defaults(self):
        r = CollaborationRecord()
        assert r.id
        assert r.team_name == ""
        assert r.collab_type == CollaborationType.INCIDENT_RESPONSE
        assert r.quality == CollaborationQuality.ADEQUATE
        assert r.frequency == CollaborationFrequency.WEEKLY
        assert r.collab_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_collaboration_metric_defaults(self):
        r = CollaborationMetric()
        assert r.id
        assert r.metric_name == ""
        assert r.collab_type == CollaborationType.INCIDENT_RESPONSE
        assert r.quality == CollaborationQuality.ADEQUATE
        assert r.score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CollaborationScorerReport()
        assert r.total_collaborations == 0
        assert r.total_metrics == 0
        assert r.avg_collab_score_pct == 0.0
        assert r.by_type == {}
        assert r.by_quality == {}
        assert r.siloed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordCollaboration:
    def test_basic(self):
        eng = _engine()
        r = eng.record_collaboration("team-a", collab_score=80.0)
        assert r.team_name == "team-a"
        assert r.collab_score == 80.0

    def test_with_quality(self):
        eng = _engine()
        r = eng.record_collaboration("team-b", quality=CollaborationQuality.EXCELLENT)
        assert r.quality == CollaborationQuality.EXCELLENT

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_collaboration(f"team-{i}")
        assert len(eng._records) == 3


class TestGetCollaboration:
    def test_found(self):
        eng = _engine()
        r = eng.record_collaboration("team-a")
        assert eng.get_collaboration(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_collaboration("nonexistent") is None


class TestListCollaborations:
    def test_list_all(self):
        eng = _engine()
        eng.record_collaboration("team-a")
        eng.record_collaboration("team-b")
        assert len(eng.list_collaborations()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_collaboration("team-a")
        eng.record_collaboration("team-b")
        results = eng.list_collaborations(team_name="team-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_collaboration("team-a", collab_type=CollaborationType.CODE_REVIEW)
        eng.record_collaboration("team-b", collab_type=CollaborationType.INCIDENT_RESPONSE)
        results = eng.list_collaborations(collab_type=CollaborationType.CODE_REVIEW)
        assert len(results) == 1


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric("resp-time", score=75.0)
        assert m.metric_name == "resp-time"
        assert m.score == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_metric(f"metric-{i}")
        assert len(eng._metrics) == 2


class TestAnalyzeTeamCollaboration:
    def test_with_data(self):
        eng = _engine()
        eng.record_collaboration("team-a", collab_score=80.0)
        eng.record_collaboration("team-a", collab_score=70.0)
        result = eng.analyze_team_collaboration("team-a")
        assert result["team_name"] == "team-a"
        assert result["total"] == 2
        assert result["avg_score"] == 75.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_team_collaboration("ghost")
        assert result["status"] == "no_data"


class TestIdentifySiloedTeams:
    def test_with_siloed(self):
        eng = _engine()
        eng.record_collaboration("team-a", quality=CollaborationQuality.POOR)
        eng.record_collaboration("team-a", quality=CollaborationQuality.POOR)
        eng.record_collaboration("team-b", quality=CollaborationQuality.GOOD)
        results = eng.identify_siloed_teams()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_siloed_teams() == []


class TestRankByCollaborationScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_collaboration("team-a", collab_score=60.0)
        eng.record_collaboration("team-b", collab_score=90.0)
        results = eng.rank_by_collaboration_score()
        assert results[0]["team_name"] == "team-b"
        assert results[0]["avg_collab_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_collaboration_score() == []


class TestDetectCollaborationTrends:
    def test_with_trends(self):
        eng = _engine()
        for i in range(5):
            eng.record_collaboration("team-a", collab_score=float(50 + i * 10))
        results = eng.detect_collaboration_trends()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"
        assert results[0]["trend"] == "improving"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_collaboration_trends() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_collaboration("team-a", collab_score=40.0, quality=CollaborationQuality.POOR)
        eng.record_collaboration("team-b", collab_score=80.0, quality=CollaborationQuality.GOOD)
        eng.add_metric("m1")
        report = eng.generate_report()
        assert report.total_collaborations == 2
        assert report.total_metrics == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_collaborations == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_collaboration("team-a")
        eng.add_metric("m1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_collaborations"] == 0
        assert stats["total_metrics"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_collaboration("team-a", collab_type=CollaborationType.CODE_REVIEW)
        eng.record_collaboration("team-b", collab_type=CollaborationType.INCIDENT_RESPONSE)
        eng.add_metric("m1")
        stats = eng.get_stats()
        assert stats["total_collaborations"] == 2
        assert stats["total_metrics"] == 1
        assert stats["unique_teams"] == 2
