"""Tests for shieldops.operations.blameless_postmortem_enforcer."""

from __future__ import annotations

from shieldops.operations.blameless_postmortem_enforcer import (
    ActionItemStatus,
    BlamelessPostmortemEnforcer,
    LearningCategory,
    PostmortemAnalysis,
    PostmortemQuality,
    PostmortemRecord,
    PostmortemReport,
)


def _engine(**kw) -> BlamelessPostmortemEnforcer:
    return BlamelessPostmortemEnforcer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_quality_excellent(self):
        assert PostmortemQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert PostmortemQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert PostmortemQuality.ADEQUATE == "adequate"

    def test_quality_poor(self):
        assert PostmortemQuality.POOR == "poor"

    def test_quality_missing(self):
        assert PostmortemQuality.MISSING == "missing"

    def test_action_completed(self):
        assert ActionItemStatus.COMPLETED == "completed"

    def test_action_in_progress(self):
        assert ActionItemStatus.IN_PROGRESS == "in_progress"

    def test_action_overdue(self):
        assert ActionItemStatus.OVERDUE == "overdue"

    def test_action_blocked(self):
        assert ActionItemStatus.BLOCKED == "blocked"

    def test_action_not_started(self):
        assert ActionItemStatus.NOT_STARTED == "not_started"

    def test_learning_process(self):
        assert LearningCategory.PROCESS == "process"

    def test_learning_technical(self):
        assert LearningCategory.TECHNICAL == "technical"

    def test_learning_communication(self):
        assert LearningCategory.COMMUNICATION == "communication"

    def test_learning_tooling(self):
        assert LearningCategory.TOOLING == "tooling"

    def test_learning_culture(self):
        assert LearningCategory.CULTURE == "culture"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_postmortem_record_defaults(self):
        r = PostmortemRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.team == ""
        assert r.quality == PostmortemQuality.ADEQUATE
        assert r.action_item_status == ActionItemStatus.NOT_STARTED
        assert r.learning_category == LearningCategory.PROCESS
        assert r.quality_score == 0.0
        assert r.action_items_count == 0
        assert r.created_at > 0

    def test_postmortem_analysis_defaults(self):
        a = PostmortemAnalysis()
        assert a.id
        assert a.incident_id == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_postmortem_report_defaults(self):
        r = PostmortemReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_quality_score == 0.0
        assert r.by_quality == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_postmortem / get_postmortem
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_postmortem(
            incident_id="INC-001",
            team="sre",
            quality=PostmortemQuality.GOOD,
            action_item_status=ActionItemStatus.IN_PROGRESS,
            learning_category=LearningCategory.TECHNICAL,
            quality_score=75.0,
            action_items_count=5,
        )
        assert r.incident_id == "INC-001"
        assert r.quality == PostmortemQuality.GOOD
        assert r.quality_score == 75.0
        assert r.action_items_count == 5

    def test_get_found(self):
        eng = _engine()
        r = eng.record_postmortem(incident_id="INC-002", quality_score=60.0)
        found = eng.get_postmortem(r.id)
        assert found is not None
        assert found.quality_score == 60.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_postmortem("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_postmortem(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_postmortems
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_postmortem(incident_id="INC-001")
        eng.record_postmortem(incident_id="INC-002")
        assert len(eng.list_postmortems()) == 2

    def test_filter_by_quality(self):
        eng = _engine()
        eng.record_postmortem(incident_id="INC-001", quality=PostmortemQuality.GOOD)
        eng.record_postmortem(incident_id="INC-002", quality=PostmortemQuality.POOR)
        results = eng.list_postmortems(quality=PostmortemQuality.GOOD)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_postmortem(incident_id="INC-001", team="sre")
        eng.record_postmortem(incident_id="INC-002", team="platform")
        results = eng.list_postmortems(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_postmortem(incident_id=f"INC-{i}")
        assert len(eng.list_postmortems(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            incident_id="INC-001",
            learning_category=LearningCategory.PROCESS,
            analysis_score=40.0,
            threshold=50.0,
            breached=True,
            description="poor process",
        )
        assert a.incident_id == "INC-001"
        assert a.analysis_score == 40.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(incident_id=f"INC-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(incident_id="INC-001")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_postmortem(
            incident_id="INC-001",
            quality=PostmortemQuality.GOOD,
            quality_score=80.0,
        )
        eng.record_postmortem(
            incident_id="INC-002",
            quality=PostmortemQuality.GOOD,
            quality_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "good" in result
        assert result["good"]["count"] == 2
        assert result["good"]["avg_quality_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_postmortem_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_postmortem(incident_id="INC-001", quality_score=30.0)
        eng.record_postmortem(incident_id="INC-002", quality_score=80.0)
        results = eng.identify_postmortem_gaps()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_postmortem(incident_id="INC-001", quality_score=50.0)
        eng.record_postmortem(incident_id="INC-002", quality_score=30.0)
        results = eng.identify_postmortem_gaps()
        assert results[0]["quality_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_quality
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_postmortem(incident_id="INC-001", team="alpha", quality_score=90.0)
        eng.record_postmortem(incident_id="INC-002", team="beta", quality_score=40.0)
        results = eng.rank_by_quality()
        assert results[0]["team"] == "beta"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality() == []


# ---------------------------------------------------------------------------
# detect_postmortem_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(incident_id="INC-001", analysis_score=50.0)
        result = eng.detect_postmortem_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(incident_id="a", analysis_score=20.0)
        eng.add_analysis(incident_id="b", analysis_score=20.0)
        eng.add_analysis(incident_id="c", analysis_score=80.0)
        eng.add_analysis(incident_id="d", analysis_score=80.0)
        result = eng.detect_postmortem_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_postmortem_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_postmortem(
            incident_id="INC-001",
            quality=PostmortemQuality.POOR,
            action_item_status=ActionItemStatus.OVERDUE,
            quality_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PostmortemReport)
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
        eng.record_postmortem(incident_id="INC-001")
        eng.add_analysis(incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_postmortem(incident_id="INC-001", team="sre", quality=PostmortemQuality.GOOD)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "good" in stats["quality_distribution"]
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(incident_id=f"INC-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
