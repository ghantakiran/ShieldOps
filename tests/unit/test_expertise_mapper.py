"""Tests for shieldops.knowledge.expertise_mapper — TeamExpertiseMapper."""

from __future__ import annotations

from shieldops.knowledge.expertise_mapper import (
    ExpertiseArea,
    ExpertiseGap,
    ExpertiseLevel,
    ExpertiseRecord,
    SkillAssessment,
    TeamExpertiseMapper,
    TeamExpertiseReport,
)


def _engine(**kw) -> TeamExpertiseMapper:
    return TeamExpertiseMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_expertise_area_infrastructure(self):
        assert ExpertiseArea.INFRASTRUCTURE == "infrastructure"

    def test_expertise_area_application(self):
        assert ExpertiseArea.APPLICATION == "application"

    def test_expertise_area_security(self):
        assert ExpertiseArea.SECURITY == "security"

    def test_expertise_area_database(self):
        assert ExpertiseArea.DATABASE == "database"

    def test_expertise_area_networking(self):
        assert ExpertiseArea.NETWORKING == "networking"

    def test_expertise_level_expert(self):
        assert ExpertiseLevel.EXPERT == "expert"

    def test_expertise_level_advanced(self):
        assert ExpertiseLevel.ADVANCED == "advanced"

    def test_expertise_level_intermediate(self):
        assert ExpertiseLevel.INTERMEDIATE == "intermediate"

    def test_expertise_level_beginner(self):
        assert ExpertiseLevel.BEGINNER == "beginner"

    def test_expertise_level_none(self):
        assert ExpertiseLevel.NONE == "none"

    def test_expertise_gap_critical_gap(self):
        assert ExpertiseGap.CRITICAL_GAP == "critical_gap"

    def test_expertise_gap_single_point_of_failure(self):
        assert ExpertiseGap.SINGLE_POINT_OF_FAILURE == "single_point_of_failure"

    def test_expertise_gap_understaffed(self):
        assert ExpertiseGap.UNDERSTAFFED == "understaffed"

    def test_expertise_gap_adequate(self):
        assert ExpertiseGap.ADEQUATE == "adequate"

    def test_expertise_gap_well_covered(self):
        assert ExpertiseGap.WELL_COVERED == "well_covered"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_expertise_record_defaults(self):
        r = ExpertiseRecord()
        assert r.id
        assert r.team_member == ""
        assert r.expertise_area == ExpertiseArea.INFRASTRUCTURE
        assert r.expertise_level == ExpertiseLevel.NONE
        assert r.expertise_gap == ExpertiseGap.CRITICAL_GAP
        assert r.coverage_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_skill_assessment_defaults(self):
        a = SkillAssessment()
        assert a.id
        assert a.assessment_name == ""
        assert a.expertise_area == ExpertiseArea.INFRASTRUCTURE
        assert a.skill_score == 0.0
        assert a.assessed_members == 0
        assert a.description == ""
        assert a.created_at > 0

    def test_team_expertise_report_defaults(self):
        r = TeamExpertiseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.covered_areas == 0
        assert r.avg_coverage_pct == 0.0
        assert r.by_area == {}
        assert r.by_level == {}
        assert r.by_gap == {}
        assert r.gap_areas == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_expertise
# ---------------------------------------------------------------------------


class TestRecordExpertise:
    def test_basic(self):
        eng = _engine()
        r = eng.record_expertise(
            team_member="alice",
            expertise_area=ExpertiseArea.APPLICATION,
            expertise_level=ExpertiseLevel.EXPERT,
            expertise_gap=ExpertiseGap.WELL_COVERED,
            coverage_pct=95.0,
            team="sre",
        )
        assert r.team_member == "alice"
        assert r.expertise_area == ExpertiseArea.APPLICATION
        assert r.expertise_level == ExpertiseLevel.EXPERT
        assert r.expertise_gap == ExpertiseGap.WELL_COVERED
        assert r.coverage_pct == 95.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_expertise(team_member=f"member-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_expertise
# ---------------------------------------------------------------------------


class TestGetExpertise:
    def test_found(self):
        eng = _engine()
        r = eng.record_expertise(
            team_member="alice",
            expertise_area=ExpertiseArea.DATABASE,
        )
        result = eng.get_expertise(r.id)
        assert result is not None
        assert result.expertise_area == ExpertiseArea.DATABASE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_expertise("nonexistent") is None


# ---------------------------------------------------------------------------
# list_expertise
# ---------------------------------------------------------------------------


class TestListExpertise:
    def test_list_all(self):
        eng = _engine()
        eng.record_expertise(team_member="alice")
        eng.record_expertise(team_member="bob")
        assert len(eng.list_expertise()) == 2

    def test_filter_by_expertise_area(self):
        eng = _engine()
        eng.record_expertise(
            team_member="alice",
            expertise_area=ExpertiseArea.INFRASTRUCTURE,
        )
        eng.record_expertise(
            team_member="bob",
            expertise_area=ExpertiseArea.SECURITY,
        )
        results = eng.list_expertise(expertise_area=ExpertiseArea.INFRASTRUCTURE)
        assert len(results) == 1

    def test_filter_by_expertise_level(self):
        eng = _engine()
        eng.record_expertise(
            team_member="alice",
            expertise_level=ExpertiseLevel.EXPERT,
        )
        eng.record_expertise(
            team_member="bob",
            expertise_level=ExpertiseLevel.BEGINNER,
        )
        results = eng.list_expertise(expertise_level=ExpertiseLevel.EXPERT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_expertise(team_member="alice", team="sre")
        eng.record_expertise(team_member="bob", team="platform")
        results = eng.list_expertise(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_expertise(team_member=f"member-{i}")
        assert len(eng.list_expertise(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            assessment_name="infra-skills-q1",
            expertise_area=ExpertiseArea.NETWORKING,
            skill_score=8.5,
            assessed_members=3,
            description="Quarterly networking skills assessment",
        )
        assert a.assessment_name == "infra-skills-q1"
        assert a.expertise_area == ExpertiseArea.NETWORKING
        assert a.skill_score == 8.5
        assert a.assessed_members == 3

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(assessment_name=f"assessment-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_expertise_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeExpertiseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_expertise(
            team_member="alice",
            expertise_area=ExpertiseArea.INFRASTRUCTURE,
            coverage_pct=90.0,
        )
        eng.record_expertise(
            team_member="bob",
            expertise_area=ExpertiseArea.INFRASTRUCTURE,
            coverage_pct=80.0,
        )
        result = eng.analyze_expertise_distribution()
        assert "infrastructure" in result
        assert result["infrastructure"]["count"] == 2
        assert result["infrastructure"]["avg_coverage_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_expertise_distribution() == {}


# ---------------------------------------------------------------------------
# identify_expertise_gaps
# ---------------------------------------------------------------------------


class TestIdentifyExpertiseGaps:
    def test_detects_gaps(self):
        eng = _engine(min_expertise_coverage_pct=70.0)
        eng.record_expertise(
            team_member="alice",
            coverage_pct=50.0,
        )
        eng.record_expertise(
            team_member="bob",
            coverage_pct=95.0,
        )
        results = eng.identify_expertise_gaps()
        assert len(results) == 1
        assert results[0]["team_member"] == "alice"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_expertise_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_coverage_score
# ---------------------------------------------------------------------------


class TestRankByCoverageScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_expertise(team_member="alice", team="sre", coverage_pct=90.0)
        eng.record_expertise(team_member="bob", team="sre", coverage_pct=80.0)
        eng.record_expertise(team_member="carol", team="platform", coverage_pct=50.0)
        results = eng.rank_by_coverage_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["total_coverage"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage_score() == []


# ---------------------------------------------------------------------------
# detect_expertise_trends
# ---------------------------------------------------------------------------


class TestDetectExpertiseTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_expertise(team_member="alice", coverage_pct=pct)
        result = eng.detect_expertise_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [50.0, 50.0, 90.0, 90.0]:
            eng.record_expertise(team_member="alice", coverage_pct=pct)
        result = eng.detect_expertise_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_expertise_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_expertise_coverage_pct=70.0)
        eng.record_expertise(
            team_member="alice",
            expertise_area=ExpertiseArea.INFRASTRUCTURE,
            expertise_level=ExpertiseLevel.INTERMEDIATE,
            coverage_pct=50.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, TeamExpertiseReport)
        assert report.total_records == 1
        assert report.avg_coverage_pct == 50.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_expertise(team_member="alice")
        eng.add_assessment(assessment_name="a1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["area_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_expertise(
            team_member="alice",
            expertise_area=ExpertiseArea.APPLICATION,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_members"] == 1
        assert "application" in stats["area_distribution"]
