"""Tests for CollaborationPatternAnalyzer."""

from __future__ import annotations

from shieldops.analytics.collaboration_pattern_analyzer import (
    CollaborationPatternAnalyzer,
    CollaborationType,
    EngagementLevel,
    PatternHealth,
)


def _engine(**kw) -> CollaborationPatternAnalyzer:
    return CollaborationPatternAnalyzer(**kw)


class TestEnums:
    def test_collaboration_type_values(self):
        for v in CollaborationType:
            assert isinstance(v.value, str)

    def test_pattern_health_values(self):
        for v in PatternHealth:
            assert isinstance(v.value, str)

    def test_engagement_level_values(self):
        for v in EngagementLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(team_id="t1")
        assert r.team_id == "t1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            team_id="t1",
            partner_team_id="t2",
            interaction_count=10,
        )
        assert r.interaction_count == 10

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(team_id=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            team_id="t1",
            partner_team_id="t2",
            interaction_count=5,
        )
        a = eng.process(r.id)
        assert hasattr(a, "team_id")
        assert a.team_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeCollaborationDensity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            team_id="t1",
            partner_team_id="t2",
            interaction_count=10,
        )
        result = eng.analyze_collaboration_density()
        assert len(result) == 1
        assert result[0]["density"] == 10.0

    def test_empty(self):
        r = _engine().analyze_collaboration_density()
        assert r == []


class TestDetectCollaborationGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.add_record(
                team_id="t1",
                engagement=EngagementLevel.NONE,
            )
        result = eng.detect_collaboration_gaps()
        assert len(result) == 1
        assert result[0]["gap_ratio"] == 1.0

    def test_empty(self):
        r = _engine().detect_collaboration_gaps()
        assert r == []


class TestRankTeamsByCrossTeamEngagement:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            team_id="t1",
            partner_team_id="t2",
            interaction_count=10,
        )
        eng.add_record(
            team_id="t2",
            partner_team_id="t1",
            interaction_count=5,
        )
        result = eng.rank_teams_by_cross_team_engagement()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine()
        assert r.rank_teams_by_cross_team_engagement() == []
