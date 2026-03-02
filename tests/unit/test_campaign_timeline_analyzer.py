"""Tests for shieldops.security.campaign_timeline_analyzer — CampaignTimelineAnalyzer."""

from __future__ import annotations

from shieldops.security.campaign_timeline_analyzer import (
    AnalysisDepth,
    CampaignTimelineAnalyzer,
    TimelineAnalysis,
    TimelineAnalysisReport,
    TimelinePhase,
    TimelineRecord,
    TimelineResolution,
)


def _engine(**kw) -> CampaignTimelineAnalyzer:
    return CampaignTimelineAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_timelinephase_val1(self):
        assert TimelinePhase.RECONNAISSANCE == "reconnaissance"

    def test_timelinephase_val2(self):
        assert TimelinePhase.WEAPONIZATION == "weaponization"

    def test_timelinephase_val3(self):
        assert TimelinePhase.DELIVERY == "delivery"

    def test_timelinephase_val4(self):
        assert TimelinePhase.EXPLOITATION == "exploitation"

    def test_timelinephase_val5(self):
        assert TimelinePhase.INSTALLATION == "installation"

    def test_timelineresolution_val1(self):
        assert TimelineResolution.MINUTE == "minute"

    def test_timelineresolution_val2(self):
        assert TimelineResolution.HOUR == "hour"

    def test_timelineresolution_val3(self):
        assert TimelineResolution.DAY == "day"

    def test_timelineresolution_val4(self):
        assert TimelineResolution.WEEK == "week"

    def test_timelineresolution_val5(self):
        assert TimelineResolution.MONTH == "month"

    def test_analysisdepth_val1(self):
        assert AnalysisDepth.SURFACE == "surface"

    def test_analysisdepth_val2(self):
        assert AnalysisDepth.STANDARD == "standard"

    def test_analysisdepth_val3(self):
        assert AnalysisDepth.DEEP == "deep"

    def test_analysisdepth_val4(self):
        assert AnalysisDepth.FORENSIC == "forensic"

    def test_analysisdepth_val5(self):
        assert AnalysisDepth.COMPREHENSIVE == "comprehensive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = TimelineRecord()
        assert r.id
        assert r.campaign_name == ""
        assert r.timeline_phase == TimelinePhase.RECONNAISSANCE
        assert r.timeline_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = TimelineAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = TimelineAnalysisReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_timeline_score == 0.0
        assert r.by_phase == {}
        assert r.by_resolution == {}
        assert r.by_depth == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_timeline(
            campaign_name="test",
            timeline_phase=TimelinePhase.WEAPONIZATION,
            timeline_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.campaign_name == "test"
        assert r.timeline_phase == TimelinePhase.WEAPONIZATION
        assert r.timeline_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_timeline(campaign_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_timeline(campaign_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_timeline(campaign_name="a")
        eng.record_timeline(campaign_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_timeline(campaign_name="a", timeline_phase=TimelinePhase.RECONNAISSANCE)
        eng.record_timeline(campaign_name="b", timeline_phase=TimelinePhase.WEAPONIZATION)
        results = eng.list_records(timeline_phase=TimelinePhase.RECONNAISSANCE)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_timeline(campaign_name="a", timeline_resolution=TimelineResolution.MINUTE)
        eng.record_timeline(campaign_name="b", timeline_resolution=TimelineResolution.HOUR)
        results = eng.list_records(timeline_resolution=TimelineResolution.MINUTE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_timeline(campaign_name="a", team="sec")
        eng.record_timeline(campaign_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_timeline(campaign_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            campaign_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(campaign_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_timeline(
            campaign_name="a",
            timeline_phase=TimelinePhase.RECONNAISSANCE,
            timeline_score=90.0,
        )
        eng.record_timeline(
            campaign_name="b",
            timeline_phase=TimelinePhase.RECONNAISSANCE,
            timeline_score=70.0,
        )
        result = eng.analyze_phase_distribution()
        assert "reconnaissance" in result
        assert result["reconnaissance"]["count"] == 2
        assert result["reconnaissance"]["avg_timeline_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_phase_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_timeline(campaign_name="a", timeline_score=60.0)
        eng.record_timeline(campaign_name="b", timeline_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["campaign_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_timeline(campaign_name="a", timeline_score=50.0)
        eng.record_timeline(campaign_name="b", timeline_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["timeline_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_timeline(campaign_name="a", service="auth-svc", timeline_score=90.0)
        eng.record_timeline(campaign_name="b", service="api-gw", timeline_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_timeline_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(campaign_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(campaign_name="t1", analysis_score=20.0)
        eng.add_analysis(campaign_name="t2", analysis_score=20.0)
        eng.add_analysis(campaign_name="t3", analysis_score=80.0)
        eng.add_analysis(campaign_name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_timeline(
            campaign_name="test",
            timeline_phase=TimelinePhase.WEAPONIZATION,
            timeline_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, TimelineAnalysisReport)
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


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_timeline(campaign_name="test")
        eng.add_analysis(campaign_name="test")
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
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_timeline(
            campaign_name="test",
            timeline_phase=TimelinePhase.RECONNAISSANCE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "reconnaissance" in stats["phase_distribution"]
