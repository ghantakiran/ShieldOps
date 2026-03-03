"""Tests for shieldops.topology.deprecation_cascade_analyzer."""

from __future__ import annotations

from shieldops.topology.deprecation_cascade_analyzer import (
    DeprecationAnalysis,
    DeprecationCascadeAnalyzer,
    DeprecationCascadeReport,
    DeprecationRecord,
    DeprecationStage,
    ImpactScope,
    MigrationStatus,
)


def _engine(**kw) -> DeprecationCascadeAnalyzer:
    return DeprecationCascadeAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stage_announced(self):
        assert DeprecationStage.ANNOUNCED == "announced"

    def test_stage_sunset(self):
        assert DeprecationStage.SUNSET == "sunset"

    def test_stage_removed(self):
        assert DeprecationStage.REMOVED == "removed"

    def test_stage_migrated(self):
        assert DeprecationStage.MIGRATED == "migrated"

    def test_stage_unknown(self):
        assert DeprecationStage.UNKNOWN == "unknown"

    def test_scope_service(self):
        assert ImpactScope.SERVICE == "service"

    def test_scope_team(self):
        assert ImpactScope.TEAM == "team"

    def test_scope_organization(self):
        assert ImpactScope.ORGANIZATION == "organization"

    def test_scope_ecosystem(self):
        assert ImpactScope.ECOSYSTEM == "ecosystem"

    def test_scope_global(self):
        assert ImpactScope.GLOBAL == "global"

    def test_migration_not_started(self):
        assert MigrationStatus.NOT_STARTED == "not_started"

    def test_migration_in_progress(self):
        assert MigrationStatus.IN_PROGRESS == "in_progress"

    def test_migration_blocked(self):
        assert MigrationStatus.BLOCKED == "blocked"

    def test_migration_completed(self):
        assert MigrationStatus.COMPLETED == "completed"

    def test_migration_deferred(self):
        assert MigrationStatus.DEFERRED == "deferred"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_deprecation_record_defaults(self):
        r = DeprecationRecord()
        assert r.id
        assert r.dependency_name == ""
        assert r.deprecation_stage == DeprecationStage.ANNOUNCED
        assert r.impact_scope == ImpactScope.SERVICE
        assert r.migration_status == MigrationStatus.NOT_STARTED
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_deprecation_analysis_defaults(self):
        c = DeprecationAnalysis()
        assert c.id
        assert c.dependency_name == ""
        assert c.deprecation_stage == DeprecationStage.ANNOUNCED
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_deprecation_cascade_report_defaults(self):
        r = DeprecationCascadeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_impact_score == 0.0
        assert r.by_stage == {}
        assert r.by_scope == {}
        assert r.by_migration_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_deprecation / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_deprecation(
            dependency_name="log4j-1.x",
            deprecation_stage=DeprecationStage.SUNSET,
            impact_scope=ImpactScope.ORGANIZATION,
            migration_status=MigrationStatus.IN_PROGRESS,
            impact_score=85.0,
            service="backend",
            team="platform",
        )
        assert r.dependency_name == "log4j-1.x"
        assert r.deprecation_stage == DeprecationStage.SUNSET
        assert r.impact_scope == ImpactScope.ORGANIZATION
        assert r.migration_status == MigrationStatus.IN_PROGRESS
        assert r.impact_score == 85.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_deprecation(dependency_name="old-sdk", impact_score=70.0)
        result = eng.get_deprecation(r.id)
        assert result is not None
        assert result.impact_score == 70.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_deprecation("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_deprecation(dependency_name=f"dep-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_deprecations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_deprecation(dependency_name="a")
        eng.record_deprecation(dependency_name="b")
        assert len(eng.list_deprecations()) == 2

    def test_filter_by_deprecation_stage(self):
        eng = _engine()
        eng.record_deprecation(dependency_name="a", deprecation_stage=DeprecationStage.ANNOUNCED)
        eng.record_deprecation(dependency_name="b", deprecation_stage=DeprecationStage.REMOVED)
        results = eng.list_deprecations(deprecation_stage=DeprecationStage.ANNOUNCED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_deprecation(dependency_name="a", team="platform")
        eng.record_deprecation(dependency_name="b", team="security")
        results = eng.list_deprecations(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_deprecation(dependency_name=f"dep-{i}")
        assert len(eng.list_deprecations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            dependency_name="old-api",
            deprecation_stage=DeprecationStage.REMOVED,
            analysis_score=90.0,
            threshold=70.0,
            breached=True,
            description="cascade risk detected",
        )
        assert a.dependency_name == "old-api"
        assert a.deprecation_stage == DeprecationStage.REMOVED
        assert a.analysis_score == 90.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(dependency_name=f"dep-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_migration_status(self):
        eng = _engine()
        eng.record_deprecation(dependency_name="a", migration_status=MigrationStatus.BLOCKED)
        eng.record_deprecation(dependency_name="b", migration_status=MigrationStatus.COMPLETED)
        results = eng.list_deprecations(migration_status=MigrationStatus.BLOCKED)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_stage_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_deprecation(
            dependency_name="a", deprecation_stage=DeprecationStage.SUNSET, impact_score=90.0
        )
        eng.record_deprecation(
            dependency_name="b", deprecation_stage=DeprecationStage.SUNSET, impact_score=70.0
        )
        result = eng.analyze_stage_distribution()
        assert "sunset" in result
        assert result["sunset"]["count"] == 2
        assert result["sunset"]["avg_impact_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_stage_distribution() == {}


# ---------------------------------------------------------------------------
# identify_cascade_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(impact_gap_threshold=70.0)
        eng.record_deprecation(dependency_name="a", impact_score=80.0)
        eng.record_deprecation(dependency_name="b", impact_score=50.0)
        results = eng.identify_cascade_gaps()
        assert len(results) == 1
        assert results[0]["dependency_name"] == "a"

    def test_sorted_descending(self):
        eng = _engine(impact_gap_threshold=50.0)
        eng.record_deprecation(dependency_name="a", impact_score=90.0)
        eng.record_deprecation(dependency_name="b", impact_score=70.0)
        results = eng.identify_cascade_gaps()
        assert len(results) == 2
        assert results[0]["impact_score"] == 90.0


# ---------------------------------------------------------------------------
# rank_by_impact
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_deprecation(dependency_name="a", service="backend", impact_score=30.0)
        eng.record_deprecation(dependency_name="b", service="frontend", impact_score=90.0)
        results = eng.rank_by_impact()
        assert len(results) == 2
        assert results[0]["service"] == "frontend"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# ---------------------------------------------------------------------------
# detect_cascade_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(dependency_name="dep", analysis_score=50.0)
        result = eng.detect_cascade_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(dependency_name="dep", analysis_score=20.0)
        eng.add_analysis(dependency_name="dep", analysis_score=20.0)
        eng.add_analysis(dependency_name="dep", analysis_score=80.0)
        eng.add_analysis(dependency_name="dep", analysis_score=80.0)
        result = eng.detect_cascade_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_cascade_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(impact_gap_threshold=60.0)
        eng.record_deprecation(
            dependency_name="log4j-1.x",
            deprecation_stage=DeprecationStage.SUNSET,
            impact_scope=ImpactScope.ORGANIZATION,
            impact_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DeprecationCascadeReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
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
        eng.record_deprecation(dependency_name="dep")
        eng.add_analysis(dependency_name="dep")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_deprecation(
            dependency_name="log4j-1.x",
            deprecation_stage=DeprecationStage.SUNSET,
            service="backend",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "sunset" in stats["stage_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_deprecation(dependency_name=f"dep-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].dependency_name == "dep-4"
