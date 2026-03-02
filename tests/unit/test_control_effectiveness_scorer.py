"""Tests for shieldops.compliance.control_effectiveness_scorer — ControlEffectivenessScorer."""

from __future__ import annotations

from shieldops.compliance.control_effectiveness_scorer import (
    ControlAnalysis,
    ControlEffectivenessReport,
    ControlEffectivenessScorer,
    ControlMaturity,
    ControlRecord,
    ControlType,
    TestResult,
)


def _engine(**kw) -> ControlEffectivenessScorer:
    return ControlEffectivenessScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_controltype_preventive(self):
        assert ControlType.PREVENTIVE == "preventive"

    def test_controltype_detective(self):
        assert ControlType.DETECTIVE == "detective"

    def test_controltype_corrective(self):
        assert ControlType.CORRECTIVE == "corrective"

    def test_controltype_compensating(self):
        assert ControlType.COMPENSATING == "compensating"

    def test_controltype_directive(self):
        assert ControlType.DIRECTIVE == "directive"

    def test_testresult_pass(self):
        assert TestResult.PASS == "pass"  # noqa: S105

    def test_testresult_fail(self):
        assert TestResult.FAIL == "fail"

    def test_testresult_partial(self):
        assert TestResult.PARTIAL == "partial"

    def test_testresult_not_tested(self):
        assert TestResult.NOT_TESTED == "not_tested"

    def test_testresult_exempt(self):
        assert TestResult.EXEMPT == "exempt"

    def test_controlmaturity_optimized(self):
        assert ControlMaturity.OPTIMIZED == "optimized"

    def test_controlmaturity_managed(self):
        assert ControlMaturity.MANAGED == "managed"

    def test_controlmaturity_defined(self):
        assert ControlMaturity.DEFINED == "defined"

    def test_controlmaturity_developing(self):
        assert ControlMaturity.DEVELOPING == "developing"

    def test_controlmaturity_initial(self):
        assert ControlMaturity.INITIAL == "initial"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_controlrecord_defaults(self):
        r = ControlRecord()
        assert r.id
        assert r.control_name == ""
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_controlanalysis_defaults(self):
        c = ControlAnalysis()
        assert c.id
        assert c.control_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_controleffectivenessreport_defaults(self):
        r = ControlEffectivenessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0
        assert r.by_type == {}
        assert r.by_result == {}
        assert r.by_maturity == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_control
# ---------------------------------------------------------------------------


class TestRecordControl:
    def test_basic(self):
        eng = _engine()
        r = eng.record_control(
            control_name="test-item",
            control_type=ControlType.DETECTIVE,
            effectiveness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.control_name == "test-item"
        assert r.effectiveness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_control(control_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_control
# ---------------------------------------------------------------------------


class TestGetControl:
    def test_found(self):
        eng = _engine()
        r = eng.record_control(control_name="test-item")
        result = eng.get_control(r.id)
        assert result is not None
        assert result.control_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_control("nonexistent") is None


# ---------------------------------------------------------------------------
# list_controls
# ---------------------------------------------------------------------------


class TestListControls:
    def test_list_all(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001")
        eng.record_control(control_name="ITEM-002")
        assert len(eng.list_controls()) == 2

    def test_filter_by_control_type(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", control_type=ControlType.PREVENTIVE)
        eng.record_control(control_name="ITEM-002", control_type=ControlType.DETECTIVE)
        results = eng.list_controls(control_type=ControlType.PREVENTIVE)
        assert len(results) == 1

    def test_filter_by_test_result(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", test_result=TestResult.PASS)
        eng.record_control(control_name="ITEM-002", test_result=TestResult.FAIL)
        results = eng.list_controls(test_result=TestResult.PASS)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", team="security")
        eng.record_control(control_name="ITEM-002", team="platform")
        results = eng.list_controls(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_control(control_name=f"ITEM-{i}")
        assert len(eng.list_controls(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            control_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.control_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(control_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_type_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_control(
            control_name="ITEM-001", control_type=ControlType.PREVENTIVE, effectiveness_score=90.0
        )
        eng.record_control(
            control_name="ITEM-002", control_type=ControlType.PREVENTIVE, effectiveness_score=70.0
        )
        result = eng.analyze_type_distribution()
        assert "preventive" in result
        assert result["preventive"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness_controls
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(control_effectiveness_threshold=75.0)
        eng.record_control(control_name="ITEM-001", effectiveness_score=30.0)
        eng.record_control(control_name="ITEM-002", effectiveness_score=90.0)
        results = eng.identify_low_effectiveness_controls()
        assert len(results) == 1
        assert results[0]["control_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(control_effectiveness_threshold=75.0)
        eng.record_control(control_name="ITEM-001", effectiveness_score=50.0)
        eng.record_control(control_name="ITEM-002", effectiveness_score=30.0)
        results = eng.identify_low_effectiveness_controls()
        assert len(results) == 2
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness_controls() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_control(control_name="ITEM-001", service="auth-svc", effectiveness_score=90.0)
        eng.record_control(control_name="ITEM-002", service="api-gw", effectiveness_score=50.0)
        results = eng.rank_by_effectiveness_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness_score() == []


# ---------------------------------------------------------------------------
# detect_effectiveness_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(control_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(control_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(control_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(control_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(control_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(control_effectiveness_threshold=75.0)
        eng.record_control(control_name="test-item", effectiveness_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, ControlEffectivenessReport)
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
        eng.record_control(control_name="ITEM-001")
        eng.add_analysis(control_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_control(
            control_name="ITEM-001",
            control_type=ControlType.PREVENTIVE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
