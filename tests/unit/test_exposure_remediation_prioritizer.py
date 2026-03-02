"""Tests for exposure_remediation_prioritizer — ExposureRemediationPrioritizer."""

from __future__ import annotations

from shieldops.security.exposure_remediation_prioritizer import (
    ExposureRemediationPrioritizer,
    RemediationAction,
    RemediationEffort,
    RemediationPriorityAnalysis,
    RemediationPriorityRecord,
    RemediationPriorityReport,
    RemediationUrgency,
)


def _engine(**kw) -> ExposureRemediationPrioritizer:
    return ExposureRemediationPrioritizer(**kw)


class TestEnums:
    def test_remediationaction_val1(self):
        assert RemediationAction.PATCH == "patch"

    def test_remediationaction_val2(self):
        assert RemediationAction.RECONFIGURE == "reconfigure"

    def test_remediationaction_val3(self):
        assert RemediationAction.DECOMMISSION == "decommission"

    def test_remediationaction_val4(self):
        assert RemediationAction.RESTRICT_ACCESS == "restrict_access"

    def test_remediationaction_val5(self):
        assert RemediationAction.MONITOR == "monitor"

    def test_remediationeffort_val1(self):
        assert RemediationEffort.MINIMAL == "minimal"

    def test_remediationeffort_val2(self):
        assert RemediationEffort.LOW == "low"

    def test_remediationeffort_val3(self):
        assert RemediationEffort.MEDIUM == "medium"

    def test_remediationeffort_val4(self):
        assert RemediationEffort.HIGH == "high"

    def test_remediationeffort_val5(self):
        assert RemediationEffort.EXTENSIVE == "extensive"

    def test_remediationurgency_val1(self):
        assert RemediationUrgency.IMMEDIATE == "immediate"

    def test_remediationurgency_val2(self):
        assert RemediationUrgency.URGENT == "urgent"

    def test_remediationurgency_val3(self):
        assert RemediationUrgency.PLANNED == "planned"

    def test_remediationurgency_val4(self):
        assert RemediationUrgency.SCHEDULED == "scheduled"

    def test_remediationurgency_val5(self):
        assert RemediationUrgency.OPTIONAL == "optional"


class TestModels:
    def test_record_defaults(self):
        r = RemediationPriorityRecord()
        assert r.id
        assert r.exposure_name == ""

    def test_analysis_defaults(self):
        a = RemediationPriorityAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = RemediationPriorityReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_priority(
            exposure_name="test",
            remediation_action=RemediationAction.RECONFIGURE,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.exposure_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_priority(exposure_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_priority(exposure_name="test")
        assert eng.get_priority(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_priority("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_priority(exposure_name="a")
        eng.record_priority(exposure_name="b")
        assert len(eng.list_priorities()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_priority(exposure_name="a", remediation_action=RemediationAction.PATCH)
        eng.record_priority(exposure_name="b", remediation_action=RemediationAction.RECONFIGURE)
        assert len(eng.list_priorities(remediation_action=RemediationAction.PATCH)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_priority(exposure_name="a", remediation_urgency=RemediationUrgency.IMMEDIATE)
        eng.record_priority(exposure_name="b", remediation_urgency=RemediationUrgency.URGENT)
        assert len(eng.list_priorities(remediation_urgency=RemediationUrgency.IMMEDIATE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_priority(exposure_name="a", team="sec")
        eng.record_priority(exposure_name="b", team="ops")
        assert len(eng.list_priorities(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_priority(exposure_name=f"t-{i}")
        assert len(eng.list_priorities(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            exposure_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(exposure_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_priority(
            exposure_name="a", remediation_action=RemediationAction.PATCH, risk_score=90.0
        )
        eng.record_priority(
            exposure_name="b", remediation_action=RemediationAction.PATCH, risk_score=70.0
        )
        result = eng.analyze_distribution()
        assert RemediationAction.PATCH.value in result
        assert result[RemediationAction.PATCH.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_priority(exposure_name="a", risk_score=60.0)
        eng.record_priority(exposure_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_priority(exposure_name="a", risk_score=50.0)
        eng.record_priority(exposure_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_priority(exposure_name="a", service="auth", risk_score=90.0)
        eng.record_priority(exposure_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(exposure_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(exposure_name="a", analysis_score=20.0)
        eng.add_analysis(exposure_name="b", analysis_score=20.0)
        eng.add_analysis(exposure_name="c", analysis_score=80.0)
        eng.add_analysis(exposure_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_priority(exposure_name="test", risk_score=50.0)
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
        eng.record_priority(exposure_name="test")
        eng.add_analysis(exposure_name="test")
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
        eng.record_priority(exposure_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
