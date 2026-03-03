"""Tests for shieldops.security.admission_controller_enforcer — AdmissionControllerEnforcer."""

from __future__ import annotations

from shieldops.security.admission_controller_enforcer import (
    AdmissionAnalysis,
    AdmissionControllerEnforcer,
    AdmissionControllerReport,
    AdmissionRecord,
    ControllerType,
    EnforcementMode,
    PolicyCategory,
)


def _engine(**kw) -> AdmissionControllerEnforcer:
    return AdmissionControllerEnforcer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ControllerType.VALIDATING == "validating"

    def test_e1_v2(self):
        assert ControllerType.MUTATING == "mutating"

    def test_e1_v3(self):
        assert ControllerType.OPA_GATEKEEPER == "opa_gatekeeper"

    def test_e1_v4(self):
        assert ControllerType.KYVERNO == "kyverno"

    def test_e1_v5(self):
        assert ControllerType.CUSTOM == "custom"

    def test_e2_v1(self):
        assert EnforcementMode.ENFORCE == "enforce"

    def test_e2_v2(self):
        assert EnforcementMode.AUDIT == "audit"

    def test_e2_v3(self):
        assert EnforcementMode.WARN == "warn"

    def test_e2_v4(self):
        assert EnforcementMode.DRY_RUN == "dry_run"

    def test_e2_v5(self):
        assert EnforcementMode.DISABLED == "disabled"

    def test_e3_v1(self):
        assert PolicyCategory.SECURITY == "security"

    def test_e3_v2(self):
        assert PolicyCategory.COMPLIANCE == "compliance"

    def test_e3_v3(self):
        assert PolicyCategory.RESOURCE == "resource"

    def test_e3_v4(self):
        assert PolicyCategory.NAMING == "naming"

    def test_e3_v5(self):
        assert PolicyCategory.CUSTOM == "custom"


class TestModels:
    def test_rec(self):
        r = AdmissionRecord()
        assert r.id and r.enforcement_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = AdmissionAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = AdmissionControllerReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_admission(
            admission_id="t",
            controller_type=ControllerType.MUTATING,
            enforcement_mode=EnforcementMode.AUDIT,
            policy_category=PolicyCategory.COMPLIANCE,
            enforcement_score=92.0,
            service="s",
            team="t",
        )
        assert r.admission_id == "t" and r.enforcement_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_admission(admission_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_admission(admission_id="t")
        assert eng.get_admission(r.id) is not None

    def test_not_found(self):
        assert _engine().get_admission("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_admission(admission_id="a")
        eng.record_admission(admission_id="b")
        assert len(eng.list_admissions()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_admission(admission_id="a", controller_type=ControllerType.VALIDATING)
        eng.record_admission(admission_id="b", controller_type=ControllerType.MUTATING)
        assert len(eng.list_admissions(controller_type=ControllerType.VALIDATING)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_admission(admission_id="a", enforcement_mode=EnforcementMode.ENFORCE)
        eng.record_admission(admission_id="b", enforcement_mode=EnforcementMode.AUDIT)
        assert len(eng.list_admissions(enforcement_mode=EnforcementMode.ENFORCE)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_admission(admission_id="a", team="x")
        eng.record_admission(admission_id="b", team="y")
        assert len(eng.list_admissions(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_admission(admission_id=f"t-{i}")
        assert len(eng.list_admissions(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            admission_id="t",
            controller_type=ControllerType.MUTATING,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(admission_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_admission(
            admission_id="a", controller_type=ControllerType.VALIDATING, enforcement_score=90.0
        )
        eng.record_admission(
            admission_id="b", controller_type=ControllerType.VALIDATING, enforcement_score=70.0
        )
        assert "validating" in eng.analyze_controller_distribution()

    def test_empty(self):
        assert _engine().analyze_controller_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(enforcement_gap_threshold=80.0)
        eng.record_admission(admission_id="a", enforcement_score=60.0)
        eng.record_admission(admission_id="b", enforcement_score=90.0)
        assert len(eng.identify_enforcement_gaps()) == 1

    def test_sorted(self):
        eng = _engine(enforcement_gap_threshold=80.0)
        eng.record_admission(admission_id="a", enforcement_score=50.0)
        eng.record_admission(admission_id="b", enforcement_score=30.0)
        assert len(eng.identify_enforcement_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_admission(admission_id="a", service="s1", enforcement_score=80.0)
        eng.record_admission(admission_id="b", service="s2", enforcement_score=60.0)
        assert eng.rank_by_enforcement()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_enforcement() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(admission_id="t", analysis_score=float(v))
        assert eng.detect_enforcement_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(admission_id="t", analysis_score=float(v))
        assert eng.detect_enforcement_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_enforcement_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_admission(admission_id="t", enforcement_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_admission(admission_id="t")
        eng.add_analysis(admission_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_admission(admission_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_admission(admission_id="a")
        eng.record_admission(admission_id="b")
        eng.add_analysis(admission_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
