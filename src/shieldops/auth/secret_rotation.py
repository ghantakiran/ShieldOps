"""Secret Rotation Scheduler — manages scheduled rotation of secrets."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SecretType(StrEnum):
    API_KEY = "api_key"
    DATABASE = "database"
    CERTIFICATE = "certificate"
    SSH_KEY = "ssh_key"
    TOKEN = "token"  # noqa: S105
    PASSWORD = "password"  # noqa: S105


class RotationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    OVERDUE = "overdue"


# --- Models ---


class SecretRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    secret_type: SecretType
    service: str
    environment: str = "production"
    rotation_interval_days: int = 90
    last_rotated_at: float | None = None
    next_rotation_due: float | None = None
    status: RotationStatus = RotationStatus.PENDING
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class RotationEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    secret_id: str
    status: RotationStatus
    initiated_by: str = ""
    started_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
    error_message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Scheduler ---


class SecretRotationScheduler:
    """Manages scheduled rotation of secrets/credentials with compliance tracking."""

    def __init__(self, max_secrets: int = 1000, default_rotation_days: int = 90) -> None:
        self.max_secrets = max_secrets
        self.default_rotation_days = default_rotation_days
        self._secrets: dict[str, SecretRecord] = {}
        self._events: dict[str, RotationEvent] = {}
        logger.info(
            "secret_rotation_scheduler.initialized",
            max_secrets=max_secrets,
            default_rotation_days=default_rotation_days,
        )

    def register_secret(
        self, name: str, secret_type: SecretType, service: str, **kw: Any
    ) -> SecretRecord:
        """Register a secret for rotation tracking."""
        if len(self._secrets) >= self.max_secrets:
            raise ValueError(f"Max secrets limit reached ({self.max_secrets})")
        record = SecretRecord(
            name=name,
            secret_type=secret_type,
            service=service,
            **kw,
        )
        if record.next_rotation_due is None:
            record.next_rotation_due = record.created_at + record.rotation_interval_days * 86400
        self._secrets[record.id] = record
        logger.info(
            "secret_rotation_scheduler.secret_registered",
            secret_id=record.id,
            name=name,
            secret_type=secret_type,
            service=service,
        )
        return record

    def start_rotation(self, secret_id: str, initiated_by: str = "") -> RotationEvent:
        """Start a rotation for a secret."""
        secret = self._secrets.get(secret_id)
        if secret is None:
            raise ValueError(f"Secret not found: {secret_id}")
        secret.status = RotationStatus.IN_PROGRESS
        event = RotationEvent(
            secret_id=secret_id,
            status=RotationStatus.IN_PROGRESS,
            initiated_by=initiated_by,
        )
        self._events[event.id] = event
        logger.info(
            "secret_rotation_scheduler.rotation_started",
            event_id=event.id,
            secret_id=secret_id,
            initiated_by=initiated_by,
        )
        return event

    def complete_rotation(
        self,
        event_id: str,
        success: bool = True,
        error_message: str = "",
    ) -> RotationEvent | None:
        """Complete a rotation event."""
        event = self._events.get(event_id)
        if event is None:
            return None
        now = time.time()
        event.completed_at = now
        if success:
            event.status = RotationStatus.COMPLETED
            secret = self._secrets.get(event.secret_id)
            if secret is not None:
                secret.last_rotated_at = now
                secret.next_rotation_due = now + secret.rotation_interval_days * 86400
                secret.status = RotationStatus.COMPLETED
            logger.info(
                "secret_rotation_scheduler.rotation_completed",
                event_id=event_id,
                secret_id=event.secret_id,
            )
        else:
            event.status = RotationStatus.FAILED
            event.error_message = error_message
            secret = self._secrets.get(event.secret_id)
            if secret is not None:
                secret.status = RotationStatus.FAILED
            logger.warning(
                "secret_rotation_scheduler.rotation_failed",
                event_id=event_id,
                secret_id=event.secret_id,
                error_message=error_message,
            )
        return event

    def get_secret(self, secret_id: str) -> SecretRecord | None:
        """Get a secret record by ID."""
        return self._secrets.get(secret_id)

    def list_secrets(
        self,
        service: str | None = None,
        secret_type: SecretType | None = None,
        status: RotationStatus | None = None,
    ) -> list[SecretRecord]:
        """List secrets with optional filters."""
        results = list(self._secrets.values())
        if service is not None:
            results = [s for s in results if s.service == service]
        if secret_type is not None:
            results = [s for s in results if s.secret_type == secret_type]
        if status is not None:
            results = [s for s in results if s.status == status]
        return results

    def get_overdue_secrets(self) -> list[SecretRecord]:
        """Get secrets that are past their rotation due date or never rotated."""
        now = time.time()
        overdue: list[SecretRecord] = []
        for secret in self._secrets.values():
            past_due = secret.next_rotation_due is not None and secret.next_rotation_due < now
            never_rotated = (
                secret.last_rotated_at is None and secret.status == RotationStatus.PENDING
            )
            if past_due or never_rotated:
                overdue.append(secret)
        return overdue

    def get_rotation_history(self, secret_id: str | None = None) -> list[RotationEvent]:
        """Get rotation events, optionally filtered by secret_id."""
        events = list(self._events.values())
        if secret_id is not None:
            events = [e for e in events if e.secret_id == secret_id]
        return events

    def delete_secret(self, secret_id: str) -> bool:
        """Delete a secret record."""
        if secret_id in self._secrets:
            del self._secrets[secret_id]
            logger.info(
                "secret_rotation_scheduler.secret_deleted",
                secret_id=secret_id,
            )
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics."""
        secrets = list(self._secrets.values())
        events = list(self._events.values())
        type_distribution: dict[str, int] = {}
        for s in secrets:
            type_distribution[s.secret_type] = type_distribution.get(s.secret_type, 0) + 1
        completed = sum(1 for e in events if e.status == RotationStatus.COMPLETED)
        failed = sum(1 for e in events if e.status == RotationStatus.FAILED)
        return {
            "total_secrets": len(secrets),
            "total_rotations": len(events),
            "overdue_count": len(self.get_overdue_secrets()),
            "completed_rotations": completed,
            "failed_rotations": failed,
            "type_distribution": type_distribution,
        }
