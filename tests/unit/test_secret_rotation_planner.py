"""Tests for shieldops.security.secret_rotation_planner — SecretRotationPlanner."""

from __future__ import annotations

from shieldops.security.secret_rotation_planner import (
    RotationRecord,
    RotationRisk,
    RotationSchedule,
    RotationStatus,
    SecretRotationPlanner,
    SecretRotationReport,
    SecretType,
)


def _engine(**kw) -> SecretRotationPlanner:
    return SecretRotationPlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_secret_type_api_key(self):
        assert SecretType.API_KEY == "api_key"

    def test_secret_type_database_credential(self):
        assert SecretType.DATABASE_CREDENTIAL == "database_credential"

    def test_secret_type_certificate(self):
        assert SecretType.CERTIFICATE == "certificate"

    def test_secret_type_ssh_key(self):
        assert SecretType.SSH_KEY == "ssh_key"

    def test_secret_type_encryption_key(self):
        assert SecretType.ENCRYPTION_KEY == "encryption_key"

    def test_status_on_schedule(self):
        assert RotationStatus.ON_SCHEDULE == "on_schedule"

    def test_status_due_soon(self):
        assert RotationStatus.DUE_SOON == "due_soon"

    def test_status_overdue(self):
        assert RotationStatus.OVERDUE == "overdue"

    def test_status_rotating(self):
        assert RotationStatus.ROTATING == "rotating"

    def test_status_completed(self):
        assert RotationStatus.COMPLETED == "completed"

    def test_risk_critical(self):
        assert RotationRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert RotationRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert RotationRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert RotationRisk.LOW == "low"

    def test_risk_minimal(self):
        assert RotationRisk.MINIMAL == "minimal"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rotation_record_defaults(self):
        r = RotationRecord()
        assert r.id
        assert r.secret_id == ""
        assert r.secret_type == SecretType.API_KEY
        assert r.rotation_status == RotationStatus.ON_SCHEDULE
        assert r.rotation_risk == RotationRisk.LOW
        assert r.days_until_rotation == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_rotation_schedule_defaults(self):
        s = RotationSchedule()
        assert s.id
        assert s.secret_id == ""
        assert s.secret_type == SecretType.API_KEY
        assert s.schedule_days == 0.0
        assert s.threshold == 0.0
        assert s.breached is False
        assert s.description == ""
        assert s.created_at > 0

    def test_secret_rotation_report_defaults(self):
        r = SecretRotationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_schedules == 0
        assert r.overdue_count == 0
        assert r.avg_days_until_rotation == 0.0
        assert r.by_secret_type == {}
        assert r.by_status == {}
        assert r.by_risk == {}
        assert r.top_overdue == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_rotation
# ---------------------------------------------------------------------------


class TestRecordRotation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_rotation(
            secret_id="SEC-001",
            secret_type=SecretType.DATABASE_CREDENTIAL,
            rotation_status=RotationStatus.DUE_SOON,
            rotation_risk=RotationRisk.MODERATE,
            days_until_rotation=7.0,
            service="api-gateway",
            team="sre",
        )
        assert r.secret_id == "SEC-001"  # noqa: S105
        assert r.secret_type == SecretType.DATABASE_CREDENTIAL
        assert r.rotation_status == RotationStatus.DUE_SOON
        assert r.rotation_risk == RotationRisk.MODERATE
        assert r.days_until_rotation == 7.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rotation(secret_id=f"SEC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_rotation
# ---------------------------------------------------------------------------


class TestGetRotation:
    def test_found(self):
        eng = _engine()
        r = eng.record_rotation(
            secret_id="SEC-001",
            rotation_status=RotationStatus.OVERDUE,
        )
        result = eng.get_rotation(r.id)
        assert result is not None
        assert result.rotation_status == RotationStatus.OVERDUE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rotation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_rotations
# ---------------------------------------------------------------------------


class TestListRotations:
    def test_list_all(self):
        eng = _engine()
        eng.record_rotation(secret_id="SEC-001")
        eng.record_rotation(secret_id="SEC-002")
        assert len(eng.list_rotations()) == 2

    def test_filter_by_secret_type(self):
        eng = _engine()
        eng.record_rotation(
            secret_id="SEC-001",
            secret_type=SecretType.CERTIFICATE,
        )
        eng.record_rotation(
            secret_id="SEC-002",
            secret_type=SecretType.API_KEY,
        )
        results = eng.list_rotations(secret_type=SecretType.CERTIFICATE)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_rotation(
            secret_id="SEC-001",
            rotation_status=RotationStatus.OVERDUE,
        )
        eng.record_rotation(
            secret_id="SEC-002",
            rotation_status=RotationStatus.ON_SCHEDULE,
        )
        results = eng.list_rotations(status=RotationStatus.OVERDUE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_rotation(secret_id="SEC-001", service="api")
        eng.record_rotation(secret_id="SEC-002", service="web")
        results = eng.list_rotations(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_rotation(secret_id="SEC-001", team="sre")
        eng.record_rotation(secret_id="SEC-002", team="platform")
        results = eng.list_rotations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rotation(secret_id=f"SEC-{i}")
        assert len(eng.list_rotations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_schedule
# ---------------------------------------------------------------------------


class TestAddSchedule:
    def test_basic(self):
        eng = _engine()
        s = eng.add_schedule(
            secret_id="SEC-001",
            secret_type=SecretType.SSH_KEY,
            schedule_days=90.0,
            threshold=30.0,
            breached=False,
            description="Rotation within schedule",
        )
        assert s.secret_id == "SEC-001"  # noqa: S105
        assert s.secret_type == SecretType.SSH_KEY
        assert s.schedule_days == 90.0
        assert s.threshold == 30.0
        assert s.breached is False
        assert s.description == "Rotation within schedule"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_schedule(secret_id=f"SEC-{i}")
        assert len(eng._schedules) == 2


# ---------------------------------------------------------------------------
# analyze_rotation_compliance
# ---------------------------------------------------------------------------


class TestAnalyzeRotationCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_rotation(
            secret_id="SEC-001",
            secret_type=SecretType.API_KEY,
            days_until_rotation=30.0,
        )
        eng.record_rotation(
            secret_id="SEC-002",
            secret_type=SecretType.API_KEY,
            days_until_rotation=60.0,
        )
        result = eng.analyze_rotation_compliance()
        assert "api_key" in result
        assert result["api_key"]["count"] == 2
        assert result["api_key"]["avg_days_until_rotation"] == 45.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_rotation_compliance() == {}


# ---------------------------------------------------------------------------
# identify_overdue_rotations
# ---------------------------------------------------------------------------


class TestIdentifyOverdueRotations:
    def test_detects_overdue(self):
        eng = _engine()
        eng.record_rotation(
            secret_id="SEC-001",
            rotation_status=RotationStatus.OVERDUE,
        )
        eng.record_rotation(
            secret_id="SEC-002",
            rotation_status=RotationStatus.ON_SCHEDULE,
        )
        results = eng.identify_overdue_rotations()
        assert len(results) == 1
        assert results[0]["secret_id"] == "SEC-001"  # noqa: S105

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_rotations() == []


# ---------------------------------------------------------------------------
# rank_by_urgency
# ---------------------------------------------------------------------------


class TestRankByUrgency:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_rotation(secret_id="SEC-001", service="api", days_until_rotation=90.0)
        eng.record_rotation(secret_id="SEC-002", service="api", days_until_rotation=80.0)
        eng.record_rotation(secret_id="SEC-003", service="web", days_until_rotation=50.0)
        results = eng.rank_by_urgency()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_days_until_rotation"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_urgency() == []


# ---------------------------------------------------------------------------
# detect_rotation_trends
# ---------------------------------------------------------------------------


class TestDetectRotationTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_schedule(secret_id="SEC-001", schedule_days=val)
        result = eng.detect_rotation_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_schedule(secret_id="SEC-001", schedule_days=val)
        result = eng.detect_rotation_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_rotation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_rotation(
            secret_id="SEC-001",
            secret_type=SecretType.DATABASE_CREDENTIAL,
            rotation_status=RotationStatus.OVERDUE,
            days_until_rotation=-5.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SecretRotationReport)
        assert report.total_records == 1
        assert report.overdue_count == 1
        assert report.avg_days_until_rotation == -5.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_rotation(secret_id="SEC-001")
        eng.add_schedule(secret_id="SEC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._schedules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_schedules"] == 0
        assert stats["secret_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_rotation(
            secret_id="SEC-001",
            secret_type=SecretType.CERTIFICATE,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_secrets"] == 1
        assert "certificate" in stats["secret_type_distribution"]
