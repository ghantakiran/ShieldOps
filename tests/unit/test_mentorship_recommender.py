"""Tests for shieldops.operations.mentorship_recommender."""

from __future__ import annotations

from shieldops.operations.mentorship_recommender import (
    MatchQuality,
    MentorshipAnalysis,
    MentorshipRecommender,
    MentorshipRecord,
    MentorshipReport,
    MentorshipType,
    SkillArea,
)


def _engine(**kw) -> MentorshipRecommender:
    return MentorshipRecommender(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_skill_incident_response(self):
        assert SkillArea.INCIDENT_RESPONSE == "incident_response"

    def test_skill_cloud_infra(self):
        assert SkillArea.CLOUD_INFRA == "cloud_infra"

    def test_skill_security_ops(self):
        assert SkillArea.SECURITY_OPS == "security_ops"

    def test_skill_automation(self):
        assert SkillArea.AUTOMATION == "automation"

    def test_skill_architecture(self):
        assert SkillArea.ARCHITECTURE == "architecture"

    def test_type_formal(self):
        assert MentorshipType.FORMAL == "formal"

    def test_type_informal(self):
        assert MentorshipType.INFORMAL == "informal"

    def test_type_peer(self):
        assert MentorshipType.PEER == "peer"

    def test_type_reverse(self):
        assert MentorshipType.REVERSE == "reverse"

    def test_type_group(self):
        assert MentorshipType.GROUP == "group"

    def test_quality_excellent(self):
        assert MatchQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert MatchQuality.GOOD == "good"

    def test_quality_fair(self):
        assert MatchQuality.FAIR == "fair"

    def test_quality_poor(self):
        assert MatchQuality.POOR == "poor"

    def test_quality_incompatible(self):
        assert MatchQuality.INCOMPATIBLE == "incompatible"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_mentorship_record_defaults(self):
        r = MentorshipRecord()
        assert r.id
        assert r.mentor == ""
        assert r.mentee == ""
        assert r.team == ""
        assert r.skill_area == SkillArea.INCIDENT_RESPONSE
        assert r.mentorship_type == MentorshipType.FORMAL
        assert r.match_quality == MatchQuality.GOOD
        assert r.match_score == 0.0
        assert r.sessions_completed == 0
        assert r.created_at > 0

    def test_mentorship_analysis_defaults(self):
        a = MentorshipAnalysis()
        assert a.id
        assert a.mentor == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_mentorship_report_defaults(self):
        r = MentorshipReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_match_score == 0.0
        assert r.by_skill_area == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_mentorship / get_mentorship
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mentorship(
            mentor="alice",
            mentee="charlie",
            team="sre",
            skill_area=SkillArea.CLOUD_INFRA,
            mentorship_type=MentorshipType.PEER,
            match_quality=MatchQuality.EXCELLENT,
            match_score=90.0,
            sessions_completed=5,
        )
        assert r.mentor == "alice"
        assert r.skill_area == SkillArea.CLOUD_INFRA
        assert r.match_score == 90.0
        assert r.sessions_completed == 5

    def test_get_found(self):
        eng = _engine()
        r = eng.record_mentorship(mentor="bob", match_score=75.0)
        found = eng.get_mentorship(r.id)
        assert found is not None
        assert found.match_score == 75.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_mentorship("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mentorship(mentor=f"mentor-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_mentorships
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_mentorship(mentor="alice")
        eng.record_mentorship(mentor="bob")
        assert len(eng.list_mentorships()) == 2

    def test_filter_by_skill_area(self):
        eng = _engine()
        eng.record_mentorship(mentor="alice", skill_area=SkillArea.CLOUD_INFRA)
        eng.record_mentorship(mentor="bob", skill_area=SkillArea.AUTOMATION)
        results = eng.list_mentorships(skill_area=SkillArea.CLOUD_INFRA)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mentorship(mentor="alice", team="sre")
        eng.record_mentorship(mentor="bob", team="platform")
        results = eng.list_mentorships(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mentorship(mentor=f"mentor-{i}")
        assert len(eng.list_mentorships(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            mentor="alice",
            skill_area=SkillArea.SECURITY_OPS,
            analysis_score=45.0,
            threshold=50.0,
            breached=True,
            description="poor match",
        )
        assert a.mentor == "alice"
        assert a.analysis_score == 45.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(mentor=f"mentor-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(mentor="alice")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_mentorship(
            mentor="alice",
            skill_area=SkillArea.CLOUD_INFRA,
            match_score=90.0,
        )
        eng.record_mentorship(
            mentor="bob",
            skill_area=SkillArea.CLOUD_INFRA,
            match_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "cloud_infra" in result
        assert result["cloud_infra"]["count"] == 2
        assert result["cloud_infra"]["avg_match_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_mentorship_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_mentorship(mentor="alice", match_score=40.0)
        eng.record_mentorship(mentor="bob", match_score=80.0)
        results = eng.identify_mentorship_gaps()
        assert len(results) == 1
        assert results[0]["mentor"] == "alice"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_mentorship(mentor="alice", match_score=50.0)
        eng.record_mentorship(mentor="bob", match_score=30.0)
        results = eng.identify_mentorship_gaps()
        assert results[0]["match_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_match
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_mentorship(mentor="alice", match_score=90.0)
        eng.record_mentorship(mentor="bob", match_score=40.0)
        results = eng.rank_by_match()
        assert results[0]["mentor"] == "alice"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_match() == []


# ---------------------------------------------------------------------------
# detect_mentorship_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(mentor="alice", analysis_score=50.0)
        result = eng.detect_mentorship_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(mentor="a", analysis_score=20.0)
        eng.add_analysis(mentor="b", analysis_score=20.0)
        eng.add_analysis(mentor="c", analysis_score=80.0)
        eng.add_analysis(mentor="d", analysis_score=80.0)
        result = eng.detect_mentorship_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_mentorship_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_mentorship(
            mentor="alice",
            skill_area=SkillArea.CLOUD_INFRA,
            match_quality=MatchQuality.POOR,
            match_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, MentorshipReport)
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
        eng.record_mentorship(mentor="alice")
        eng.add_analysis(mentor="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_mentorship(mentor="alice", team="sre", skill_area=SkillArea.CLOUD_INFRA)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "cloud_infra" in stats["skill_area_distribution"]
        assert stats["unique_mentors"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(mentor=f"mentor-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
