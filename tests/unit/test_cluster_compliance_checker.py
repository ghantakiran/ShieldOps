"""Tests for shieldops.security.cluster_compliance_checker — ClusterComplianceChecker."""

from __future__ import annotations

from shieldops.security.cluster_compliance_checker import (
    CheckResult,
    ClusterComplianceChecker,
    ClusterComplianceReport,
    ComplianceBenchmark,
    ComplianceCheckAnalysis,
    ComplianceCheckRecord,
    RemediationPriority,
)


def _engine(**kw) -> ClusterComplianceChecker:
    return ClusterComplianceChecker(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ComplianceBenchmark.CIS_K8S == "cis_k8s"

    def test_e1_v2(self):
        assert ComplianceBenchmark.NSA_CISA == "nsa_cisa"

    def test_e1_v3(self):
        assert ComplianceBenchmark.SOC2 == "soc2"

    def test_e1_v4(self):
        assert ComplianceBenchmark.PCI_DSS == "pci_dss"

    def test_e1_v5(self):
        assert ComplianceBenchmark.CUSTOM == "custom"

    def test_e2_v1(self):
        assert CheckResult.PASS == "pass"  # noqa: S105

    def test_e2_v2(self):
        assert CheckResult.FAIL == "fail"

    def test_e2_v3(self):
        assert CheckResult.WARN == "warn"

    def test_e2_v4(self):
        assert CheckResult.SKIP == "skip"

    def test_e2_v5(self):
        assert CheckResult.NOT_APPLICABLE == "not_applicable"

    def test_e3_v1(self):
        assert RemediationPriority.IMMEDIATE == "immediate"

    def test_e3_v2(self):
        assert RemediationPriority.HIGH == "high"

    def test_e3_v3(self):
        assert RemediationPriority.MEDIUM == "medium"

    def test_e3_v4(self):
        assert RemediationPriority.LOW == "low"

    def test_e3_v5(self):
        assert RemediationPriority.DEFERRED == "deferred"


class TestModels:
    def test_rec(self):
        r = ComplianceCheckRecord()
        assert r.id and r.compliance_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ComplianceCheckAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ClusterComplianceReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_check(
            check_id="t",
            compliance_benchmark=ComplianceBenchmark.NSA_CISA,
            check_result=CheckResult.FAIL,
            remediation_priority=RemediationPriority.HIGH,
            compliance_score=92.0,
            service="s",
            team="t",
        )
        assert r.check_id == "t" and r.compliance_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_check(check_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_check(check_id="t")
        assert eng.get_check(r.id) is not None

    def test_not_found(self):
        assert _engine().get_check("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_check(check_id="a")
        eng.record_check(check_id="b")
        assert len(eng.list_checks()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_check(check_id="a", compliance_benchmark=ComplianceBenchmark.CIS_K8S)
        eng.record_check(check_id="b", compliance_benchmark=ComplianceBenchmark.NSA_CISA)
        assert len(eng.list_checks(compliance_benchmark=ComplianceBenchmark.CIS_K8S)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_check(check_id="a", check_result=CheckResult.PASS)
        eng.record_check(check_id="b", check_result=CheckResult.FAIL)
        assert len(eng.list_checks(check_result=CheckResult.PASS)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_check(check_id="a", team="x")
        eng.record_check(check_id="b", team="y")
        assert len(eng.list_checks(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_check(check_id=f"t-{i}")
        assert len(eng.list_checks(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            check_id="t",
            compliance_benchmark=ComplianceBenchmark.NSA_CISA,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(check_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_check(
            check_id="a", compliance_benchmark=ComplianceBenchmark.CIS_K8S, compliance_score=90.0
        )
        eng.record_check(
            check_id="b", compliance_benchmark=ComplianceBenchmark.CIS_K8S, compliance_score=70.0
        )
        assert "cis_k8s" in eng.analyze_benchmark_distribution()

    def test_empty(self):
        assert _engine().analyze_benchmark_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_check(check_id="a", compliance_score=60.0)
        eng.record_check(check_id="b", compliance_score=90.0)
        assert len(eng.identify_compliance_gaps()) == 1

    def test_sorted(self):
        eng = _engine(compliance_gap_threshold=80.0)
        eng.record_check(check_id="a", compliance_score=50.0)
        eng.record_check(check_id="b", compliance_score=30.0)
        assert len(eng.identify_compliance_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_check(check_id="a", service="s1", compliance_score=80.0)
        eng.record_check(check_id="b", service="s2", compliance_score=60.0)
        assert eng.rank_by_compliance()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_compliance() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(check_id="t", analysis_score=float(v))
        assert eng.detect_compliance_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(check_id="t", analysis_score=float(v))
        assert eng.detect_compliance_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_compliance_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_check(check_id="t", compliance_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_check(check_id="t")
        eng.add_analysis(check_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_check(check_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_check(check_id="a")
        eng.record_check(check_id="b")
        eng.add_analysis(check_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
