"""Tests for shieldops.security.secrets_detector — SecretsSprawlDetector.

Covers SecretType, DetectionSource, and SecretSeverity enums, SecretFinding /
SecretRotationRecord / SecretsReport models, and all SecretsSprawlDetector
operations including recording, resolution, rotation, risk detection, sprawl
trend analysis, and report generation.
"""

from __future__ import annotations

from shieldops.security.secrets_detector import (
    DetectionSource,
    SecretFinding,
    SecretRotationRecord,
    SecretSeverity,
    SecretsReport,
    SecretsSprawlDetector,
    SecretType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> SecretsSprawlDetector:
    return SecretsSprawlDetector(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of SecretType, DetectionSource, and SecretSeverity."""

    # -- SecretType (6 members) -----------------------------------------------

    def test_secret_type_api_key(self):
        assert SecretType.API_KEY == "api_key"

    def test_secret_type_password(self):
        assert SecretType.PASSWORD == "password"  # noqa: S105

    def test_secret_type_token(self):
        assert SecretType.TOKEN == "token"  # noqa: S105

    def test_secret_type_private_key(self):
        assert SecretType.PRIVATE_KEY == "private_key"

    def test_secret_type_connection_string(self):
        assert SecretType.CONNECTION_STRING == "connection_string"

    def test_secret_type_certificate(self):
        assert SecretType.CERTIFICATE == "certificate"

    # -- DetectionSource (5 members) ------------------------------------------

    def test_source_git_repository(self):
        assert DetectionSource.GIT_REPOSITORY == "git_repository"

    def test_source_config_file(self):
        assert DetectionSource.CONFIG_FILE == "config_file"

    def test_source_environment_variable(self):
        assert DetectionSource.ENVIRONMENT_VARIABLE == "environment_variable"

    def test_source_container_image(self):
        assert DetectionSource.CONTAINER_IMAGE == "container_image"

    def test_source_ci_cd_pipeline(self):
        assert DetectionSource.CI_CD_PIPELINE == "ci_cd_pipeline"

    # -- SecretSeverity (5 members) -------------------------------------------

    def test_severity_info(self):
        assert SecretSeverity.INFO == "info"

    def test_severity_low(self):
        assert SecretSeverity.LOW == "low"

    def test_severity_medium(self):
        assert SecretSeverity.MEDIUM == "medium"

    def test_severity_high(self):
        assert SecretSeverity.HIGH == "high"

    def test_severity_critical(self):
        assert SecretSeverity.CRITICAL == "critical"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_secret_finding_defaults(self):
        f = SecretFinding()
        assert f.id
        assert f.secret_type == SecretType.API_KEY
        assert f.source == DetectionSource.GIT_REPOSITORY
        assert f.severity == SecretSeverity.MEDIUM
        assert f.service_name == ""
        assert f.file_path == ""
        assert f.description == ""
        assert f.is_resolved is False
        assert f.resolved_at == 0.0
        assert f.created_at > 0

    def test_secret_rotation_record_defaults(self):
        r = SecretRotationRecord()
        assert r.id
        assert r.finding_id == ""
        assert r.service_name == ""
        assert r.rotated_by == ""
        assert r.rotation_method == ""
        assert r.rotated_at > 0

    def test_secrets_report_defaults(self):
        r = SecretsReport()
        assert r.total_findings == 0
        assert r.open_findings == 0
        assert r.resolved_findings == 0
        assert r.high_severity_count == 0
        assert r.rotation_count == 0
        assert r.type_distribution == {}
        assert r.source_distribution == {}
        assert r.services_at_risk == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# RecordFinding
# ===========================================================================


class TestRecordFinding:
    """Test SecretsSprawlDetector.record_finding."""

    def test_basic_record(self):
        eng = _engine()
        f = eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.HIGH,
            service_name="auth-svc",
            file_path="config.yaml",
            description="Hardcoded token",
        )
        assert f.id
        assert f.secret_type == SecretType.TOKEN
        assert f.source == DetectionSource.GIT_REPOSITORY
        assert f.severity == SecretSeverity.HIGH
        assert f.service_name == "auth-svc"
        assert f.file_path == "config.yaml"
        assert f.description == "Hardcoded token"
        assert f.is_resolved is False

    def test_eviction_on_overflow(self):
        eng = _engine(max_findings=2)
        eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.LOW,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.PASSWORD,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.MEDIUM,
            service_name="svc-b",
        )
        f3 = eng.record_finding(
            secret_type=SecretType.CERTIFICATE,
            source=DetectionSource.CI_CD_PIPELINE,
            severity=SecretSeverity.HIGH,
            service_name="svc-c",
        )
        findings = eng.list_findings(limit=10)
        assert len(findings) == 2
        assert findings[-1].id == f3.id


# ===========================================================================
# GetFinding
# ===========================================================================


class TestGetFinding:
    """Test SecretsSprawlDetector.get_finding."""

    def test_found(self):
        eng = _engine()
        f = eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.MEDIUM,
            service_name="svc-x",
        )
        assert eng.get_finding(f.id) is f

    def test_not_found(self):
        eng = _engine()
        assert eng.get_finding("nonexistent-id") is None


# ===========================================================================
# ListFindings
# ===========================================================================


class TestListFindings:
    """Test SecretsSprawlDetector.list_findings with various filters."""

    def test_all_findings(self):
        eng = _engine()
        eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.LOW,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.HIGH,
            service_name="svc-b",
        )
        assert len(eng.list_findings()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.LOW,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.HIGH,
            service_name="svc-b",
        )
        results = eng.list_findings(secret_type=SecretType.TOKEN)
        assert len(results) == 1
        assert results[0].secret_type == SecretType.TOKEN

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.LOW,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.HIGH,
            service_name="svc-b",
        )
        results = eng.list_findings(severity=SecretSeverity.HIGH)
        assert len(results) == 1
        assert results[0].severity == SecretSeverity.HIGH

    def test_filter_by_resolved(self):
        eng = _engine()
        f1 = eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.LOW,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.HIGH,
            service_name="svc-b",
        )
        eng.resolve_finding(f1.id)
        resolved = eng.list_findings(is_resolved=True)
        assert len(resolved) == 1
        assert resolved[0].id == f1.id
        unresolved = eng.list_findings(is_resolved=False)
        assert len(unresolved) == 1


# ===========================================================================
# ResolveFinding
# ===========================================================================


class TestResolveFinding:
    """Test SecretsSprawlDetector.resolve_finding."""

    def test_resolve_success(self):
        eng = _engine()
        f = eng.record_finding(
            secret_type=SecretType.PASSWORD,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.CRITICAL,
            service_name="db-svc",
        )
        assert eng.resolve_finding(f.id) is True
        updated = eng.get_finding(f.id)
        assert updated is not None
        assert updated.is_resolved is True
        assert updated.resolved_at > 0

    def test_resolve_not_found(self):
        eng = _engine()
        assert eng.resolve_finding("no-such-id") is False


# ===========================================================================
# RecordRotation
# ===========================================================================


class TestRecordRotation:
    """Test SecretsSprawlDetector.record_rotation."""

    def test_basic_rotation(self):
        eng = _engine()
        f = eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.HIGH,
            service_name="auth-svc",
        )
        rot = eng.record_rotation(
            finding_id=f.id,
            service_name="auth-svc",
            rotated_by="ops-team",
            rotation_method="vault-rotate",
        )
        assert rot.id
        assert rot.finding_id == f.id
        assert rot.service_name == "auth-svc"
        assert rot.rotated_by == "ops-team"
        assert rot.rotation_method == "vault-rotate"
        assert rot.rotated_at > 0


# ===========================================================================
# DetectHighRiskServices
# ===========================================================================


class TestDetectHighRiskServices:
    """Test SecretsSprawlDetector.detect_high_risk_services."""

    def test_services_with_many_high_severity(self):
        eng = _engine(high_severity_threshold=3)
        for _ in range(4):
            eng.record_finding(
                secret_type=SecretType.API_KEY,
                source=DetectionSource.GIT_REPOSITORY,
                severity=SecretSeverity.CRITICAL,
                service_name="risky-svc",
            )
        # Add a low-severity finding to another service (should not appear)
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.LOW,
            service_name="safe-svc",
        )
        high_risk = eng.detect_high_risk_services()
        assert len(high_risk) == 1
        assert high_risk[0]["service_name"] == "risky-svc"
        assert high_risk[0]["high_critical_count"] == 4
        assert high_risk[0]["total_open"] == 4


# ===========================================================================
# AnalyzeSprawlTrends
# ===========================================================================


class TestAnalyzeSprawlTrends:
    """Test SecretsSprawlDetector.analyze_sprawl_trends."""

    def test_trends_over_time(self):
        eng = _engine()
        eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.LOW,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.MEDIUM,
            service_name="svc-b",
        )
        trends = eng.analyze_sprawl_trends()
        assert trends["total"] == 2
        assert len(trends["monthly_findings"]) >= 1
        assert len(trends["open_vs_resolved"]) >= 1
        first_month = trends["monthly_findings"][0]
        assert "month" in first_month
        assert "new_findings" in first_month


# ===========================================================================
# IdentifyUnrotatedSecrets
# ===========================================================================


class TestIdentifyUnrotatedSecrets:
    """Test SecretsSprawlDetector.identify_unrotated_secrets."""

    def test_unrotated_vs_rotated(self):
        eng = _engine()
        f1 = eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.HIGH,
            service_name="svc-a",
        )
        f2 = eng.record_finding(
            secret_type=SecretType.PASSWORD,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.CRITICAL,
            service_name="svc-b",
        )
        # Rotate f1 only
        eng.record_rotation(
            finding_id=f1.id,
            service_name="svc-a",
            rotated_by="ops",
            rotation_method="auto",
        )
        unrotated = eng.identify_unrotated_secrets()
        assert len(unrotated) == 1
        assert unrotated[0].id == f2.id


# ===========================================================================
# GenerateSecretsReport
# ===========================================================================


class TestGenerateSecretsReport:
    """Test SecretsSprawlDetector.generate_secrets_report."""

    def test_basic_report(self):
        eng = _engine(high_severity_threshold=100)
        eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.HIGH,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.LOW,
            service_name="svc-b",
        )
        eng.resolve_finding(eng.list_findings()[1].id)

        report = eng.generate_secrets_report()
        assert isinstance(report, SecretsReport)
        assert report.total_findings == 2
        assert report.open_findings == 1
        assert report.resolved_findings == 1
        assert report.high_severity_count >= 1
        assert report.generated_at > 0
        assert len(report.type_distribution) >= 1
        assert len(report.source_distribution) >= 1
        assert len(report.recommendations) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test SecretsSprawlDetector.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        f = eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.MEDIUM,
            service_name="svc-a",
        )
        eng.record_rotation(
            finding_id=f.id,
            service_name="svc-a",
            rotated_by="ops",
            rotation_method="manual",
        )
        eng.clear_data()
        assert len(eng.list_findings()) == 0
        stats = eng.get_stats()
        assert stats["total_findings"] == 0
        assert stats["total_rotations"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test SecretsSprawlDetector.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_findings"] == 0
        assert stats["total_rotations"] == 0
        assert stats["open_findings"] == 0
        assert stats["unique_services"] == 0
        assert stats["severity_distribution"] == {}
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        f = eng.record_finding(
            secret_type=SecretType.API_KEY,
            source=DetectionSource.GIT_REPOSITORY,
            severity=SecretSeverity.HIGH,
            service_name="svc-a",
        )
        eng.record_finding(
            secret_type=SecretType.TOKEN,
            source=DetectionSource.CONFIG_FILE,
            severity=SecretSeverity.LOW,
            service_name="svc-b",
        )
        eng.record_rotation(
            finding_id=f.id,
            service_name="svc-a",
            rotated_by="ops",
            rotation_method="auto",
        )
        stats = eng.get_stats()
        assert stats["total_findings"] == 2
        assert stats["total_rotations"] == 1
        assert stats["open_findings"] == 2
        assert stats["unique_services"] == 2
        assert stats["severity_distribution"]["high"] == 1
        assert stats["severity_distribution"]["low"] == 1
        assert stats["source_distribution"]["git_repository"] == 1
        assert stats["source_distribution"]["config_file"] == 1
