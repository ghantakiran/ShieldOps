"""Tests for shieldops.operations.oncall_fatigue_mitigator."""

from __future__ import annotations

from shieldops.operations.oncall_fatigue_mitigator import (
    FatigueAnalysis,
    FatigueLevel,
    FatigueRecord,
    FatigueReport,
    FatigueSource,
    MitigationAction,
    OncallFatigueMitigator,
)


def _engine(**kw) -> OncallFatigueMitigator:
    return OncallFatigueMitigator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_alert_volume(self):
        assert FatigueSource.ALERT_VOLUME == "alert_volume"

    def test_source_night_pages(self):
        assert FatigueSource.NIGHT_PAGES == "night_pages"

    def test_source_weekend_pages(self):
        assert FatigueSource.WEEKEND_PAGES == "weekend_pages"

    def test_source_long_incidents(self):
        assert FatigueSource.LONG_INCIDENTS == "long_incidents"

    def test_source_consecutive_shifts(self):
        assert FatigueSource.CONSECUTIVE_SHIFTS == "consecutive_shifts"

    def test_action_redistribute(self):
        assert MitigationAction.REDISTRIBUTE == "redistribute"

    def test_action_suppress(self):
        assert MitigationAction.SUPPRESS == "suppress"

    def test_action_automate(self):
        assert MitigationAction.AUTOMATE == "automate"

    def test_action_escalate(self):
        assert MitigationAction.ESCALATE == "escalate"

    def test_action_buffer(self):
        assert MitigationAction.BUFFER == "buffer"

    def test_level_critical(self):
        assert FatigueLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert FatigueLevel.HIGH == "high"

    def test_level_moderate(self):
        assert FatigueLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert FatigueLevel.LOW == "low"

    def test_level_minimal(self):
        assert FatigueLevel.MINIMAL == "minimal"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_fatigue_record_defaults(self):
        r = FatigueRecord()
        assert r.id
        assert r.engineer == ""
        assert r.team == ""
        assert r.fatigue_source == FatigueSource.ALERT_VOLUME
        assert r.mitigation_action == MitigationAction.REDISTRIBUTE
        assert r.fatigue_level == FatigueLevel.MINIMAL
        assert r.fatigue_score == 0.0
        assert r.page_count == 0
        assert r.created_at > 0

    def test_fatigue_analysis_defaults(self):
        a = FatigueAnalysis()
        assert a.id
        assert a.engineer == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_fatigue_report_defaults(self):
        r = FatigueReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_fatigue_score == 0.0
        assert r.by_source == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_fatigue / get_fatigue
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_fatigue(
            engineer="alice",
            team="sre",
            fatigue_source=FatigueSource.NIGHT_PAGES,
            mitigation_action=MitigationAction.REDISTRIBUTE,
            fatigue_level=FatigueLevel.HIGH,
            fatigue_score=75.0,
            page_count=30,
        )
        assert r.engineer == "alice"
        assert r.fatigue_source == FatigueSource.NIGHT_PAGES
        assert r.fatigue_score == 75.0
        assert r.page_count == 30

    def test_get_found(self):
        eng = _engine()
        r = eng.record_fatigue(engineer="bob", fatigue_score=60.0)
        found = eng.get_fatigue(r.id)
        assert found is not None
        assert found.fatigue_score == 60.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_fatigue("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_fatigue(engineer=f"eng-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_fatigues
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_fatigue(engineer="alice")
        eng.record_fatigue(engineer="bob")
        assert len(eng.list_fatigues()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_fatigue(engineer="alice", fatigue_source=FatigueSource.ALERT_VOLUME)
        eng.record_fatigue(engineer="bob", fatigue_source=FatigueSource.NIGHT_PAGES)
        results = eng.list_fatigues(fatigue_source=FatigueSource.ALERT_VOLUME)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_fatigue(engineer="alice", team="sre")
        eng.record_fatigue(engineer="bob", team="platform")
        results = eng.list_fatigues(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_fatigue(engineer=f"eng-{i}")
        assert len(eng.list_fatigues(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            engineer="alice",
            fatigue_source=FatigueSource.CONSECUTIVE_SHIFTS,
            analysis_score=70.0,
            threshold=50.0,
            breached=True,
            description="high consecutive shifts",
        )
        assert a.engineer == "alice"
        assert a.analysis_score == 70.0
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
        eng.record_fatigue(
            engineer="alice",
            fatigue_source=FatigueSource.ALERT_VOLUME,
            fatigue_score=70.0,
        )
        eng.record_fatigue(
            engineer="bob",
            fatigue_source=FatigueSource.ALERT_VOLUME,
            fatigue_score=50.0,
        )
        result = eng.analyze_distribution()
        assert "alert_volume" in result
        assert result["alert_volume"]["count"] == 2
        assert result["alert_volume"]["avg_fatigue_score"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_fatigue_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_fatigue(engineer="alice", fatigue_score=80.0)
        eng.record_fatigue(engineer="bob", fatigue_score=40.0)
        results = eng.identify_fatigue_gaps()
        assert len(results) == 1
        assert results[0]["engineer"] == "alice"

    def test_sorted_descending(self):
        eng = _engine(threshold=50.0)
        eng.record_fatigue(engineer="alice", fatigue_score=90.0)
        eng.record_fatigue(engineer="bob", fatigue_score=70.0)
        results = eng.identify_fatigue_gaps()
        assert results[0]["fatigue_score"] == 90.0


# ---------------------------------------------------------------------------
# rank_by_fatigue
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_fatigue(engineer="alice", fatigue_score=30.0)
        eng.record_fatigue(engineer="bob", fatigue_score=80.0)
        results = eng.rank_by_fatigue()
        assert results[0]["engineer"] == "bob"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_fatigue() == []


# ---------------------------------------------------------------------------
# detect_fatigue_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(engineer="alice", analysis_score=50.0)
        result = eng.detect_fatigue_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(engineer="a", analysis_score=20.0)
        eng.add_analysis(engineer="b", analysis_score=20.0)
        eng.add_analysis(engineer="c", analysis_score=80.0)
        eng.add_analysis(engineer="d", analysis_score=80.0)
        result = eng.detect_fatigue_trends()
        assert result["trend"] == "worsening"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_fatigue_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_fatigue(
            engineer="alice",
            fatigue_source=FatigueSource.NIGHT_PAGES,
            fatigue_level=FatigueLevel.CRITICAL,
            fatigue_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, FatigueReport)
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
        eng.record_fatigue(engineer="alice")
        eng.add_analysis(engineer="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_fatigue(engineer="alice", team="sre", fatigue_source=FatigueSource.NIGHT_PAGES)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "night_pages" in stats["source_distribution"]
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
