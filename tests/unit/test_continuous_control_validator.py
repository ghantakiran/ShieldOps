"""Tests for shieldops.compliance.continuous_control_validator — ContinuousControlValidator."""

from __future__ import annotations

from shieldops.compliance.continuous_control_validator import (
    ContinuousControlValidationReport,
    ContinuousControlValidator,
    ControlEffectiveness,
    ControlFramework,
    ControlValidationAnalysis,
    ControlValidationRecord,
    ValidationFrequency,
)


def _engine(**kw) -> ContinuousControlValidator:
    return ContinuousControlValidator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ControlFramework.NIST_CSF == "nist_csf"

    def test_e1_v2(self):
        assert ControlFramework.ISO_27001 == "iso_27001"

    def test_e1_v3(self):
        assert ControlFramework.CIS_CONTROLS == "cis_controls"

    def test_e1_v4(self):
        assert ControlFramework.COBIT == "cobit"

    def test_e1_v5(self):
        assert ControlFramework.SOC2_TSC == "soc2_tsc"

    def test_e2_v1(self):
        assert ValidationFrequency.CONTINUOUS == "continuous"

    def test_e2_v2(self):
        assert ValidationFrequency.DAILY == "daily"

    def test_e2_v3(self):
        assert ValidationFrequency.WEEKLY == "weekly"

    def test_e2_v4(self):
        assert ValidationFrequency.MONTHLY == "monthly"

    def test_e2_v5(self):
        assert ValidationFrequency.ON_DEMAND == "on_demand"

    def test_e3_v1(self):
        assert ControlEffectiveness.EFFECTIVE == "effective"

    def test_e3_v2(self):
        assert ControlEffectiveness.PARTIALLY_EFFECTIVE == "partially_effective"

    def test_e3_v3(self):
        assert ControlEffectiveness.INEFFECTIVE == "ineffective"

    def test_e3_v4(self):
        assert ControlEffectiveness.NOT_IMPLEMENTED == "not_implemented"

    def test_e3_v5(self):
        assert ControlEffectiveness.NOT_APPLICABLE == "not_applicable"


class TestModels:
    def test_rec(self):
        r = ControlValidationRecord()
        assert r.id and r.validation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ControlValidationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ContinuousControlValidationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_validation(
            validation_id="t",
            control_framework=ControlFramework.ISO_27001,
            validation_frequency=ValidationFrequency.DAILY,
            control_effectiveness=ControlEffectiveness.PARTIALLY_EFFECTIVE,
            validation_score=92.0,
            service="s",
            team="t",
        )
        assert r.validation_id == "t" and r.validation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(validation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation(validation_id="t")
        assert eng.get_validation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_validation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_validation(validation_id="a")
        eng.record_validation(validation_id="b")
        assert len(eng.list_validations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_validation(validation_id="a", control_framework=ControlFramework.NIST_CSF)
        eng.record_validation(validation_id="b", control_framework=ControlFramework.ISO_27001)
        assert len(eng.list_validations(control_framework=ControlFramework.NIST_CSF)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_validation(
            validation_id="a", validation_frequency=ValidationFrequency.CONTINUOUS
        )
        eng.record_validation(validation_id="b", validation_frequency=ValidationFrequency.DAILY)
        assert len(eng.list_validations(validation_frequency=ValidationFrequency.CONTINUOUS)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_validation(validation_id="a", team="x")
        eng.record_validation(validation_id="b", team="y")
        assert len(eng.list_validations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(validation_id=f"t-{i}")
        assert len(eng.list_validations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            validation_id="t",
            control_framework=ControlFramework.ISO_27001,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(validation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_validation(
            validation_id="a", control_framework=ControlFramework.NIST_CSF, validation_score=90.0
        )
        eng.record_validation(
            validation_id="b", control_framework=ControlFramework.NIST_CSF, validation_score=70.0
        )
        assert "nist_csf" in eng.analyze_validation_distribution()

    def test_empty(self):
        assert _engine().analyze_validation_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(validation_gap_threshold=80.0)
        eng.record_validation(validation_id="a", validation_score=60.0)
        eng.record_validation(validation_id="b", validation_score=90.0)
        assert len(eng.identify_validation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(validation_gap_threshold=80.0)
        eng.record_validation(validation_id="a", validation_score=50.0)
        eng.record_validation(validation_id="b", validation_score=30.0)
        assert len(eng.identify_validation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_validation(validation_id="a", service="s1", validation_score=80.0)
        eng.record_validation(validation_id="b", service="s2", validation_score=60.0)
        assert eng.rank_by_validation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_validation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(validation_id="t", analysis_score=float(v))
        assert eng.detect_validation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(validation_id="t", analysis_score=float(v))
        assert eng.detect_validation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_validation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_validation(validation_id="t", validation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_validation(validation_id="t")
        eng.add_analysis(validation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_validation(validation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_validation(validation_id="a")
        eng.record_validation(validation_id="b")
        eng.add_analysis(validation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
