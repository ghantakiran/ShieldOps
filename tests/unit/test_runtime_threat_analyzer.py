"""Tests for RuntimeThreatAnalyzer."""

from __future__ import annotations

from shieldops.security.runtime_threat_analyzer import (
    DetectionMethod,
    RuntimeContext,
    RuntimeThreatAnalyzer,
    ThreatBehavior,
)


def _engine(**kw) -> RuntimeThreatAnalyzer:
    return RuntimeThreatAnalyzer(**kw)


class TestEnums:
    def test_ctx_container(self):
        assert RuntimeContext.CONTAINER == "container"

    def test_ctx_serverless(self):
        assert RuntimeContext.SERVERLESS == "serverless"

    def test_ctx_vm(self):
        assert RuntimeContext.VM == "vm"

    def test_ctx_bare_metal(self):
        assert RuntimeContext.BARE_METAL == "bare_metal"

    def test_beh_injection(self):
        assert ThreatBehavior.PROCESS_INJECTION == "process_injection"

    def test_beh_escalation(self):
        assert ThreatBehavior.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_beh_lateral(self):
        assert ThreatBehavior.LATERAL_MOVEMENT == "lateral_movement"

    def test_beh_staging(self):
        assert ThreatBehavior.DATA_STAGING == "data_staging"

    def test_det_behavioral(self):
        assert DetectionMethod.BEHAVIORAL == "behavioral"

    def test_det_signature(self):
        assert DetectionMethod.SIGNATURE == "signature"

    def test_det_heuristic(self):
        assert DetectionMethod.HEURISTIC == "heuristic"

    def test_det_anomaly(self):
        assert DetectionMethod.ANOMALY == "anomaly"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            threat_id="t1",
            context=RuntimeContext.VM,
            severity_score=85.0,
        )
        assert r.threat_id == "t1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(threat_id=f"t-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            threat_id="t1",
            severity_score=95.0,
            evasion_attempts=2,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.threat_level == "critical"
        assert a.evasion_detected is True

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(threat_id="t1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(threat_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(threat_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeRuntimeBehavior:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            threat_id="t1",
            context=RuntimeContext.CONTAINER,
            severity_score=80.0,
        )
        result = eng.analyze_runtime_behavior()
        assert len(result) == 1
        assert result[0]["context"] == "container"

    def test_empty(self):
        assert _engine().analyze_runtime_behavior() == []


class TestDetectEvasionTechniques:
    def test_basic(self):
        eng = _engine()
        eng.add_record(threat_id="t1", evasion_attempts=3)
        result = eng.detect_evasion_techniques()
        assert len(result) == 1
        assert result[0]["evasion_attempts"] == 3

    def test_no_evasion(self):
        eng = _engine()
        eng.add_record(threat_id="t1", evasion_attempts=0)
        assert eng.detect_evasion_techniques() == []


class TestComputeThreatSeverity:
    def test_basic(self):
        eng = _engine()
        eng.add_record(threat_id="t1", severity_score=90.0)
        result = eng.compute_threat_severity()
        assert result["avg_severity"] == 90.0

    def test_empty(self):
        result = _engine().compute_threat_severity()
        assert result["avg_severity"] == 0.0
