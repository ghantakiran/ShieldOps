"""Tests for shieldops.observability.backup_verification — BackupVerificationEngine."""

from __future__ import annotations

import time

from shieldops.observability.backup_verification import (
    BackupRecord,
    BackupType,
    BackupVerificationEngine,
    RecoveryReadiness,
    RecoveryReport,
    VerificationResult,
    VerificationStatus,
)


def _engine(**kw) -> BackupVerificationEngine:
    return BackupVerificationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # BackupType (5 values)

    def test_backup_type_full(self):
        assert BackupType.FULL == "full"

    def test_backup_type_incremental(self):
        assert BackupType.INCREMENTAL == "incremental"

    def test_backup_type_differential(self):
        assert BackupType.DIFFERENTIAL == "differential"

    def test_backup_type_snapshot(self):
        assert BackupType.SNAPSHOT == "snapshot"

    def test_backup_type_log(self):
        assert BackupType.LOG == "log"

    # VerificationStatus (5 values)

    def test_verification_status_pending(self):
        assert VerificationStatus.PENDING == "pending"

    def test_verification_status_verifying(self):
        assert VerificationStatus.VERIFYING == "verifying"

    def test_verification_status_verified(self):
        assert VerificationStatus.VERIFIED == "verified"

    def test_verification_status_failed(self):
        assert VerificationStatus.FAILED == "failed"

    def test_verification_status_stale(self):
        assert VerificationStatus.STALE == "stale"

    # RecoveryReadiness (4 values)

    def test_recovery_readiness_ready(self):
        assert RecoveryReadiness.READY == "ready"

    def test_recovery_readiness_degraded(self):
        assert RecoveryReadiness.DEGRADED == "degraded"

    def test_recovery_readiness_not_ready(self):
        assert RecoveryReadiness.NOT_READY == "not_ready"

    def test_recovery_readiness_unknown(self):
        assert RecoveryReadiness.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_backup_record_defaults(self):
        record = BackupRecord(service="db-primary")
        assert record.id
        assert record.service == "db-primary"
        assert record.backup_type == BackupType.FULL
        assert record.size_bytes == 0
        assert record.location == ""
        assert record.status == VerificationStatus.PENDING
        assert record.checksum == ""
        assert record.created_at > 0
        assert record.verified_at is None

    def test_verification_result_defaults(self):
        result = VerificationResult(backup_id="b-1")
        assert result.id
        assert result.backup_id == "b-1"
        assert result.passed is False
        assert result.integrity_check is False
        assert result.restore_test is False
        assert result.details == ""
        assert result.verified_at > 0

    def test_recovery_report_defaults(self):
        report = RecoveryReport(service="db-primary")
        assert report.service == "db-primary"
        assert report.total_backups == 0
        assert report.verified_backups == 0
        assert report.stale_backups == 0
        assert report.readiness == RecoveryReadiness.UNKNOWN
        assert report.last_verified_at is None


# ---------------------------------------------------------------------------
# register_backup
# ---------------------------------------------------------------------------


class TestRegisterBackup:
    def test_basic_register(self):
        eng = _engine()
        record = eng.register_backup("db-primary")
        assert record.service == "db-primary"
        assert record.backup_type == BackupType.FULL
        assert record.status == VerificationStatus.PENDING
        assert eng.get_backup(record.id) is not None

    def test_register_assigns_unique_ids(self):
        eng = _engine()
        b1 = eng.register_backup("svc-a")
        b2 = eng.register_backup("svc-b")
        assert b1.id != b2.id

    def test_register_with_extra_fields(self):
        eng = _engine()
        record = eng.register_backup(
            "db-primary",
            backup_type=BackupType.INCREMENTAL,
            size_bytes=1024000,
            location="s3://backups/db-primary",
            checksum="abc123",
        )
        assert record.backup_type == BackupType.INCREMENTAL
        assert record.size_bytes == 1024000
        assert record.location == "s3://backups/db-primary"
        assert record.checksum == "abc123"

    def test_evicts_at_max_backups(self):
        eng = _engine(max_backups=3)
        ids = []
        for i in range(4):
            record = eng.register_backup(f"svc-{i}")
            ids.append(record.id)
        assert eng.get_backup(ids[0]) is None
        assert eng.get_backup(ids[3]) is not None
        assert len(eng.list_backups()) == 3


# ---------------------------------------------------------------------------
# verify_backup
# ---------------------------------------------------------------------------


class TestVerifyBackup:
    def test_verify_pass(self):
        eng = _engine()
        record = eng.register_backup("db-primary", size_bytes=5000)
        result = eng.verify_backup(record.id)
        assert result is not None
        assert result.passed is True
        assert result.integrity_check is True
        assert result.restore_test is False
        assert result.details == "Verification passed"
        updated = eng.get_backup(record.id)
        assert updated.status == VerificationStatus.VERIFIED
        assert updated.verified_at is not None

    def test_verify_fail(self):
        eng = _engine()
        record = eng.register_backup("db-primary")
        # integrity_check=False makes passed=False
        result = eng.verify_backup(record.id, integrity_check=False)
        assert result is not None
        assert result.passed is False
        assert result.details == "Verification failed"
        updated = eng.get_backup(record.id)
        assert updated.status == VerificationStatus.FAILED

    def test_verify_not_found(self):
        eng = _engine()
        result = eng.verify_backup("nonexistent")
        assert result is None

    def test_verify_with_restore_test(self):
        eng = _engine()
        # size_bytes > 0 means restore_test passes
        record = eng.register_backup("db-primary", size_bytes=5000)
        result = eng.verify_backup(record.id, restore_test=True)
        assert result is not None
        assert result.passed is True
        assert result.restore_test is True


# ---------------------------------------------------------------------------
# get_backup
# ---------------------------------------------------------------------------


class TestGetBackup:
    def test_found(self):
        eng = _engine()
        record = eng.register_backup("db-primary")
        result = eng.get_backup(record.id)
        assert result is not None
        assert result.id == record.id

    def test_not_found(self):
        eng = _engine()
        assert eng.get_backup("nonexistent") is None


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------


class TestListBackups:
    def test_list_all(self):
        eng = _engine()
        eng.register_backup("svc-a")
        eng.register_backup("svc-b")
        eng.register_backup("svc-c")
        assert len(eng.list_backups()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_backup("svc-a")
        eng.register_backup("svc-b")
        eng.register_backup("svc-a")
        results = eng.list_backups(service="svc-a")
        assert len(results) == 2
        assert all(b.service == "svc-a" for b in results)

    def test_filter_by_type(self):
        eng = _engine()
        eng.register_backup("svc-a", backup_type=BackupType.FULL)
        eng.register_backup("svc-b", backup_type=BackupType.INCREMENTAL)
        eng.register_backup("svc-c", backup_type=BackupType.FULL)
        results = eng.list_backups(backup_type=BackupType.FULL)
        assert len(results) == 2
        assert all(b.backup_type == BackupType.FULL for b in results)

    def test_filter_by_status(self):
        eng = _engine()
        b1 = eng.register_backup("svc-a", size_bytes=100)
        eng.register_backup("svc-b")
        eng.verify_backup(b1.id)
        results = eng.list_backups(status=VerificationStatus.VERIFIED)
        assert len(results) == 1
        assert results[0].status == VerificationStatus.VERIFIED


# ---------------------------------------------------------------------------
# get_stale_backups
# ---------------------------------------------------------------------------


class TestGetStaleBackups:
    def test_basic_stale_detection(self):
        eng = _engine(stale_hours=0.0001)  # ~0.36 seconds threshold
        record = eng.register_backup("db-primary")
        # Force created_at into the past
        record.created_at = time.time() - 3600
        stale = eng.get_stale_backups()
        assert len(stale) == 1
        assert stale[0].id == record.id
        assert stale[0].status == VerificationStatus.STALE

    def test_none_stale(self):
        eng = _engine(stale_hours=9999)
        eng.register_backup("db-primary")
        stale = eng.get_stale_backups()
        assert stale == []


# ---------------------------------------------------------------------------
# get_recovery_report
# ---------------------------------------------------------------------------


class TestGetRecoveryReport:
    def test_ready(self):
        eng = _engine()
        # 5 backups, verify 4 (80%) -> READY
        records = []
        for _ in range(5):
            records.append(eng.register_backup("db-primary", size_bytes=100))
        for r in records[:4]:
            eng.verify_backup(r.id)
        report = eng.get_recovery_report("db-primary")
        assert report.readiness == RecoveryReadiness.READY
        assert report.total_backups == 5
        assert report.verified_backups == 4

    def test_degraded(self):
        eng = _engine()
        # 4 backups, verify 2 (50%) -> DEGRADED
        records = []
        for _ in range(4):
            records.append(eng.register_backup("db-primary", size_bytes=100))
        for r in records[:2]:
            eng.verify_backup(r.id)
        report = eng.get_recovery_report("db-primary")
        assert report.readiness == RecoveryReadiness.DEGRADED
        assert report.verified_backups == 2

    def test_not_ready(self):
        eng = _engine()
        # 5 backups, verify 1 (20%) -> NOT_READY
        records = []
        for _ in range(5):
            records.append(eng.register_backup("db-primary", size_bytes=100))
        eng.verify_backup(records[0].id)
        report = eng.get_recovery_report("db-primary")
        assert report.readiness == RecoveryReadiness.NOT_READY
        assert report.verified_backups == 1

    def test_unknown_no_backups(self):
        eng = _engine()
        report = eng.get_recovery_report("no-such-service")
        assert report.readiness == RecoveryReadiness.UNKNOWN
        assert report.total_backups == 0
        assert report.last_verified_at is None


# ---------------------------------------------------------------------------
# get_recovery_readiness_all
# ---------------------------------------------------------------------------


class TestGetRecoveryReadinessAll:
    def test_basic_readiness_all(self):
        eng = _engine()
        eng.register_backup("svc-a", size_bytes=100)
        eng.register_backup("svc-b", size_bytes=100)
        reports = eng.get_recovery_readiness_all()
        assert len(reports) == 2
        services = {r.service for r in reports}
        assert services == {"svc-a", "svc-b"}


# ---------------------------------------------------------------------------
# list_verifications
# ---------------------------------------------------------------------------


class TestListVerifications:
    def test_list_all_verifications(self):
        eng = _engine()
        b1 = eng.register_backup("svc-a", size_bytes=100)
        b2 = eng.register_backup("svc-b", size_bytes=100)
        eng.verify_backup(b1.id)
        eng.verify_backup(b2.id)
        results = eng.list_verifications()
        assert len(results) == 2

    def test_filter_by_backup_id(self):
        eng = _engine()
        b1 = eng.register_backup("svc-a", size_bytes=100)
        b2 = eng.register_backup("svc-b", size_bytes=100)
        eng.verify_backup(b1.id)
        eng.verify_backup(b2.id)
        results = eng.list_verifications(backup_id=b1.id)
        assert len(results) == 1
        assert results[0].backup_id == b1.id


# ---------------------------------------------------------------------------
# delete_backup
# ---------------------------------------------------------------------------


class TestDeleteBackup:
    def test_delete_success(self):
        eng = _engine()
        record = eng.register_backup("db-primary")
        assert eng.delete_backup(record.id) is True
        assert eng.get_backup(record.id) is None

    def test_delete_not_found(self):
        eng = _engine()
        assert eng.delete_backup("nonexistent") is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_backups"] == 0
        assert stats["total_verifications"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["type_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        b1 = eng.register_backup("svc-a", backup_type=BackupType.FULL, size_bytes=1000)
        eng.register_backup("svc-b", backup_type=BackupType.INCREMENTAL, size_bytes=500)
        eng.verify_backup(b1.id)

        stats = eng.get_stats()
        assert stats["total_backups"] == 2
        assert stats["total_verifications"] == 1
        assert stats["total_size_bytes"] == 1500
        assert stats["type_distribution"][BackupType.FULL] == 1
        assert stats["type_distribution"][BackupType.INCREMENTAL] == 1
        assert stats["status_distribution"][VerificationStatus.VERIFIED] == 1
        assert stats["status_distribution"][VerificationStatus.PENDING] == 1
