"""Backup Verification Engine — validate backup integrity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BackupType(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    LOG = "log"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"
    STALE = "stale"


class RecoveryReadiness(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


# --- Models ---


class BackupRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    backup_type: BackupType = BackupType.FULL
    size_bytes: int = 0
    location: str = ""
    status: VerificationStatus = VerificationStatus.PENDING
    checksum: str = ""
    created_at: float = Field(default_factory=time.time)
    verified_at: float | None = None


class VerificationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backup_id: str
    passed: bool = False
    integrity_check: bool = False
    restore_test: bool = False
    details: str = ""
    verified_at: float = Field(default_factory=time.time)


class RecoveryReport(BaseModel):
    service: str
    total_backups: int = 0
    verified_backups: int = 0
    stale_backups: int = 0
    readiness: RecoveryReadiness = RecoveryReadiness.UNKNOWN
    last_verified_at: float | None = None


# --- Engine ---


class BackupVerificationEngine:
    """Validates backup integrity, tests recovery readiness, detects stale backups."""

    def __init__(
        self,
        max_backups: int = 10000,
        stale_hours: float = 48.0,
    ) -> None:
        self._max_backups = max_backups
        self._stale_hours = stale_hours
        self._backups: dict[str, BackupRecord] = {}
        self._verifications: list[VerificationResult] = []
        logger.info(
            "backup_verification.initialized",
            max_backups=max_backups,
            stale_hours=stale_hours,
        )

    def register_backup(
        self,
        service: str,
        backup_type: BackupType = BackupType.FULL,
        size_bytes: int = 0,
        location: str = "",
        **kw: Any,
    ) -> BackupRecord:
        """Register a new backup."""
        record = BackupRecord(
            service=service,
            backup_type=backup_type,
            size_bytes=size_bytes,
            location=location,
            **kw,
        )
        self._backups[record.id] = record
        if len(self._backups) > self._max_backups:
            oldest = next(iter(self._backups))
            del self._backups[oldest]
        logger.info(
            "backup_verification.backup_registered",
            backup_id=record.id,
            service=service,
            backup_type=backup_type,
        )
        return record

    def verify_backup(
        self,
        backup_id: str,
        integrity_check: bool = True,
        restore_test: bool = False,
    ) -> VerificationResult | None:
        """Verify a backup's integrity."""
        backup = self._backups.get(backup_id)
        if backup is None:
            return None
        passed = integrity_check and (not restore_test or backup.size_bytes > 0)
        result = VerificationResult(
            backup_id=backup_id,
            passed=passed,
            integrity_check=integrity_check,
            restore_test=restore_test,
            details="Verification passed" if passed else "Verification failed",
        )
        self._verifications.append(result)
        backup.status = VerificationStatus.VERIFIED if passed else VerificationStatus.FAILED
        backup.verified_at = time.time()
        logger.info(
            "backup_verification.backup_verified",
            backup_id=backup_id,
            passed=passed,
        )
        return result

    def get_backup(self, backup_id: str) -> BackupRecord | None:
        """Retrieve a backup by ID."""
        return self._backups.get(backup_id)

    def list_backups(
        self,
        service: str | None = None,
        backup_type: BackupType | None = None,
        status: VerificationStatus | None = None,
    ) -> list[BackupRecord]:
        """List backups with optional filters."""
        results = list(self._backups.values())
        if service is not None:
            results = [b for b in results if b.service == service]
        if backup_type is not None:
            results = [b for b in results if b.backup_type == backup_type]
        if status is not None:
            results = [b for b in results if b.status == status]
        return results

    def get_stale_backups(self) -> list[BackupRecord]:
        """Get backups that haven't been verified within stale_hours."""
        cutoff = time.time() - (self._stale_hours * 3600)
        stale: list[BackupRecord] = []
        for backup in self._backups.values():
            is_stale = (backup.verified_at is None and backup.created_at < cutoff) or (
                backup.verified_at is not None and backup.verified_at < cutoff
            )
            if is_stale:
                backup.status = VerificationStatus.STALE
                stale.append(backup)
        return stale

    def get_recovery_report(self, service: str) -> RecoveryReport:
        """Get recovery readiness report for a service."""
        backups = [b for b in self._backups.values() if b.service == service]
        total = len(backups)
        verified = sum(1 for b in backups if b.status == VerificationStatus.VERIFIED)
        stale = sum(1 for b in backups if b.status == VerificationStatus.STALE)
        verified_times = [b.verified_at for b in backups if b.verified_at is not None]
        last_verified = max(verified_times) if verified_times else None
        if total == 0:
            readiness = RecoveryReadiness.UNKNOWN
        elif verified / total >= 0.8:
            readiness = RecoveryReadiness.READY
        elif verified / total >= 0.5:
            readiness = RecoveryReadiness.DEGRADED
        else:
            readiness = RecoveryReadiness.NOT_READY
        return RecoveryReport(
            service=service,
            total_backups=total,
            verified_backups=verified,
            stale_backups=stale,
            readiness=readiness,
            last_verified_at=last_verified,
        )

    def get_recovery_readiness_all(self) -> list[RecoveryReport]:
        """Get recovery readiness for all services."""
        services = sorted({b.service for b in self._backups.values()})
        return [self.get_recovery_report(s) for s in services]

    def list_verifications(
        self,
        backup_id: str | None = None,
        limit: int = 100,
    ) -> list[VerificationResult]:
        """List verifications with optional filter."""
        results = list(self._verifications)
        if backup_id is not None:
            results = [v for v in results if v.backup_id == backup_id]
        return results[-limit:]

    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup record."""
        if backup_id in self._backups:
            del self._backups[backup_id]
            logger.info("backup_verification.backup_deleted", backup_id=backup_id)
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        type_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for b in self._backups.values():
            type_counts[b.backup_type] = type_counts.get(b.backup_type, 0) + 1
            status_counts[b.status] = status_counts.get(b.status, 0) + 1
        total_size = sum(b.size_bytes for b in self._backups.values())
        return {
            "total_backups": len(self._backups),
            "total_verifications": len(self._verifications),
            "total_size_bytes": total_size,
            "type_distribution": type_counts,
            "status_distribution": status_counts,
        }
