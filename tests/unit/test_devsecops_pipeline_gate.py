"""Tests for DevSecOpsPipelineGate."""

from __future__ import annotations

from shieldops.security.devsecops_pipeline_gate import (
    ArtifactType,
    DevSecOpsPipelineGate,
    GateDecision,
    PipelineSecurityReport,
    SBOMEntry,
    ScanResult,
    ScanType,
    VulnSeverity,
)


def _engine(**kw) -> DevSecOpsPipelineGate:
    return DevSecOpsPipelineGate(**kw)


# --- Enum tests ---


class TestEnums:
    def test_gate_pass(self):
        assert GateDecision.PASS == "pass"  # noqa: S105

    def test_gate_fail(self):
        assert GateDecision.FAIL == "fail"

    def test_gate_warn(self):
        assert GateDecision.WARN == "warn"

    def test_gate_skip(self):
        assert GateDecision.SKIP == "skip"

    def test_scan_sast(self):
        assert ScanType.SAST == "sast"

    def test_scan_dast(self):
        assert ScanType.DAST == "dast"

    def test_scan_sca(self):
        assert ScanType.SCA == "sca"

    def test_scan_container(self):
        assert ScanType.CONTAINER == "container"

    def test_scan_secret(self):
        assert ScanType.SECRET == "secret"  # noqa: S105

    def test_artifact_docker(self):
        assert ArtifactType.DOCKER_IMAGE == "docker_image"

    def test_artifact_jar(self):
        assert ArtifactType.JAR == "jar"

    def test_vuln_low(self):
        assert VulnSeverity.LOW == "low"

    def test_vuln_critical(self):
        assert VulnSeverity.CRITICAL == "critical"


# --- Model tests ---


class TestModels:
    def test_scan_defaults(self):
        s = ScanResult()
        assert s.id
        assert s.decision == GateDecision.PASS
        assert s.vuln_count == 0

    def test_sbom_defaults(self):
        s = SBOMEntry()
        assert s.id
        assert s.vulnerability_ids == []

    def test_report_defaults(self):
        r = PipelineSecurityReport()
        assert r.total_scans == 0
        assert r.pass_rate == 0.0


# --- scan_artifact ---


class TestScanArtifact:
    def test_pass(self):
        eng = _engine(score_threshold=50.0, max_critical=0, max_high=5)
        s = eng.scan_artifact(
            artifact_name="app:latest",
            score=80.0,
            critical_count=0,
            high_count=2,
        )
        assert s.decision == GateDecision.PASS

    def test_fail_critical(self):
        eng = _engine(max_critical=0)
        s = eng.scan_artifact(
            artifact_name="app:latest",
            score=80.0,
            critical_count=1,
        )
        assert s.decision == GateDecision.FAIL

    def test_warn_high(self):
        eng = _engine(max_critical=5, max_high=2)
        s = eng.scan_artifact(
            artifact_name="app:latest",
            score=80.0,
            critical_count=0,
            high_count=5,
        )
        assert s.decision == GateDecision.WARN

    def test_warn_low_score(self):
        eng = _engine(score_threshold=80.0, max_critical=5, max_high=10)
        s = eng.scan_artifact(artifact_name="app:latest", score=40.0)
        assert s.decision == GateDecision.WARN

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.scan_artifact(artifact_name=f"a-{i}")
        assert len(eng._scans) == 3


# --- evaluate_gate ---


class TestEvaluateGate:
    def test_found(self):
        eng = _engine()
        s = eng.scan_artifact(artifact_name="app:latest", score=80.0)
        result = eng.evaluate_gate(s.id)
        assert result["decision"] == "pass"

    def test_not_found(self):
        eng = _engine()
        result = eng.evaluate_gate("unknown")
        assert result["error"] == "not_found"


# --- enforce_policy ---


class TestEnforcePolicy:
    def test_block(self):
        eng = _engine()
        eng.scan_artifact(artifact_name="app", critical_count=5)
        result = eng.enforce_policy("app", max_critical=0)
        assert result["blocked"] == 1

    def test_no_block(self):
        eng = _engine()
        eng.scan_artifact(artifact_name="app", critical_count=0)
        result = eng.enforce_policy("app", max_critical=5)
        assert result["blocked"] == 0


# --- generate_sbom ---


class TestGenerateSBOM:
    def test_basic(self):
        eng = _engine()
        entry = eng.generate_sbom(
            artifact_name="app",
            package_name="requests",
            version="2.31.0",
            license_name="Apache-2.0",
            vulnerability_ids=["CVE-2023-001"],
        )
        assert entry.package_name == "requests"
        assert len(entry.vulnerability_ids) == 1

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.generate_sbom(artifact_name="a", package_name=f"p{i}")
        assert len(eng._sbom) == 2


# --- get_pipeline_security_score ---


class TestPipelineScore:
    def test_with_data(self):
        eng = _engine(score_threshold=50.0, max_critical=5, max_high=10)
        eng.scan_artifact(artifact_name="a", score=80.0)
        eng.scan_artifact(artifact_name="b", score=60.0)
        result = eng.get_pipeline_security_score()
        assert result["total"] == 2
        assert result["avg_score"] == 70.0
        assert result["pass_rate"] == 100.0

    def test_empty(self):
        eng = _engine()
        result = eng.get_pipeline_security_score()
        assert result["total"] == 0


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.scan_artifact(artifact_name="app", score=40.0, critical_count=1)
        report = eng.generate_report()
        assert isinstance(report, PipelineSecurityReport)
        assert report.total_scans == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert len(report.recommendations) > 0


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.scan_artifact(artifact_name="a", service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_scans"] == 1

    def test_clear(self):
        eng = _engine()
        eng.scan_artifact(artifact_name="a")
        eng.generate_sbom(artifact_name="a", package_name="p")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._scans) == 0
        assert len(eng._sbom) == 0
