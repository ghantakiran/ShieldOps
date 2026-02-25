"""Tests for shieldops.operations.sre_maturity — SREMaturityAssessor."""

from __future__ import annotations

from shieldops.operations.sre_maturity import (
    AssessmentScope,
    MaturityAssessment,
    MaturityDimension,
    MaturityRoadmapItem,
    MaturityTier,
    SREMaturityAssessor,
    SREMaturityReport,
)


def _engine(**kw) -> SREMaturityAssessor:
    return SREMaturityAssessor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # MaturityDimension (5)
    def test_dimension_oncall(self):
        assert MaturityDimension.ONCALL == "oncall"

    def test_dimension_incident_management(self):
        assert MaturityDimension.INCIDENT_MANAGEMENT == "incident_management"

    def test_dimension_slo_adoption(self):
        assert MaturityDimension.SLO_ADOPTION == "slo_adoption"

    def test_dimension_automation(self):
        assert MaturityDimension.AUTOMATION == "automation"

    def test_dimension_observability(self):
        assert MaturityDimension.OBSERVABILITY == "observability"

    # MaturityTier (5)
    def test_tier_initial(self):
        assert MaturityTier.INITIAL == "initial"

    def test_tier_developing(self):
        assert MaturityTier.DEVELOPING == "developing"

    def test_tier_defined(self):
        assert MaturityTier.DEFINED == "defined"

    def test_tier_managed(self):
        assert MaturityTier.MANAGED == "managed"

    def test_tier_optimizing(self):
        assert MaturityTier.OPTIMIZING == "optimizing"

    # AssessmentScope (5)
    def test_scope_team(self):
        assert AssessmentScope.TEAM == "team"

    def test_scope_organization(self):
        assert AssessmentScope.ORGANIZATION == "organization"

    def test_scope_service(self):
        assert AssessmentScope.SERVICE == "service"

    def test_scope_platform(self):
        assert AssessmentScope.PLATFORM == "platform"

    def test_scope_enterprise(self):
        assert AssessmentScope.ENTERPRISE == "enterprise"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_maturity_assessment_defaults(self):
        r = MaturityAssessment()
        assert r.id
        assert r.entity == ""
        assert r.scope == AssessmentScope.TEAM
        assert r.dimension == MaturityDimension.ONCALL
        assert r.tier == MaturityTier.INITIAL
        assert r.score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_maturity_roadmap_item_defaults(self):
        r = MaturityRoadmapItem()
        assert r.id
        assert r.entity == ""
        assert r.dimension == MaturityDimension.ONCALL
        assert r.current_tier == MaturityTier.INITIAL
        assert r.target_tier == MaturityTier.DEFINED
        assert r.recommendation == ""
        assert r.effort == "medium"
        assert r.created_at > 0

    def test_sre_maturity_report_defaults(self):
        r = SREMaturityReport()
        assert r.total_assessments == 0
        assert r.total_roadmap_items == 0
        assert r.avg_score == 0.0
        assert r.by_dimension == {}
        assert r.by_tier == {}
        assert r.gaps_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_assessment
# -------------------------------------------------------------------


class TestRecordAssessment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_assessment("team-alpha", dimension=MaturityDimension.ONCALL)
        assert r.entity == "team-alpha"
        assert r.dimension == MaturityDimension.ONCALL
        assert r.tier == MaturityTier.INITIAL
        assert r.score == 1.0  # auto from tier

    def test_explicit_score(self):
        eng = _engine()
        r = eng.record_assessment("team-alpha", tier=MaturityTier.MANAGED, score=3.8)
        assert r.score == 3.8

    def test_auto_score_from_tier(self):
        eng = _engine()
        r = eng.record_assessment("team-alpha", tier=MaturityTier.OPTIMIZING)
        assert r.score == 5.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_assessment(f"team-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_assessment
# -------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        r = eng.record_assessment("team-alpha")
        assert eng.get_assessment(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# -------------------------------------------------------------------
# list_assessments
# -------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.record_assessment("team-alpha")
        eng.record_assessment("team-beta")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_entity(self):
        eng = _engine()
        eng.record_assessment("team-alpha")
        eng.record_assessment("team-beta")
        results = eng.list_assessments(entity="team-alpha")
        assert len(results) == 1
        assert results[0].entity == "team-alpha"

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_assessment("t1", dimension=MaturityDimension.ONCALL)
        eng.record_assessment("t2", dimension=MaturityDimension.AUTOMATION)
        results = eng.list_assessments(dimension=MaturityDimension.AUTOMATION)
        assert len(results) == 1
        assert results[0].entity == "t2"


# -------------------------------------------------------------------
# add_roadmap_item
# -------------------------------------------------------------------


class TestAddRoadmapItem:
    def test_basic(self):
        eng = _engine()
        item = eng.add_roadmap_item(
            "team-alpha",
            dimension=MaturityDimension.SLO_ADOPTION,
            current_tier=MaturityTier.INITIAL,
            target_tier=MaturityTier.DEFINED,
            recommendation="Adopt SLOs for critical services",
        )
        assert item.entity == "team-alpha"
        assert item.dimension == MaturityDimension.SLO_ADOPTION
        assert item.recommendation == "Adopt SLOs for critical services"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_roadmap_item(f"team-{i}")
        assert len(eng._roadmap) == 2


# -------------------------------------------------------------------
# calculate_overall_maturity
# -------------------------------------------------------------------


class TestCalculateOverallMaturity:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            "team-alpha",
            dimension=MaturityDimension.ONCALL,
            tier=MaturityTier.DEFINED,
        )
        eng.record_assessment(
            "team-alpha",
            dimension=MaturityDimension.AUTOMATION,
            tier=MaturityTier.MANAGED,
        )
        result = eng.calculate_overall_maturity("team-alpha")
        assert result["entity"] == "team-alpha"
        # avg: (3.0 + 4.0) / 2 = 3.5
        assert result["score"] == 3.5
        assert result["tier"] == "managed"
        assert result["dimensions_assessed"] == 2

    def test_no_data(self):
        eng = _engine()
        result = eng.calculate_overall_maturity("team-ghost")
        assert result["score"] == 0.0
        assert result["tier"] == "initial"


# -------------------------------------------------------------------
# identify_maturity_gaps
# -------------------------------------------------------------------


class TestIdentifyMaturityGaps:
    def test_with_gaps(self):
        eng = _engine(target_maturity_score=3.0)
        eng.record_assessment("t1", tier=MaturityTier.INITIAL)  # score=1.0 < 3.0
        eng.record_assessment("t2", tier=MaturityTier.OPTIMIZING)  # score=5.0 >= 3.0
        gaps = eng.identify_maturity_gaps()
        assert len(gaps) == 1
        assert gaps[0]["entity"] == "t1"
        assert gaps[0]["gap"] == 2.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_maturity_gaps() == []


# -------------------------------------------------------------------
# generate_roadmap
# -------------------------------------------------------------------


class TestGenerateRoadmap:
    def test_with_items(self):
        eng = _engine()
        eng.add_roadmap_item("team-alpha", recommendation="Improve oncall")
        eng.add_roadmap_item("team-alpha", recommendation="Adopt SLOs")
        eng.add_roadmap_item("team-beta", recommendation="Automate toil")
        results = eng.generate_roadmap("team-alpha")
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.generate_roadmap("team-ghost") == []


# -------------------------------------------------------------------
# rank_teams_by_maturity
# -------------------------------------------------------------------


class TestRankTeamsByMaturity:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment("team-alpha", tier=MaturityTier.OPTIMIZING)
        eng.record_assessment("team-beta", tier=MaturityTier.INITIAL)
        results = eng.rank_teams_by_maturity()
        assert len(results) == 2
        assert results[0]["entity"] == "team-alpha"
        assert results[0]["avg_score"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_teams_by_maturity() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(target_maturity_score=3.0)
        eng.record_assessment("t1", dimension=MaturityDimension.ONCALL, tier=MaturityTier.INITIAL)
        eng.record_assessment(
            "t2",
            dimension=MaturityDimension.AUTOMATION,
            tier=MaturityTier.OPTIMIZING,
        )
        eng.add_roadmap_item("t1")
        report = eng.generate_report()
        assert report.total_assessments == 2
        assert report.total_roadmap_items == 1
        assert report.by_tier != {}
        assert report.by_dimension != {}
        assert report.gaps_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_assessments == 0
        assert report.avg_score == 0.0
        assert "meets target" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_assessment("team-alpha")
        eng.add_roadmap_item("team-alpha")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._roadmap) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_roadmap_items"] == 0
        assert stats["tier_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_assessment("team-alpha", tier=MaturityTier.DEFINED)
        eng.record_assessment("team-beta", tier=MaturityTier.INITIAL)
        eng.add_roadmap_item("team-alpha")
        stats = eng.get_stats()
        assert stats["total_assessments"] == 2
        assert stats["total_roadmap_items"] == 1
        assert stats["unique_entities"] == 2
        assert stats["target_maturity_score"] == 3.0
