"""Tests for shieldops.compliance.regulatory_change_impact — RegulatoryChangeImpact."""

from __future__ import annotations

from shieldops.compliance.regulatory_change_impact import (
    ChangeType,
    ImpactLevel,
    ReadinessState,
    RegulatoryChangeAnalysis,
    RegulatoryChangeImpact,
    RegulatoryChangeRecord,
    RegulatoryChangeReport,
)


def _engine(**kw) -> RegulatoryChangeImpact:
    return RegulatoryChangeImpact(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_changetype_new_regulation(self):
        assert ChangeType.NEW_REGULATION == "new_regulation"

    def test_changetype_amendment(self):
        assert ChangeType.AMENDMENT == "amendment"

    def test_changetype_interpretation(self):
        assert ChangeType.INTERPRETATION == "interpretation"

    def test_changetype_enforcement_action(self):
        assert ChangeType.ENFORCEMENT_ACTION == "enforcement_action"

    def test_changetype_guideline_update(self):
        assert ChangeType.GUIDELINE_UPDATE == "guideline_update"

    def test_impactlevel_transformational(self):
        assert ImpactLevel.TRANSFORMATIONAL == "transformational"

    def test_impactlevel_significant(self):
        assert ImpactLevel.SIGNIFICANT == "significant"

    def test_impactlevel_moderate(self):
        assert ImpactLevel.MODERATE == "moderate"

    def test_impactlevel_minor(self):
        assert ImpactLevel.MINOR == "minor"

    def test_impactlevel_negligible(self):
        assert ImpactLevel.NEGLIGIBLE == "negligible"

    def test_readinessstate_compliant(self):
        assert ReadinessState.COMPLIANT == "compliant"

    def test_readinessstate_in_progress(self):
        assert ReadinessState.IN_PROGRESS == "in_progress"

    def test_readinessstate_gap_identified(self):
        assert ReadinessState.GAP_IDENTIFIED == "gap_identified"

    def test_readinessstate_not_started(self):
        assert ReadinessState.NOT_STARTED == "not_started"

    def test_readinessstate_not_applicable(self):
        assert ReadinessState.NOT_APPLICABLE == "not_applicable"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_regulatorychangerecord_defaults(self):
        r = RegulatoryChangeRecord()
        assert r.id
        assert r.change_name == ""
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_regulatorychangeanalysis_defaults(self):
        c = RegulatoryChangeAnalysis()
        assert c.id
        assert c.change_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_regulatorychangereport_defaults(self):
        r = RegulatoryChangeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_impact_count == 0
        assert r.avg_impact_score == 0
        assert r.by_type == {}
        assert r.by_impact == {}
        assert r.by_readiness == {}
        assert r.top_high_impact == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_change
# ---------------------------------------------------------------------------


class TestRecordChange:
    def test_basic(self):
        eng = _engine()
        r = eng.record_change(
            change_name="test-item",
            change_type=ChangeType.AMENDMENT,
            impact_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.change_name == "test-item"
        assert r.impact_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_change(change_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_change
# ---------------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        eng = _engine()
        r = eng.record_change(change_name="test-item")
        result = eng.get_change(r.id)
        assert result is not None
        assert result.change_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_change("nonexistent") is None


# ---------------------------------------------------------------------------
# list_changes
# ---------------------------------------------------------------------------


class TestListChanges:
    def test_list_all(self):
        eng = _engine()
        eng.record_change(change_name="ITEM-001")
        eng.record_change(change_name="ITEM-002")
        assert len(eng.list_changes()) == 2

    def test_filter_by_change_type(self):
        eng = _engine()
        eng.record_change(change_name="ITEM-001", change_type=ChangeType.NEW_REGULATION)
        eng.record_change(change_name="ITEM-002", change_type=ChangeType.AMENDMENT)
        results = eng.list_changes(change_type=ChangeType.NEW_REGULATION)
        assert len(results) == 1

    def test_filter_by_impact_level(self):
        eng = _engine()
        eng.record_change(change_name="ITEM-001", impact_level=ImpactLevel.TRANSFORMATIONAL)
        eng.record_change(change_name="ITEM-002", impact_level=ImpactLevel.SIGNIFICANT)
        results = eng.list_changes(impact_level=ImpactLevel.TRANSFORMATIONAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_change(change_name="ITEM-001", team="security")
        eng.record_change(change_name="ITEM-002", team="platform")
        results = eng.list_changes(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_change(change_name=f"ITEM-{i}")
        assert len(eng.list_changes(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            change_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.change_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(change_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_type_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_change(
            change_name="ITEM-001", change_type=ChangeType.NEW_REGULATION, impact_score=90.0
        )
        eng.record_change(
            change_name="ITEM-002", change_type=ChangeType.NEW_REGULATION, impact_score=70.0
        )
        result = eng.analyze_type_distribution()
        assert "new_regulation" in result
        assert result["new_regulation"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_changes
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(regulatory_impact_threshold=60.0)
        eng.record_change(change_name="ITEM-001", impact_score=90.0)
        eng.record_change(change_name="ITEM-002", impact_score=40.0)
        results = eng.identify_high_impact_changes()
        assert len(results) == 1
        assert results[0]["change_name"] == "ITEM-001"

    def test_sorted_descending(self):
        eng = _engine(regulatory_impact_threshold=60.0)
        eng.record_change(change_name="ITEM-001", impact_score=80.0)
        eng.record_change(change_name="ITEM-002", impact_score=95.0)
        results = eng.identify_high_impact_changes()
        assert len(results) == 2
        assert results[0]["impact_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_changes() == []


# ---------------------------------------------------------------------------
# rank_by_impact_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_change(change_name="ITEM-001", service="auth-svc", impact_score=90.0)
        eng.record_change(change_name="ITEM-002", service="api-gw", impact_score=50.0)
        results = eng.rank_by_impact_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# ---------------------------------------------------------------------------
# detect_impact_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(change_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_impact_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(change_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(change_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(change_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(change_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_impact_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(regulatory_impact_threshold=60.0)
        eng.record_change(change_name="test-item", impact_score=90.0)
        report = eng.generate_report()
        assert isinstance(report, RegulatoryChangeReport)
        assert report.total_records == 1
        assert report.high_impact_count == 1
        assert len(report.top_high_impact) == 1
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
        eng.record_change(change_name="ITEM-001")
        eng.add_analysis(change_name="ITEM-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_change(
            change_name="ITEM-001",
            change_type=ChangeType.NEW_REGULATION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
