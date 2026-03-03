"""Tests for shieldops.security.conditional_access_engine — ConditionalAccessEngine."""

from __future__ import annotations

from shieldops.security.conditional_access_engine import (
    AccessAction,
    AccessPolicyAnalysis,
    AccessPolicyRecord,
    ConditionalAccessEngine,
    ConditionalAccessReport,
    EvaluationResult,
    PolicyCondition,
)


def _engine(**kw) -> ConditionalAccessEngine:
    return ConditionalAccessEngine(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert PolicyCondition.LOCATION == "location"

    def test_e1_v2(self):
        assert PolicyCondition.DEVICE_STATE == "device_state"

    def test_e1_v3(self):
        assert PolicyCondition.RISK_LEVEL == "risk_level"

    def test_e1_v4(self):
        assert PolicyCondition.USER_GROUP == "user_group"

    def test_e1_v5(self):
        assert PolicyCondition.APPLICATION == "application"

    def test_e2_v1(self):
        assert AccessAction.GRANT == "grant"

    def test_e2_v2(self):
        assert AccessAction.BLOCK == "block"

    def test_e2_v3(self):
        assert AccessAction.REQUIRE_MFA == "require_mfa"

    def test_e2_v4(self):
        assert AccessAction.LIMIT_ACCESS == "limit_access"

    def test_e2_v5(self):
        assert AccessAction.SESSION_CONTROL == "session_control"

    def test_e3_v1(self):
        assert EvaluationResult.PASSED == "passed"  # noqa: S105

    def test_e3_v2(self):
        assert EvaluationResult.FAILED == "failed"

    def test_e3_v3(self):
        assert EvaluationResult.CONDITIONAL == "conditional"

    def test_e3_v4(self):
        assert EvaluationResult.SKIPPED == "skipped"

    def test_e3_v5(self):
        assert EvaluationResult.ERROR == "error"


class TestModels:
    def test_rec(self):
        r = AccessPolicyRecord()
        assert r.id and r.policy_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = AccessPolicyAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ConditionalAccessReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_policy(
            policy_id="t",
            policy_condition=PolicyCondition.DEVICE_STATE,
            access_action=AccessAction.BLOCK,
            evaluation_result=EvaluationResult.FAILED,
            policy_score=92.0,
            service="s",
            team="t",
        )
        assert r.policy_id == "t" and r.policy_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_policy(policy_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_policy(policy_id="t")
        assert eng.get_policy(r.id) is not None

    def test_not_found(self):
        assert _engine().get_policy("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_policy(policy_id="a")
        eng.record_policy(policy_id="b")
        assert len(eng.list_policies()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_policy(policy_id="a", policy_condition=PolicyCondition.LOCATION)
        eng.record_policy(policy_id="b", policy_condition=PolicyCondition.DEVICE_STATE)
        assert len(eng.list_policies(policy_condition=PolicyCondition.LOCATION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_policy(policy_id="a", access_action=AccessAction.GRANT)
        eng.record_policy(policy_id="b", access_action=AccessAction.BLOCK)
        assert len(eng.list_policies(access_action=AccessAction.GRANT)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_policy(policy_id="a", team="x")
        eng.record_policy(policy_id="b", team="y")
        assert len(eng.list_policies(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_policy(policy_id=f"t-{i}")
        assert len(eng.list_policies(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            policy_id="t",
            policy_condition=PolicyCondition.DEVICE_STATE,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(policy_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_policy(
            policy_id="a", policy_condition=PolicyCondition.LOCATION, policy_score=90.0
        )
        eng.record_policy(
            policy_id="b", policy_condition=PolicyCondition.LOCATION, policy_score=70.0
        )
        assert "location" in eng.analyze_policy_distribution()

    def test_empty(self):
        assert _engine().analyze_policy_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(policy_gap_threshold=80.0)
        eng.record_policy(policy_id="a", policy_score=60.0)
        eng.record_policy(policy_id="b", policy_score=90.0)
        assert len(eng.identify_policy_gaps()) == 1

    def test_sorted(self):
        eng = _engine(policy_gap_threshold=80.0)
        eng.record_policy(policy_id="a", policy_score=50.0)
        eng.record_policy(policy_id="b", policy_score=30.0)
        assert len(eng.identify_policy_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_policy(policy_id="a", service="s1", policy_score=80.0)
        eng.record_policy(policy_id="b", service="s2", policy_score=60.0)
        assert eng.rank_by_policy()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_policy() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(policy_id="t", analysis_score=float(v))
        assert eng.detect_policy_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(policy_id="t", analysis_score=float(v))
        assert eng.detect_policy_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_policy_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_policy(policy_id="t", policy_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_policy(policy_id="t")
        eng.add_analysis(policy_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_policy(policy_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_policy(policy_id="a")
        eng.record_policy(policy_id="b")
        eng.add_analysis(policy_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
