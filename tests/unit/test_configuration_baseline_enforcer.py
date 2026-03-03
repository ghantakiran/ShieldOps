"""Tests for shieldops.security.configuration_baseline_enforcer — ConfigurationBaselineEnforcer."""

from __future__ import annotations

from shieldops.security.configuration_baseline_enforcer import (
    BaselineAnalysis,
    BaselineRecord,
    BaselineSource,
    ConfigurationBaselineEnforcer,
    ConfigurationBaselineReport,
    DeviationType,
    EnforcementResult,
)


def _engine(**kw) -> ConfigurationBaselineEnforcer:
    return ConfigurationBaselineEnforcer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert BaselineSource.CIS_BENCHMARK == "cis_benchmark"

    def test_e1_v2(self):
        assert BaselineSource.VENDOR_HARDENING == "vendor_hardening"

    def test_e1_v3(self):
        assert BaselineSource.CUSTOM == "custom"

    def test_e1_v4(self):
        assert BaselineSource.INDUSTRY_STANDARD == "industry_standard"

    def test_e1_v5(self):
        assert BaselineSource.REGULATORY == "regulatory"

    def test_e2_v1(self):
        assert DeviationType.ADDED == "added"

    def test_e2_v2(self):
        assert DeviationType.REMOVED == "removed"

    def test_e2_v3(self):
        assert DeviationType.MODIFIED == "modified"

    def test_e2_v4(self):
        assert DeviationType.MISSING == "missing"

    def test_e2_v5(self):
        assert DeviationType.UNAUTHORIZED == "unauthorized"

    def test_e3_v1(self):
        assert EnforcementResult.COMPLIANT == "compliant"

    def test_e3_v2(self):
        assert EnforcementResult.REMEDIATED == "remediated"

    def test_e3_v3(self):
        assert EnforcementResult.EXCEPTION == "exception"

    def test_e3_v4(self):
        assert EnforcementResult.FAILED == "failed"

    def test_e3_v5(self):
        assert EnforcementResult.PENDING == "pending"


class TestModels:
    def test_rec(self):
        r = BaselineRecord()
        assert r.id and r.compliance_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = BaselineAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ConfigurationBaselineReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_baseline(
            baseline_id="t",
            baseline_source=BaselineSource.VENDOR_HARDENING,
            deviation_type=DeviationType.REMOVED,
            enforcement_result=EnforcementResult.REMEDIATED,
            compliance_score=92.0,
            service="s",
            team="t",
        )
        assert r.baseline_id == "t" and r.compliance_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_baseline(baseline_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_baseline(baseline_id="t")
        assert eng.get_baseline(r.id) is not None

    def test_not_found(self):
        assert _engine().get_baseline("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_baseline(baseline_id="a")
        eng.record_baseline(baseline_id="b")
        assert len(eng.list_baselines()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_baseline(baseline_id="a", baseline_source=BaselineSource.CIS_BENCHMARK)
        eng.record_baseline(baseline_id="b", baseline_source=BaselineSource.VENDOR_HARDENING)
        assert len(eng.list_baselines(baseline_source=BaselineSource.CIS_BENCHMARK)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_baseline(baseline_id="a", deviation_type=DeviationType.ADDED)
        eng.record_baseline(baseline_id="b", deviation_type=DeviationType.REMOVED)
        assert len(eng.list_baselines(deviation_type=DeviationType.ADDED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_baseline(baseline_id="a", team="x")
        eng.record_baseline(baseline_id="b", team="y")
        assert len(eng.list_baselines(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_baseline(baseline_id=f"t-{i}")
        assert len(eng.list_baselines(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            baseline_id="t",
            baseline_source=BaselineSource.VENDOR_HARDENING,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(baseline_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_baseline(
            baseline_id="a", baseline_source=BaselineSource.CIS_BENCHMARK, compliance_score=90.0
        )
        eng.record_baseline(
            baseline_id="b", baseline_source=BaselineSource.CIS_BENCHMARK, compliance_score=70.0
        )
        assert "cis_benchmark" in eng.analyze_baseline_distribution()

    def test_empty(self):
        assert _engine().analyze_baseline_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_baseline(baseline_id="a", compliance_score=60.0)
        eng.record_baseline(baseline_id="b", compliance_score=90.0)
        assert len(eng.identify_baseline_gaps()) == 1

    def test_sorted(self):
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_baseline(baseline_id="a", compliance_score=50.0)
        eng.record_baseline(baseline_id="b", compliance_score=30.0)
        assert len(eng.identify_baseline_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_baseline(baseline_id="a", service="s1", compliance_score=80.0)
        eng.record_baseline(baseline_id="b", service="s2", compliance_score=60.0)
        assert eng.rank_by_baseline()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_baseline() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(baseline_id="t", analysis_score=float(v))
        assert eng.detect_baseline_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(baseline_id="t", analysis_score=float(v))
        assert eng.detect_baseline_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_baseline_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_baseline(baseline_id="t", compliance_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_baseline(baseline_id="t")
        eng.add_analysis(baseline_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_baseline(baseline_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_baseline(baseline_id="a")
        eng.record_baseline(baseline_id="b")
        eng.add_analysis(baseline_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
