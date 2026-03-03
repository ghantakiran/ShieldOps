"""Tests for shieldops.security.detection_tuning_engine — DetectionTuningEngine."""

from __future__ import annotations

from shieldops.security.detection_tuning_engine import (
    DetectionTuningEngine,
    DetectionType,
    TuningAction,
    TuningAnalysis,
    TuningImpact,
    TuningRecord,
    TuningReport,
)


def _engine(**kw) -> DetectionTuningEngine:
    return DetectionTuningEngine(**kw)


class TestEnums:
    def test_tuningaction_val1(self):
        assert TuningAction.THRESHOLD_ADJUST == "threshold_adjust"

    def test_tuningaction_val2(self):
        assert TuningAction.FILTER_REFINE == "filter_refine"

    def test_tuningaction_val3(self):
        assert TuningAction.LOGIC_UPDATE == "logic_update"

    def test_tuningaction_val4(self):
        assert TuningAction.CORRELATION_ADD == "correlation_add"

    def test_tuningaction_val5(self):
        assert TuningAction.SUPPRESSION == "suppression"

    def test_detectiontype_val1(self):
        assert DetectionType.SIGNATURE == "signature"

    def test_detectiontype_val2(self):
        assert DetectionType.ANOMALY == "anomaly"

    def test_detectiontype_val3(self):
        assert DetectionType.BEHAVIORAL == "behavioral"

    def test_detectiontype_val4(self):
        assert DetectionType.HEURISTIC == "heuristic"

    def test_detectiontype_val5(self):
        assert DetectionType.ML_BASED == "ml_based"

    def test_tuningimpact_val1(self):
        assert TuningImpact.HIGH == "high"

    def test_tuningimpact_val2(self):
        assert TuningImpact.MEDIUM == "medium"

    def test_tuningimpact_val3(self):
        assert TuningImpact.LOW == "low"

    def test_tuningimpact_val4(self):
        assert TuningImpact.MINIMAL == "minimal"

    def test_tuningimpact_val5(self):
        assert TuningImpact.NEGATIVE == "negative"


class TestModels:
    def test_record_defaults(self):
        r = TuningRecord()
        assert r.id
        assert r.rule_name == ""

    def test_analysis_defaults(self):
        a = TuningAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = TuningReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_tuning(
            rule_name="test",
            tuning_action=TuningAction.FILTER_REFINE,
            effectiveness_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.rule_name == "test"
        assert r.effectiveness_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_tuning(rule_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_tuning(rule_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_tuning(rule_name="a")
        eng.record_tuning(rule_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_tuning(rule_name="a", tuning_action=TuningAction.THRESHOLD_ADJUST)
        eng.record_tuning(rule_name="b", tuning_action=TuningAction.FILTER_REFINE)
        assert len(eng.list_records(tuning_action=TuningAction.THRESHOLD_ADJUST)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_tuning(rule_name="a", detection_type=DetectionType.SIGNATURE)
        eng.record_tuning(rule_name="b", detection_type=DetectionType.ANOMALY)
        assert len(eng.list_records(detection_type=DetectionType.SIGNATURE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_tuning(rule_name="a", team="sec")
        eng.record_tuning(rule_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_tuning(rule_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            rule_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(rule_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_tuning(
            rule_name="a", tuning_action=TuningAction.THRESHOLD_ADJUST, effectiveness_score=90.0
        )
        eng.record_tuning(
            rule_name="b", tuning_action=TuningAction.THRESHOLD_ADJUST, effectiveness_score=70.0
        )
        result = eng.analyze_distribution()
        assert TuningAction.THRESHOLD_ADJUST.value in result
        assert result[TuningAction.THRESHOLD_ADJUST.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_tuning(rule_name="a", effectiveness_score=60.0)
        eng.record_tuning(rule_name="b", effectiveness_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_tuning(rule_name="a", effectiveness_score=50.0)
        eng.record_tuning(rule_name="b", effectiveness_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_tuning(rule_name="a", service="auth", effectiveness_score=90.0)
        eng.record_tuning(rule_name="b", service="api", effectiveness_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(rule_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(rule_name="a", analysis_score=20.0)
        eng.add_analysis(rule_name="b", analysis_score=20.0)
        eng.add_analysis(rule_name="c", analysis_score=80.0)
        eng.add_analysis(rule_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_tuning(rule_name="test", effectiveness_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_tuning(rule_name="test")
        eng.add_analysis(rule_name="test")
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
        eng.record_tuning(rule_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
