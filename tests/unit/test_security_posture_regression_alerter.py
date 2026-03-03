"""Tests for SecurityPostureRegressionAlerter."""

from __future__ import annotations

from shieldops.security.security_posture_regression_alerter import (
    AlertAction,
    RegressionAnalysis,
    RegressionCause,
    RegressionRecord,
    RegressionType,
    SecurityPostureRegressionAlerter,
    SecurityPostureRegressionReport,
)


def _engine(**kw) -> SecurityPostureRegressionAlerter:
    return SecurityPostureRegressionAlerter(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert RegressionType.CONFIGURATION == "configuration"

    def test_e1_v2(self):
        assert RegressionType.ACCESS_CONTROL == "access_control"

    def test_e1_v3(self):
        assert RegressionType.VULNERABILITY == "vulnerability"

    def test_e1_v4(self):
        assert RegressionType.COMPLIANCE == "compliance"

    def test_e1_v5(self):
        assert RegressionType.MONITORING == "monitoring"

    def test_e2_v1(self):
        assert RegressionCause.DEPLOYMENT == "deployment"

    def test_e2_v2(self):
        assert RegressionCause.CONFIGURATION_CHANGE == "configuration_change"

    def test_e2_v3(self):
        assert RegressionCause.POLICY_UPDATE == "policy_update"

    def test_e2_v4(self):
        assert RegressionCause.INFRASTRUCTURE == "infrastructure"

    def test_e2_v5(self):
        assert RegressionCause.HUMAN_ERROR == "human_error"

    def test_e3_v1(self):
        assert AlertAction.AUTO_REMEDIATE == "auto_remediate"

    def test_e3_v2(self):
        assert AlertAction.ESCALATE == "escalate"

    def test_e3_v3(self):
        assert AlertAction.MONITOR == "monitor"

    def test_e3_v4(self):
        assert AlertAction.ROLLBACK == "rollback"

    def test_e3_v5(self):
        assert AlertAction.ACCEPT == "accept"


class TestModels:
    def test_rec(self):
        r = RegressionRecord()
        assert r.id and r.regression_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = RegressionAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SecurityPostureRegressionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_regression(
            regression_id="t",
            regression_type=RegressionType.ACCESS_CONTROL,
            regression_cause=RegressionCause.CONFIGURATION_CHANGE,
            alert_action=AlertAction.ESCALATE,
            regression_score=92.0,
            service="s",
            team="t",
        )
        assert r.regression_id == "t" and r.regression_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_regression(regression_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_regression(regression_id="t")
        assert eng.get_regression(r.id) is not None

    def test_not_found(self):
        assert _engine().get_regression("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_regression(regression_id="a")
        eng.record_regression(regression_id="b")
        assert len(eng.list_regressions()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_regression(regression_id="a", regression_type=RegressionType.CONFIGURATION)
        eng.record_regression(regression_id="b", regression_type=RegressionType.ACCESS_CONTROL)
        assert len(eng.list_regressions(regression_type=RegressionType.CONFIGURATION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_regression(regression_id="a", regression_cause=RegressionCause.DEPLOYMENT)
        eng.record_regression(
            regression_id="b", regression_cause=RegressionCause.CONFIGURATION_CHANGE
        )
        assert len(eng.list_regressions(regression_cause=RegressionCause.DEPLOYMENT)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_regression(regression_id="a", team="x")
        eng.record_regression(regression_id="b", team="y")
        assert len(eng.list_regressions(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_regression(regression_id=f"t-{i}")
        assert len(eng.list_regressions(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            regression_id="t",
            regression_type=RegressionType.ACCESS_CONTROL,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(regression_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_regression(
            regression_id="a", regression_type=RegressionType.CONFIGURATION, regression_score=90.0
        )
        eng.record_regression(
            regression_id="b", regression_type=RegressionType.CONFIGURATION, regression_score=70.0
        )
        assert "configuration" in eng.analyze_regression_distribution()

    def test_empty(self):
        assert _engine().analyze_regression_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(regression_gap_threshold=80.0)
        eng.record_regression(regression_id="a", regression_score=60.0)
        eng.record_regression(regression_id="b", regression_score=90.0)
        assert len(eng.identify_regression_gaps()) == 1

    def test_sorted(self):
        eng = _engine(regression_gap_threshold=80.0)
        eng.record_regression(regression_id="a", regression_score=50.0)
        eng.record_regression(regression_id="b", regression_score=30.0)
        assert len(eng.identify_regression_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_regression(regression_id="a", service="s1", regression_score=80.0)
        eng.record_regression(regression_id="b", service="s2", regression_score=60.0)
        assert eng.rank_by_regression()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_regression() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(regression_id="t", analysis_score=float(v))
        assert eng.detect_regression_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(regression_id="t", analysis_score=float(v))
        assert eng.detect_regression_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_regression_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_regression(regression_id="t", regression_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_regression(regression_id="t")
        eng.add_analysis(regression_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_regression(regression_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_regression(regression_id="a")
        eng.record_regression(regression_id="b")
        eng.add_analysis(regression_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
