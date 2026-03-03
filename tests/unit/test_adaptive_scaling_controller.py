"""Tests for shieldops.operations.adaptive_scaling_controller — AdaptiveScalingController."""

from __future__ import annotations

from shieldops.operations.adaptive_scaling_controller import (
    AdaptiveScalingController,
    AdaptiveScalingReport,
    ScalingAction,
    ScalingAnalysis,
    ScalingOutcome,
    ScalingRecord,
    ScalingSource,
)


def _engine(**kw) -> AdaptiveScalingController:
    return AdaptiveScalingController(**kw)


class TestEnums:
    def test_scaling_action_scale_up(self):
        assert ScalingAction.SCALE_UP == "scale_up"

    def test_scaling_action_scale_down(self):
        assert ScalingAction.SCALE_DOWN == "scale_down"

    def test_scaling_action_scale_out(self):
        assert ScalingAction.SCALE_OUT == "scale_out"

    def test_scaling_action_scale_in(self):
        assert ScalingAction.SCALE_IN == "scale_in"

    def test_scaling_action_rebalance(self):
        assert ScalingAction.REBALANCE == "rebalance"

    def test_scaling_source_ml_prediction(self):
        assert ScalingSource.ML_PREDICTION == "ml_prediction"

    def test_scaling_source_threshold(self):
        assert ScalingSource.THRESHOLD == "threshold"

    def test_scaling_source_schedule(self):
        assert ScalingSource.SCHEDULE == "schedule"

    def test_scaling_source_event_driven(self):
        assert ScalingSource.EVENT_DRIVEN == "event_driven"

    def test_scaling_source_manual(self):
        assert ScalingSource.MANUAL == "manual"

    def test_scaling_outcome_success(self):
        assert ScalingOutcome.SUCCESS == "success"

    def test_scaling_outcome_partial(self):
        assert ScalingOutcome.PARTIAL == "partial"

    def test_scaling_outcome_failed(self):
        assert ScalingOutcome.FAILED == "failed"

    def test_scaling_outcome_rolled_back(self):
        assert ScalingOutcome.ROLLED_BACK == "rolled_back"

    def test_scaling_outcome_pending(self):
        assert ScalingOutcome.PENDING == "pending"


class TestModels:
    def test_record_defaults(self):
        r = ScalingRecord()
        assert r.id
        assert r.name == ""
        assert r.scaling_action == ScalingAction.SCALE_UP
        assert r.scaling_source == ScalingSource.ML_PREDICTION
        assert r.scaling_outcome == ScalingOutcome.PENDING
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ScalingAnalysis()
        assert a.id
        assert a.name == ""
        assert a.scaling_action == ScalingAction.SCALE_UP
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AdaptiveScalingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_scaling_action == {}
        assert r.by_scaling_source == {}
        assert r.by_scaling_outcome == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            scaling_action=ScalingAction.SCALE_UP,
            scaling_source=ScalingSource.THRESHOLD,
            scaling_outcome=ScalingOutcome.SUCCESS,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.scaling_action == ScalingAction.SCALE_UP
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_scaling_action(self):
        eng = _engine()
        eng.record_entry(name="a", scaling_action=ScalingAction.SCALE_UP)
        eng.record_entry(name="b", scaling_action=ScalingAction.SCALE_DOWN)
        assert len(eng.list_records(scaling_action=ScalingAction.SCALE_UP)) == 1

    def test_filter_by_scaling_source(self):
        eng = _engine()
        eng.record_entry(name="a", scaling_source=ScalingSource.ML_PREDICTION)
        eng.record_entry(name="b", scaling_source=ScalingSource.THRESHOLD)
        assert len(eng.list_records(scaling_source=ScalingSource.ML_PREDICTION)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
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
        eng.record_entry(name="a", scaling_action=ScalingAction.SCALE_DOWN, score=90.0)
        eng.record_entry(name="b", scaling_action=ScalingAction.SCALE_DOWN, score=70.0)
        result = eng.analyze_distribution()
        assert "scale_down" in result
        assert result["scale_down"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
