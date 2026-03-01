"""Tests for shieldops.incidents.triage_quality — TriageQualityAnalyzer."""

from __future__ import annotations

from shieldops.incidents.triage_quality import (
    TriageAccuracy,
    TriageMetric,
    TriageOutcome,
    TriageQualityAnalyzer,
    TriageQualityReport,
    TriageRecord,
    TriageSpeed,
)


def _engine(**kw) -> TriageQualityAnalyzer:
    return TriageQualityAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_accuracy_correct(self):
        assert TriageAccuracy.CORRECT == "correct"

    def test_accuracy_mostly_correct(self):
        assert TriageAccuracy.MOSTLY_CORRECT == "mostly_correct"

    def test_accuracy_partially_correct(self):
        assert TriageAccuracy.PARTIALLY_CORRECT == "partially_correct"

    def test_accuracy_incorrect(self):
        assert TriageAccuracy.INCORRECT == "incorrect"

    def test_accuracy_unverified(self):
        assert TriageAccuracy.UNVERIFIED == "unverified"

    def test_speed_immediate(self):
        assert TriageSpeed.IMMEDIATE == "immediate"

    def test_speed_fast(self):
        assert TriageSpeed.FAST == "fast"

    def test_speed_normal(self):
        assert TriageSpeed.NORMAL == "normal"

    def test_speed_slow(self):
        assert TriageSpeed.SLOW == "slow"

    def test_speed_delayed(self):
        assert TriageSpeed.DELAYED == "delayed"

    def test_outcome_resolved_quickly(self):
        assert TriageOutcome.RESOLVED_QUICKLY == "resolved_quickly"

    def test_outcome_escalated_correctly(self):
        assert TriageOutcome.ESCALATED_CORRECTLY == "escalated_correctly"

    def test_outcome_misrouted(self):
        assert TriageOutcome.MISROUTED == "misrouted"

    def test_outcome_delayed_resolution(self):
        assert TriageOutcome.DELAYED_RESOLUTION == "delayed_resolution"

    def test_outcome_reopened(self):
        assert TriageOutcome.REOPENED == "reopened"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_triage_record_defaults(self):
        r = TriageRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.triage_accuracy == TriageAccuracy.UNVERIFIED
        assert r.triage_speed == TriageSpeed.NORMAL
        assert r.triage_outcome == TriageOutcome.RESOLVED_QUICKLY
        assert r.quality_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_triage_metric_defaults(self):
        m = TriageMetric()
        assert m.id
        assert m.metric_name == ""
        assert m.triage_accuracy == TriageAccuracy.UNVERIFIED
        assert m.quality_threshold == 0.0
        assert m.avg_quality_score == 0.0
        assert m.description == ""
        assert m.created_at > 0

    def test_triage_quality_report_defaults(self):
        r = TriageQualityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.poor_triages == 0
        assert r.avg_quality_score == 0.0
        assert r.by_accuracy == {}
        assert r.by_speed == {}
        assert r.by_outcome == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_triage
# ---------------------------------------------------------------------------


class TestRecordTriage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.CORRECT,
            triage_speed=TriageSpeed.FAST,
            triage_outcome=TriageOutcome.RESOLVED_QUICKLY,
            quality_score=95.0,
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.triage_accuracy == TriageAccuracy.CORRECT
        assert r.triage_speed == TriageSpeed.FAST
        assert r.triage_outcome == TriageOutcome.RESOLVED_QUICKLY
        assert r.quality_score == 95.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_triage(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_triage
# ---------------------------------------------------------------------------


class TestGetTriage:
    def test_found(self):
        eng = _engine()
        r = eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.CORRECT,
        )
        result = eng.get_triage(r.id)
        assert result is not None
        assert result.triage_accuracy == TriageAccuracy.CORRECT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_triage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_triages
# ---------------------------------------------------------------------------


class TestListTriages:
    def test_list_all(self):
        eng = _engine()
        eng.record_triage(incident_id="INC-001")
        eng.record_triage(incident_id="INC-002")
        assert len(eng.list_triages()) == 2

    def test_filter_by_accuracy(self):
        eng = _engine()
        eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.CORRECT,
        )
        eng.record_triage(
            incident_id="INC-002",
            triage_accuracy=TriageAccuracy.INCORRECT,
        )
        results = eng.list_triages(accuracy=TriageAccuracy.CORRECT)
        assert len(results) == 1

    def test_filter_by_speed(self):
        eng = _engine()
        eng.record_triage(
            incident_id="INC-001",
            triage_speed=TriageSpeed.FAST,
        )
        eng.record_triage(
            incident_id="INC-002",
            triage_speed=TriageSpeed.SLOW,
        )
        results = eng.list_triages(speed=TriageSpeed.FAST)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_triage(incident_id="INC-001", team="sre")
        eng.record_triage(incident_id="INC-002", team="platform")
        results = eng.list_triages(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_triage(incident_id=f"INC-{i}")
        assert len(eng.list_triages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            metric_name="accuracy-check",
            triage_accuracy=TriageAccuracy.CORRECT,
            quality_threshold=0.8,
            avg_quality_score=90.0,
            description="Accuracy check metric",
        )
        assert m.metric_name == "accuracy-check"
        assert m.triage_accuracy == TriageAccuracy.CORRECT
        assert m.quality_threshold == 0.8
        assert m.avg_quality_score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(metric_name=f"met-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_triage_accuracy
# ---------------------------------------------------------------------------


class TestAnalyzeTriageAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.CORRECT,
            quality_score=90.0,
        )
        eng.record_triage(
            incident_id="INC-002",
            triage_accuracy=TriageAccuracy.CORRECT,
            quality_score=80.0,
        )
        result = eng.analyze_triage_accuracy()
        assert "correct" in result
        assert result["correct"]["count"] == 2
        assert result["correct"]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_triage_accuracy() == {}


# ---------------------------------------------------------------------------
# identify_poor_triages
# ---------------------------------------------------------------------------


class TestIdentifyPoorTriages:
    def test_detects_incorrect(self):
        eng = _engine()
        eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.INCORRECT,
            quality_score=20.0,
        )
        eng.record_triage(
            incident_id="INC-002",
            triage_accuracy=TriageAccuracy.CORRECT,
        )
        results = eng.identify_poor_triages()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_detects_partially_correct(self):
        eng = _engine()
        eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.PARTIALLY_CORRECT,
        )
        results = eng.identify_poor_triages()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_poor_triages() == []


# ---------------------------------------------------------------------------
# rank_by_quality_score
# ---------------------------------------------------------------------------


class TestRankByQualityScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_triage(incident_id="INC-001", team="sre", quality_score=90.0)
        eng.record_triage(incident_id="INC-002", team="sre", quality_score=80.0)
        eng.record_triage(incident_id="INC-003", team="platform", quality_score=70.0)
        results = eng.rank_by_quality_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_quality_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_quality_score() == []


# ---------------------------------------------------------------------------
# detect_triage_trends
# ---------------------------------------------------------------------------


class TestDetectTriageTrends:
    def test_stable(self):
        eng = _engine()
        for s in [80.0, 80.0, 80.0, 80.0]:
            eng.add_metric(metric_name="m", avg_quality_score=s)
        result = eng.detect_triage_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_metric(metric_name="m", avg_quality_score=s)
        result = eng.detect_triage_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_triage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.INCORRECT,
            triage_speed=TriageSpeed.SLOW,
            quality_score=30.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, TriageQualityReport)
        assert report.total_records == 1
        assert report.poor_triages == 1
        assert report.avg_quality_score == 30.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "below threshold" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_triage(incident_id="INC-001")
        eng.add_metric(metric_name="m1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["accuracy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_triage(
            incident_id="INC-001",
            triage_accuracy=TriageAccuracy.CORRECT,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_incidents"] == 1
        assert "correct" in stats["accuracy_distribution"]
