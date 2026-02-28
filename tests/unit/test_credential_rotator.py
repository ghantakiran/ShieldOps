"""Tests for shieldops.security.credential_rotator."""

from __future__ import annotations

from shieldops.security.credential_rotator import (
    CredentialRotationOrchestrator,
    CredentialRotatorReport,
    CredentialType,
    RotationPolicy,
    RotationRecord,
    RotationStatus,
    RotationStrategy,
)


def _engine(**kw) -> CredentialRotationOrchestrator:
    return CredentialRotationOrchestrator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CredentialType (5)
    def test_type_api_key(self):
        assert CredentialType.API_KEY == "api_key"

    def test_type_database_password(self):
        assert (
            CredentialType.DATABASE_PASSWORD == "database_password"  # noqa: S105
        )

    def test_type_tls_certificate(self):
        assert CredentialType.TLS_CERTIFICATE == "tls_certificate"

    def test_type_ssh_key(self):
        assert CredentialType.SSH_KEY == "ssh_key"

    def test_type_service_token(self):
        assert (
            CredentialType.SERVICE_TOKEN == "service_token"  # noqa: S105
        )

    # RotationStatus (5)
    def test_status_scheduled(self):
        assert RotationStatus.SCHEDULED == "scheduled"

    def test_status_in_progress(self):
        assert RotationStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert RotationStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert RotationStatus.FAILED == "failed"

    def test_status_rolled_back(self):
        assert RotationStatus.ROLLED_BACK == "rolled_back"

    # RotationStrategy (5)
    def test_strategy_zero_downtime(self):
        assert RotationStrategy.ZERO_DOWNTIME == "zero_downtime"

    def test_strategy_blue_green(self):
        assert RotationStrategy.BLUE_GREEN == "blue_green"

    def test_strategy_sequential(self):
        assert RotationStrategy.SEQUENTIAL == "sequential"

    def test_strategy_immediate(self):
        assert RotationStrategy.IMMEDIATE == "immediate"

    def test_strategy_gradual(self):
        assert RotationStrategy.GRADUAL == "gradual"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_rotation_record_defaults(self):
        r = RotationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.credential_type == CredentialType.API_KEY
        assert r.status == RotationStatus.SCHEDULED
        assert r.strategy == RotationStrategy.ZERO_DOWNTIME
        assert r.duration_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_rotation_policy_defaults(self):
        r = RotationPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.credential_type == CredentialType.API_KEY
        assert r.strategy == RotationStrategy.ZERO_DOWNTIME
        assert r.rotation_interval_days == 90
        assert r.max_age_days == 180.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = CredentialRotatorReport()
        assert r.total_rotations == 0
        assert r.total_policies == 0
        assert r.completion_rate_pct == 0.0
        assert r.by_credential_type == {}
        assert r.by_status == {}
        assert r.failed_rotation_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_rotation
# -------------------------------------------------------------------


class TestRecordRotation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rotation(
            "svc-a",
            credential_type=CredentialType.API_KEY,
            status=RotationStatus.COMPLETED,
        )
        assert r.service_name == "svc-a"
        assert r.credential_type == CredentialType.API_KEY

    def test_with_strategy(self):
        eng = _engine()
        r = eng.record_rotation(
            "svc-b",
            strategy=RotationStrategy.BLUE_GREEN,
        )
        assert r.strategy == RotationStrategy.BLUE_GREEN

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rotation(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_rotation
# -------------------------------------------------------------------


class TestGetRotation:
    def test_found(self):
        eng = _engine()
        r = eng.record_rotation("svc-a")
        assert eng.get_rotation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rotation("nonexistent") is None


# -------------------------------------------------------------------
# list_rotations
# -------------------------------------------------------------------


class TestListRotations:
    def test_list_all(self):
        eng = _engine()
        eng.record_rotation("svc-a")
        eng.record_rotation("svc-b")
        assert len(eng.list_rotations()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_rotation("svc-a")
        eng.record_rotation("svc-b")
        results = eng.list_rotations(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_rotation(
            "svc-a",
            credential_type=CredentialType.SSH_KEY,
        )
        eng.record_rotation(
            "svc-b",
            credential_type=CredentialType.API_KEY,
        )
        results = eng.list_rotations(
            credential_type=CredentialType.SSH_KEY,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "rotate-api-keys",
            credential_type=CredentialType.API_KEY,
            strategy=RotationStrategy.ZERO_DOWNTIME,
            rotation_interval_days=30,
            max_age_days=60.0,
        )
        assert p.policy_name == "rotate-api-keys"
        assert p.rotation_interval_days == 30

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_rotation_health
# -------------------------------------------------------------------


class TestAnalyzeRotationHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_rotation(
            "svc-a",
            status=RotationStatus.COMPLETED,
        )
        eng.record_rotation(
            "svc-a",
            status=RotationStatus.FAILED,
        )
        result = eng.analyze_rotation_health("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["rotation_count"] == 2
        assert result["completion_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_rotation_health("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_failed_rotations
# -------------------------------------------------------------------


class TestIdentifyFailedRotations:
    def test_with_failures(self):
        eng = _engine()
        eng.record_rotation(
            "svc-a",
            status=RotationStatus.FAILED,
        )
        eng.record_rotation(
            "svc-a",
            status=RotationStatus.FAILED,
        )
        eng.record_rotation(
            "svc-b",
            status=RotationStatus.COMPLETED,
        )
        results = eng.identify_failed_rotations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_rotations() == []


# -------------------------------------------------------------------
# rank_by_rotation_frequency
# -------------------------------------------------------------------


class TestRankByRotationFrequency:
    def test_with_data(self):
        eng = _engine()
        eng.record_rotation("svc-a")
        eng.record_rotation("svc-a")
        eng.record_rotation("svc-b")
        results = eng.rank_by_rotation_frequency()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["rotation_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_rotation_frequency() == []


# -------------------------------------------------------------------
# detect_stale_credentials
# -------------------------------------------------------------------


class TestDetectStaleCredentials:
    def test_with_stale(self):
        eng = _engine()
        for _ in range(5):
            eng.record_rotation(
                "svc-a",
                status=RotationStatus.FAILED,
            )
        eng.record_rotation(
            "svc-b",
            status=RotationStatus.COMPLETED,
        )
        results = eng.detect_stale_credentials()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["stale_detected"] is True

    def test_no_stale(self):
        eng = _engine()
        eng.record_rotation(
            "svc-a",
            status=RotationStatus.FAILED,
        )
        assert eng.detect_stale_credentials() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_rotation(
            "svc-a",
            status=RotationStatus.COMPLETED,
        )
        eng.record_rotation(
            "svc-b",
            status=RotationStatus.FAILED,
        )
        eng.record_rotation(
            "svc-b",
            status=RotationStatus.FAILED,
        )
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_rotations == 3
        assert report.total_policies == 1
        assert report.by_credential_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_rotations == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_rotation("svc-a")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_rotations"] == 0
        assert stats["total_policies"] == 0
        assert stats["credential_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rotation(
            "svc-a",
            credential_type=CredentialType.API_KEY,
        )
        eng.record_rotation(
            "svc-b",
            credential_type=CredentialType.SSH_KEY,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_rotations"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_services"] == 2
