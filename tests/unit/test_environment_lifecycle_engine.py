"""Tests for environment_lifecycle_engine — EnvironmentLifecycleEngine."""

from __future__ import annotations

from shieldops.operations.environment_lifecycle_engine import (
    EnvironmentLifecycleEngine,
    EnvironmentPurpose,
    EnvironmentStage,
    LifecycleAction,
)


def _engine(**kw) -> EnvironmentLifecycleEngine:
    return EnvironmentLifecycleEngine(**kw)


class TestEnums:
    def test_environmentstage_requested(self):
        assert EnvironmentStage.REQUESTED == "requested"

    def test_environmentstage_provisioning(self):
        assert EnvironmentStage.PROVISIONING == "provisioning"

    def test_environmentstage_active(self):
        assert EnvironmentStage.ACTIVE == "active"

    def test_environmentstage_hibernating(self):
        assert EnvironmentStage.HIBERNATING == "hibernating"

    def test_environmentstage_decommissioned(self):
        assert EnvironmentStage.DECOMMISSIONED == "decommissioned"

    def test_environmentpurpose_development(self):
        assert EnvironmentPurpose.DEVELOPMENT == "development"

    def test_environmentpurpose_testing(self):
        assert EnvironmentPurpose.TESTING == "testing"

    def test_environmentpurpose_staging(self):
        assert EnvironmentPurpose.STAGING == "staging"

    def test_environmentpurpose_preview(self):
        assert EnvironmentPurpose.PREVIEW == "preview"

    def test_environmentpurpose_production(self):
        assert EnvironmentPurpose.PRODUCTION == "production"

    def test_lifecycleaction_create(self):
        assert LifecycleAction.CREATE == "create"

    def test_lifecycleaction_scale(self):
        assert LifecycleAction.SCALE == "scale"

    def test_lifecycleaction_hibernate(self):
        assert LifecycleAction.HIBERNATE == "hibernate"

    def test_lifecycleaction_wake(self):
        assert LifecycleAction.WAKE == "wake"

    def test_lifecycleaction_destroy(self):
        assert LifecycleAction.DESTROY == "destroy"


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            environment_stage=EnvironmentStage.ACTIVE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.environment_stage == EnvironmentStage.ACTIVE
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

    def test_filter_by_environment_stage(self):
        eng = _engine()
        eng.record_item(
            name="a",
            environment_stage=EnvironmentStage.ACTIVE,
        )
        eng.record_item(
            name="b",
            environment_stage=EnvironmentStage.PROVISIONING,
        )
        result = eng.list_records(
            environment_stage=EnvironmentStage.ACTIVE,
        )
        assert len(result) == 1

    def test_filter_by_environment_purpose(self):
        eng = _engine()
        eng.record_item(
            name="a",
            environment_purpose=EnvironmentPurpose.DEVELOPMENT,
        )
        eng.record_item(
            name="b",
            environment_purpose=EnvironmentPurpose.STAGING,
        )
        result = eng.list_records(
            environment_purpose=EnvironmentPurpose.DEVELOPMENT,
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
            environment_stage=EnvironmentStage.ACTIVE,
            score=90.0,
        )
        eng.record_item(
            name="b",
            environment_stage=EnvironmentStage.ACTIVE,
            score=70.0,
        )
        result = eng.analyze_distribution()
        assert "active" in result
        assert result["active"]["count"] == 2

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
