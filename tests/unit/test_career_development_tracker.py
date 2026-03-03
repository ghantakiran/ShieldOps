"""Tests for shieldops.analytics.career_development_tracker."""

from __future__ import annotations

from shieldops.analytics.career_development_tracker import (
    CareerAnalysis,
    CareerDevelopmentTracker,
    CareerRecord,
    CareerReport,
    CareerStage,
    DevelopmentArea,
    ProgressStatus,
)


def _engine(**kw) -> CareerDevelopmentTracker:
    return CareerDevelopmentTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_stage_junior(self):
        assert CareerStage.JUNIOR == "junior"

    def test_stage_mid_level(self):
        assert CareerStage.MID_LEVEL == "mid_level"

    def test_stage_senior(self):
        assert CareerStage.SENIOR == "senior"

    def test_stage_staff(self):
        assert CareerStage.STAFF == "staff"

    def test_stage_principal(self):
        assert CareerStage.PRINCIPAL == "principal"

    def test_area_technical(self):
        assert DevelopmentArea.TECHNICAL == "technical"

    def test_area_leadership(self):
        assert DevelopmentArea.LEADERSHIP == "leadership"

    def test_area_communication(self):
        assert DevelopmentArea.COMMUNICATION == "communication"

    def test_area_domain(self):
        assert DevelopmentArea.DOMAIN == "domain"

    def test_area_strategic(self):
        assert DevelopmentArea.STRATEGIC == "strategic"

    def test_status_on_track(self):
        assert ProgressStatus.ON_TRACK == "on_track"

    def test_status_ahead(self):
        assert ProgressStatus.AHEAD == "ahead"

    def test_status_behind(self):
        assert ProgressStatus.BEHIND == "behind"

    def test_status_stalled(self):
        assert ProgressStatus.STALLED == "stalled"

    def test_status_undefined(self):
        assert ProgressStatus.UNDEFINED == "undefined"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_career_record_defaults(self):
        r = CareerRecord()
        assert r.id
        assert r.engineer == ""
        assert r.team == ""
        assert r.career_stage == CareerStage.MID_LEVEL
        assert r.development_area == DevelopmentArea.TECHNICAL
        assert r.progress_status == ProgressStatus.ON_TRACK
        assert r.progress_score == 0.0
        assert r.months_in_role == 0
        assert r.created_at > 0

    def test_career_analysis_defaults(self):
        a = CareerAnalysis()
        assert a.id
        assert a.engineer == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_career_report_defaults(self):
        r = CareerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_progress_score == 0.0
        assert r.by_stage == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_career / get_career
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_career(
            engineer="alice",
            team="sre",
            career_stage=CareerStage.SENIOR,
            development_area=DevelopmentArea.LEADERSHIP,
            progress_status=ProgressStatus.AHEAD,
            progress_score=85.0,
            months_in_role=18,
        )
        assert r.engineer == "alice"
        assert r.career_stage == CareerStage.SENIOR
        assert r.progress_score == 85.0
        assert r.months_in_role == 18

    def test_get_found(self):
        eng = _engine()
        r = eng.record_career(engineer="bob", progress_score=65.0)
        found = eng.get_career(r.id)
        assert found is not None
        assert found.progress_score == 65.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_career("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_career(engineer=f"eng-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_careers
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_career(engineer="alice")
        eng.record_career(engineer="bob")
        assert len(eng.list_careers()) == 2

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_career(engineer="alice", career_stage=CareerStage.JUNIOR)
        eng.record_career(engineer="bob", career_stage=CareerStage.SENIOR)
        results = eng.list_careers(career_stage=CareerStage.JUNIOR)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_career(engineer="alice", team="sre")
        eng.record_career(engineer="bob", team="platform")
        results = eng.list_careers(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_career(engineer=f"eng-{i}")
        assert len(eng.list_careers(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            engineer="alice",
            development_area=DevelopmentArea.LEADERSHIP,
            analysis_score=40.0,
            threshold=50.0,
            breached=True,
            description="leadership gap",
        )
        assert a.engineer == "alice"
        assert a.analysis_score == 40.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(engineer=f"eng-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(engineer="alice")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_career(
            engineer="alice",
            career_stage=CareerStage.SENIOR,
            progress_score=80.0,
        )
        eng.record_career(
            engineer="bob",
            career_stage=CareerStage.SENIOR,
            progress_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "senior" in result
        assert result["senior"]["count"] == 2
        assert result["senior"]["avg_progress_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_development_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_career(engineer="alice", progress_score=40.0)
        eng.record_career(engineer="bob", progress_score=80.0)
        results = eng.identify_development_gaps()
        assert len(results) == 1
        assert results[0]["engineer"] == "alice"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_career(engineer="alice", progress_score=50.0)
        eng.record_career(engineer="bob", progress_score=30.0)
        results = eng.identify_development_gaps()
        assert results[0]["progress_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_progress
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_career(engineer="alice", progress_score=90.0)
        eng.record_career(engineer="bob", progress_score=40.0)
        results = eng.rank_by_progress()
        assert results[0]["engineer"] == "bob"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_progress() == []


# ---------------------------------------------------------------------------
# detect_development_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(engineer="alice", analysis_score=50.0)
        result = eng.detect_development_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(engineer="a", analysis_score=20.0)
        eng.add_analysis(engineer="b", analysis_score=20.0)
        eng.add_analysis(engineer="c", analysis_score=80.0)
        eng.add_analysis(engineer="d", analysis_score=80.0)
        result = eng.detect_development_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_development_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_career(
            engineer="alice",
            career_stage=CareerStage.JUNIOR,
            development_area=DevelopmentArea.TECHNICAL,
            progress_status=ProgressStatus.BEHIND,
            progress_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CareerReport)
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
        eng.record_career(engineer="alice")
        eng.add_analysis(engineer="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_career(engineer="alice", team="sre", career_stage=CareerStage.SENIOR)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "senior" in stats["stage_distribution"]
        assert stats["unique_engineers"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(engineer=f"eng-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
