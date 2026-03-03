"""Tests for shieldops.security.pod_network_policy_validator — PodNetworkPolicyValidator."""

from __future__ import annotations

from shieldops.security.pod_network_policy_validator import (
    NetworkPolicyAnalysis,
    NetworkPolicyRecord,
    PodNetworkPolicyReport,
    PodNetworkPolicyValidator,
    PolicyAction,
    PolicyScope,
    ValidationResult,
)


def _engine(**kw) -> PodNetworkPolicyValidator:
    return PodNetworkPolicyValidator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert PolicyScope.INGRESS == "ingress"

    def test_e1_v2(self):
        assert PolicyScope.EGRESS == "egress"

    def test_e1_v3(self):
        assert PolicyScope.BOTH == "both"

    def test_e1_v4(self):
        assert PolicyScope.NONE == "none"

    def test_e1_v5(self):
        assert PolicyScope.DEFAULT == "default"

    def test_e2_v1(self):
        assert ValidationResult.COMPLIANT == "compliant"

    def test_e2_v2(self):
        assert ValidationResult.VIOLATION == "violation"

    def test_e2_v3(self):
        assert ValidationResult.MISSING == "missing"

    def test_e2_v4(self):
        assert ValidationResult.OVERPERMISSIVE == "overpermissive"

    def test_e2_v5(self):
        assert ValidationResult.REDUNDANT == "redundant"

    def test_e3_v1(self):
        assert PolicyAction.ALLOW == "allow"

    def test_e3_v2(self):
        assert PolicyAction.DENY == "deny"

    def test_e3_v3(self):
        assert PolicyAction.LOG == "log"

    def test_e3_v4(self):
        assert PolicyAction.ALERT == "alert"

    def test_e3_v5(self):
        assert PolicyAction.QUARANTINE == "quarantine"


class TestModels:
    def test_rec(self):
        r = NetworkPolicyRecord()
        assert r.id and r.validation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = NetworkPolicyAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = PodNetworkPolicyReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_validation(
            policy_id="t",
            policy_scope=PolicyScope.EGRESS,
            validation_result=ValidationResult.VIOLATION,
            policy_action=PolicyAction.DENY,
            validation_score=92.0,
            service="s",
            team="t",
        )
        assert r.policy_id == "t" and r.validation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(policy_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation(policy_id="t")
        assert eng.get_validation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_validation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_validation(policy_id="a")
        eng.record_validation(policy_id="b")
        assert len(eng.list_validations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_validation(policy_id="a", policy_scope=PolicyScope.INGRESS)
        eng.record_validation(policy_id="b", policy_scope=PolicyScope.EGRESS)
        assert len(eng.list_validations(policy_scope=PolicyScope.INGRESS)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_validation(policy_id="a", validation_result=ValidationResult.COMPLIANT)
        eng.record_validation(policy_id="b", validation_result=ValidationResult.VIOLATION)
        assert len(eng.list_validations(validation_result=ValidationResult.COMPLIANT)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_validation(policy_id="a", team="x")
        eng.record_validation(policy_id="b", team="y")
        assert len(eng.list_validations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(policy_id=f"t-{i}")
        assert len(eng.list_validations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            policy_id="t", policy_scope=PolicyScope.EGRESS, analysis_score=88.5, breached=True
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
        eng.record_validation(
            policy_id="a", policy_scope=PolicyScope.INGRESS, validation_score=90.0
        )
        eng.record_validation(
            policy_id="b", policy_scope=PolicyScope.INGRESS, validation_score=70.0
        )
        assert "ingress" in eng.analyze_scope_distribution()

    def test_empty(self):
        assert _engine().analyze_scope_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(validation_gap_threshold=80.0)
        eng.record_validation(policy_id="a", validation_score=60.0)
        eng.record_validation(policy_id="b", validation_score=90.0)
        assert len(eng.identify_validation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(validation_gap_threshold=80.0)
        eng.record_validation(policy_id="a", validation_score=50.0)
        eng.record_validation(policy_id="b", validation_score=30.0)
        assert len(eng.identify_validation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_validation(policy_id="a", service="s1", validation_score=80.0)
        eng.record_validation(policy_id="b", service="s2", validation_score=60.0)
        assert eng.rank_by_validation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_validation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(policy_id="t", analysis_score=float(v))
        assert eng.detect_validation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(policy_id="t", analysis_score=float(v))
        assert eng.detect_validation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_validation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_validation(policy_id="t", validation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_validation(policy_id="t")
        eng.add_analysis(policy_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_validation(policy_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_validation(policy_id="a")
        eng.record_validation(policy_id="b")
        eng.add_analysis(policy_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
