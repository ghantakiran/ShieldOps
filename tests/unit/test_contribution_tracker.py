"""Tests for shieldops.knowledge.contribution_tracker — KnowledgeContributionTracker."""

from __future__ import annotations

from shieldops.knowledge.contribution_tracker import (
    ContributionImpact,
    ContributionQuality,
    ContributionRecord,
    ContributionTrackerReport,
    ContributionType,
    ContributorProfile,
    KnowledgeContributionTracker,
)


def _engine(**kw) -> KnowledgeContributionTracker:
    return KnowledgeContributionTracker(**kw)


class TestEnums:
    def test_type_runbook(self):
        assert ContributionType.RUNBOOK == "runbook"

    def test_type_playbook(self):
        assert ContributionType.PLAYBOOK == "playbook"

    def test_type_documentation(self):
        assert ContributionType.DOCUMENTATION == "documentation"

    def test_type_postmortem(self):
        assert ContributionType.POSTMORTEM == "postmortem"

    def test_type_training_material(self):
        assert ContributionType.TRAINING_MATERIAL == "training_material"

    def test_quality_excellent(self):
        assert ContributionQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert ContributionQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert ContributionQuality.ADEQUATE == "adequate"

    def test_quality_needs_improvement(self):
        assert ContributionQuality.NEEDS_IMPROVEMENT == "needs_improvement"

    def test_quality_poor(self):
        assert ContributionQuality.POOR == "poor"

    def test_impact_high(self):
        assert ContributionImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert ContributionImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert ContributionImpact.LOW == "low"

    def test_impact_minimal(self):
        assert ContributionImpact.MINIMAL == "minimal"

    def test_impact_unknown(self):
        assert ContributionImpact.UNKNOWN == "unknown"


class TestModels:
    def test_contribution_record_defaults(self):
        r = ContributionRecord()
        assert r.id
        assert r.contributor_name == ""
        assert r.contribution_type == ContributionType.DOCUMENTATION
        assert r.quality == ContributionQuality.ADEQUATE
        assert r.impact == ContributionImpact.UNKNOWN
        assert r.quality_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_contributor_profile_defaults(self):
        r = ContributorProfile()
        assert r.id
        assert r.profile_name == ""
        assert r.contribution_type == ContributionType.DOCUMENTATION
        assert r.quality == ContributionQuality.ADEQUATE
        assert r.total_contributions == 0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ContributionTrackerReport()
        assert r.total_contributions == 0
        assert r.total_profiles == 0
        assert r.avg_quality_score_pct == 0.0
        assert r.by_type == {}
        assert r.by_quality == {}
        assert r.top_contributor_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordContribution:
    def test_basic(self):
        eng = _engine()
        r = eng.record_contribution("alice", quality_score=80.0)
        assert r.contributor_name == "alice"
        assert r.quality_score == 80.0

    def test_with_type(self):
        eng = _engine()
        r = eng.record_contribution("bob", contribution_type=ContributionType.RUNBOOK)
        assert r.contribution_type == ContributionType.RUNBOOK

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_contribution(f"user-{i}")
        assert len(eng._records) == 3


class TestGetContribution:
    def test_found(self):
        eng = _engine()
        r = eng.record_contribution("alice")
        assert eng.get_contribution(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_contribution("nonexistent") is None


class TestListContributions:
    def test_list_all(self):
        eng = _engine()
        eng.record_contribution("alice")
        eng.record_contribution("bob")
        assert len(eng.list_contributions()) == 2

    def test_filter_by_contributor(self):
        eng = _engine()
        eng.record_contribution("alice")
        eng.record_contribution("bob")
        results = eng.list_contributions(contributor_name="alice")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_contribution("alice", contribution_type=ContributionType.RUNBOOK)
        eng.record_contribution("bob", contribution_type=ContributionType.DOCUMENTATION)
        results = eng.list_contributions(contribution_type=ContributionType.RUNBOOK)
        assert len(results) == 1


class TestAddContributorProfile:
    def test_basic(self):
        eng = _engine()
        p = eng.add_contributor_profile("alice-profile", total_contributions=10)
        assert p.profile_name == "alice-profile"
        assert p.total_contributions == 10

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_contributor_profile(f"profile-{i}")
        assert len(eng._profiles) == 2


class TestAnalyzeContributionPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_contribution("alice", quality_score=80.0)
        eng.record_contribution("alice", quality_score=70.0)
        result = eng.analyze_contribution_patterns("alice")
        assert result["contributor_name"] == "alice"
        assert result["total"] == 2
        assert result["avg_score"] == 75.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_contribution_patterns("ghost")
        assert result["status"] == "no_data"


class TestIdentifyTopContributors:
    def test_with_top(self):
        eng = _engine()
        eng.record_contribution("alice", quality=ContributionQuality.EXCELLENT)
        eng.record_contribution("alice", quality=ContributionQuality.GOOD)
        eng.record_contribution("bob", quality=ContributionQuality.POOR)
        results = eng.identify_top_contributors()
        assert len(results) == 1
        assert results[0]["contributor_name"] == "alice"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_top_contributors() == []


class TestRankByImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_contribution("alice", quality_score=60.0)
        eng.record_contribution("bob", quality_score=90.0)
        results = eng.rank_by_impact()
        assert results[0]["contributor_name"] == "bob"
        assert results[0]["avg_quality_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


class TestDetectKnowledgeGaps:
    def test_with_gaps(self):
        eng = _engine()
        for i in range(5):
            eng.record_contribution("alice", quality_score=float(80 - i * 10))
        results = eng.detect_knowledge_gaps()
        assert len(results) == 1
        assert results[0]["contributor_name"] == "alice"
        assert results[0]["gap"] == "widening"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_knowledge_gaps() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_contribution("alice", quality_score=40.0, quality=ContributionQuality.POOR)
        eng.record_contribution("bob", quality_score=80.0, quality=ContributionQuality.GOOD)
        eng.add_contributor_profile("p1")
        report = eng.generate_report()
        assert report.total_contributions == 2
        assert report.total_profiles == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_contributions == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_contribution("alice")
        eng.add_contributor_profile("p1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._profiles) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_contributions"] == 0
        assert stats["total_profiles"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_contribution("alice", contribution_type=ContributionType.RUNBOOK)
        eng.record_contribution("bob", contribution_type=ContributionType.DOCUMENTATION)
        eng.add_contributor_profile("p1")
        stats = eng.get_stats()
        assert stats["total_contributions"] == 2
        assert stats["total_profiles"] == 1
        assert stats["unique_contributors"] == 2
