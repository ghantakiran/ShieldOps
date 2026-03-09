"""Tests for SecurityChaosEngine."""

from __future__ import annotations

from shieldops.security.security_chaos_engine import (
    ChaosReport,
    Experiment,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
    ResilienceGrade,
    SecurityChaosEngine,
)


def _engine(**kw) -> SecurityChaosEngine:
    return SecurityChaosEngine(**kw)


# --- Enum tests ---


class TestEnums:
    def test_type_credential_leak(self):
        assert ExperimentType.CREDENTIAL_LEAK == "credential_leak"

    def test_type_network_partition(self):
        assert ExperimentType.NETWORK_PARTITION == "network_partition"

    def test_type_cert_expiry(self):
        assert ExperimentType.CERTIFICATE_EXPIRY == "certificate_expiry"

    def test_type_dns_hijack(self):
        assert ExperimentType.DNS_HIJACK == "dns_hijack"

    def test_type_priv_esc(self):
        assert ExperimentType.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_type_data_corruption(self):
        assert ExperimentType.DATA_CORRUPTION == "data_corruption"

    def test_status_designed(self):
        assert ExperimentStatus.DESIGNED == "designed"

    def test_status_running(self):
        assert ExperimentStatus.RUNNING == "running"

    def test_status_completed(self):
        assert ExperimentStatus.COMPLETED == "completed"

    def test_status_aborted(self):
        assert ExperimentStatus.ABORTED == "aborted"

    def test_grade_excellent(self):
        assert ResilienceGrade.EXCELLENT == "excellent"

    def test_grade_critical(self):
        assert ResilienceGrade.CRITICAL == "critical"


# --- Model tests ---


class TestModels:
    def test_experiment_defaults(self):
        e = Experiment()
        assert e.id
        assert e.experiment_type == ExperimentType.CREDENTIAL_LEAK
        assert e.status == ExperimentStatus.DESIGNED

    def test_result_defaults(self):
        r = ExperimentResult()
        assert r.id
        assert r.detected is False
        assert r.findings == []

    def test_report_defaults(self):
        r = ChaosReport()
        assert r.total_experiments == 0
        assert r.grade == ""


# --- design_experiment ---


class TestDesignExperiment:
    def test_basic(self):
        eng = _engine()
        e = eng.design_experiment(
            name="cred-leak-test",
            experiment_type=ExperimentType.CREDENTIAL_LEAK,
            blast_radius="single-host",
            target_service="auth",
            team="sec",
            hypothesis="Auth service detects leaked creds within 5 min",
        )
        assert e.name == "cred-leak-test"
        assert e.experiment_type == ExperimentType.CREDENTIAL_LEAK
        assert e.hypothesis != ""

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.design_experiment(name=f"e-{i}")
        assert len(eng._experiments) == 3


# --- inject_security_failure ---


class TestInjectFailure:
    def test_success(self):
        eng = _engine()
        e = eng.design_experiment(name="test")
        result = eng.inject_security_failure(e.id)
        assert result["status"] == "running"
        assert e.status == ExperimentStatus.RUNNING

    def test_not_found(self):
        eng = _engine()
        result = eng.inject_security_failure("unknown")
        assert result["error"] == "not_found"


# --- observe_response ---


class TestObserveResponse:
    def test_detected(self):
        eng = _engine()
        e = eng.design_experiment(name="test")
        eng.inject_security_failure(e.id)
        r = eng.observe_response(
            e.id,
            detected=True,
            resilience_score=85.0,
            findings=["detected in 30s"],
        )
        assert r.detected is True
        assert r.resilience_score == 85.0
        assert e.status == ExperimentStatus.COMPLETED

    def test_not_detected(self):
        eng = _engine()
        e = eng.design_experiment(name="test")
        r = eng.observe_response(e.id, detected=False, resilience_score=20.0)
        assert r.detected is False

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.observe_response(f"e-{i}", resilience_score=50.0)
        assert len(eng._results) == 2


# --- evaluate_resilience ---


class TestEvaluateResilience:
    def test_with_data(self):
        eng = _engine()
        e = eng.design_experiment(name="test")
        eng.observe_response(e.id, detected=True, resilience_score=90.0)
        result = eng.evaluate_resilience()
        assert result["avg_resilience"] == 90.0
        assert result["detection_rate"] == 100.0
        assert result["grade"] == "excellent"

    def test_empty(self):
        eng = _engine()
        result = eng.evaluate_resilience()
        assert result["grade"] == "critical"

    def test_poor_grade(self):
        eng = _engine()
        eng.observe_response("e1", detected=False, resilience_score=30.0)
        result = eng.evaluate_resilience()
        assert result["grade"] == "poor"

    def test_fair_grade(self):
        eng = _engine()
        eng.observe_response("e1", detected=True, resilience_score=55.0)
        result = eng.evaluate_resilience()
        assert result["grade"] == "fair"


# --- generate_findings ---


class TestFindings:
    def test_with_data(self):
        eng = _engine()
        e = eng.design_experiment(name="test", experiment_type=ExperimentType.DNS_HIJACK)
        eng.observe_response(
            e.id,
            resilience_score=30.0,
            findings=["DNS not monitored"],
        )
        findings = eng.generate_findings()
        assert len(findings) == 1
        assert findings[0]["finding"] == "DNS not monitored"

    def test_empty(self):
        eng = _engine()
        assert eng.generate_findings() == []

    def test_sorted_by_score(self):
        eng = _engine()
        e1 = eng.design_experiment(name="a")
        e2 = eng.design_experiment(name="b")
        eng.observe_response(e1.id, resilience_score=80.0, findings=["ok"])
        eng.observe_response(e2.id, resilience_score=20.0, findings=["bad"])
        findings = eng.generate_findings()
        assert findings[0]["resilience_score"] == 20.0


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(resilience_threshold=80.0)
        e = eng.design_experiment(name="test")
        eng.observe_response(e.id, detected=False, resilience_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, ChaosReport)
        assert report.total_experiments == 1
        assert report.total_results == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert len(report.recommendations) > 0


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.design_experiment(name="a", target_service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_experiments"] == 1

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_experiments"] == 0

    def test_clear(self):
        eng = _engine()
        eng.design_experiment(name="test")
        eng.observe_response("e1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._experiments) == 0
        assert len(eng._results) == 0
