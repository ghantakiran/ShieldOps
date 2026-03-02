"""Tests for shieldops.security.hunt_effectiveness_tracker — HuntEffectivenessTracker."""

from __future__ import annotations

from shieldops.security.hunt_effectiveness_tracker import (
    HuntAnalysis,
    HuntEffectivenessTracker,
    HuntOutcome,
    HuntRecord,
    HuntReport,
    HuntROI,
    HuntType,
)


def _engine(**kw) -> HuntEffectivenessTracker:
    return HuntEffectivenessTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_hypothesis_driven(self):
        assert HuntType.HYPOTHESIS_DRIVEN == "hypothesis_driven"

    def test_type_intel_driven(self):
        assert HuntType.INTEL_DRIVEN == "intel_driven"

    def test_type_anomaly_based(self):
        assert HuntType.ANOMALY_BASED == "anomaly_based"

    def test_type_automated(self):
        assert HuntType.AUTOMATED == "automated"

    def test_type_ad_hoc(self):
        assert HuntType.AD_HOC == "ad_hoc"

    def test_outcome_threat_found(self):
        assert HuntOutcome.THREAT_FOUND == "threat_found"

    def test_outcome_false_positive(self):
        assert HuntOutcome.FALSE_POSITIVE == "false_positive"

    def test_outcome_inconclusive(self):
        assert HuntOutcome.INCONCLUSIVE == "inconclusive"

    def test_outcome_new_detection(self):
        assert HuntOutcome.NEW_DETECTION == "new_detection"

    def test_outcome_no_findings(self):
        assert HuntOutcome.NO_FINDINGS == "no_findings"

    def test_roi_high_value(self):
        assert HuntROI.HIGH_VALUE == "high_value"

    def test_roi_moderate_value(self):
        assert HuntROI.MODERATE_VALUE == "moderate_value"

    def test_roi_low_value(self):
        assert HuntROI.LOW_VALUE == "low_value"

    def test_roi_break_even(self):
        assert HuntROI.BREAK_EVEN == "break_even"

    def test_roi_negative_roi(self):
        assert HuntROI.NEGATIVE_ROI == "negative_roi"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_hunt_record_defaults(self):
        r = HuntRecord()
        assert r.id
        assert r.hunt_name == ""
        assert r.hunt_type == HuntType.HYPOTHESIS_DRIVEN
        assert r.hunt_outcome == HuntOutcome.THREAT_FOUND
        assert r.hunt_roi == HuntROI.HIGH_VALUE
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_hunt_analysis_defaults(self):
        c = HuntAnalysis()
        assert c.id
        assert c.hunt_name == ""
        assert c.hunt_type == HuntType.HYPOTHESIS_DRIVEN
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_hunt_report_defaults(self):
        r = HuntReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.by_roi == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_hunt
# ---------------------------------------------------------------------------


class TestRecordHunt:
    def test_basic(self):
        eng = _engine()
        r = eng.record_hunt(
            hunt_name="hunt-001",
            hunt_type=HuntType.INTEL_DRIVEN,
            hunt_outcome=HuntOutcome.THREAT_FOUND,
            hunt_roi=HuntROI.HIGH_VALUE,
            effectiveness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.hunt_name == "hunt-001"
        assert r.hunt_type == HuntType.INTEL_DRIVEN
        assert r.hunt_outcome == HuntOutcome.THREAT_FOUND
        assert r.hunt_roi == HuntROI.HIGH_VALUE
        assert r.effectiveness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_hunt(hunt_name=f"hunt-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_hunt
# ---------------------------------------------------------------------------


class TestGetHunt:
    def test_found(self):
        eng = _engine()
        r = eng.record_hunt(
            hunt_name="hunt-001",
            hunt_roi=HuntROI.HIGH_VALUE,
        )
        result = eng.get_hunt(r.id)
        assert result is not None
        assert result.hunt_roi == HuntROI.HIGH_VALUE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_hunt("nonexistent") is None


# ---------------------------------------------------------------------------
# list_hunts
# ---------------------------------------------------------------------------


class TestListHunts:
    def test_list_all(self):
        eng = _engine()
        eng.record_hunt(hunt_name="hunt-001")
        eng.record_hunt(hunt_name="hunt-002")
        assert len(eng.list_hunts()) == 2

    def test_filter_by_hunt_type(self):
        eng = _engine()
        eng.record_hunt(
            hunt_name="hunt-001",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
        )
        eng.record_hunt(
            hunt_name="hunt-002",
            hunt_type=HuntType.INTEL_DRIVEN,
        )
        results = eng.list_hunts(hunt_type=HuntType.HYPOTHESIS_DRIVEN)
        assert len(results) == 1

    def test_filter_by_hunt_outcome(self):
        eng = _engine()
        eng.record_hunt(
            hunt_name="hunt-001",
            hunt_outcome=HuntOutcome.THREAT_FOUND,
        )
        eng.record_hunt(
            hunt_name="hunt-002",
            hunt_outcome=HuntOutcome.FALSE_POSITIVE,
        )
        results = eng.list_hunts(hunt_outcome=HuntOutcome.THREAT_FOUND)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_hunt(hunt_name="hunt-001", team="security")
        eng.record_hunt(hunt_name="hunt-002", team="platform")
        results = eng.list_hunts(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_hunt(hunt_name=f"hunt-{i}")
        assert len(eng.list_hunts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            hunt_name="hunt-001",
            hunt_type=HuntType.INTEL_DRIVEN,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low effectiveness detected",
        )
        assert a.hunt_name == "hunt-001"
        assert a.hunt_type == HuntType.INTEL_DRIVEN
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(hunt_name=f"hunt-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_hunt_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_hunt(
            hunt_name="hunt-001",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
            effectiveness_score=90.0,
        )
        eng.record_hunt(
            hunt_name="hunt-002",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
            effectiveness_score=70.0,
        )
        result = eng.analyze_hunt_distribution()
        assert "hypothesis_driven" in result
        assert result["hypothesis_driven"]["count"] == 2
        assert result["hypothesis_driven"]["avg_effectiveness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_hunt_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness_hunts
# ---------------------------------------------------------------------------


class TestIdentifyLowEffectivenessHunts:
    def test_detects_below_threshold(self):
        eng = _engine(hunt_effectiveness_threshold=80.0)
        eng.record_hunt(hunt_name="hunt-001", effectiveness_score=60.0)
        eng.record_hunt(hunt_name="hunt-002", effectiveness_score=90.0)
        results = eng.identify_low_effectiveness_hunts()
        assert len(results) == 1
        assert results[0]["hunt_name"] == "hunt-001"

    def test_sorted_ascending(self):
        eng = _engine(hunt_effectiveness_threshold=80.0)
        eng.record_hunt(hunt_name="hunt-001", effectiveness_score=50.0)
        eng.record_hunt(hunt_name="hunt-002", effectiveness_score=30.0)
        results = eng.identify_low_effectiveness_hunts()
        assert len(results) == 2
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness_hunts() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_hunt(hunt_name="hunt-001", service="auth-svc", effectiveness_score=90.0)
        eng.record_hunt(hunt_name="hunt-002", service="api-gw", effectiveness_score=50.0)
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_effectiveness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_hunt_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(hunt_name="hunt-001", analysis_score=50.0)
        result = eng.detect_hunt_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(hunt_name="hunt-001", analysis_score=20.0)
        eng.add_analysis(hunt_name="hunt-002", analysis_score=20.0)
        eng.add_analysis(hunt_name="hunt-003", analysis_score=80.0)
        eng.add_analysis(hunt_name="hunt-004", analysis_score=80.0)
        result = eng.detect_hunt_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_hunt_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(hunt_effectiveness_threshold=80.0)
        eng.record_hunt(
            hunt_name="hunt-001",
            hunt_type=HuntType.INTEL_DRIVEN,
            hunt_outcome=HuntOutcome.THREAT_FOUND,
            hunt_roi=HuntROI.HIGH_VALUE,
            effectiveness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, HuntReport)
        assert report.total_records == 1
        assert report.low_effectiveness_count == 1
        assert len(report.top_low_effectiveness) == 1
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
        eng.record_hunt(hunt_name="hunt-001")
        eng.add_analysis(hunt_name="hunt-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_hunt(
            hunt_name="hunt-001",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "hypothesis_driven" in stats["type_distribution"]
