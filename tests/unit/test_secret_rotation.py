"""Tests for shieldops.auth.secret_rotation — SecretRotationScheduler."""

from __future__ import annotations

import time

import pytest

from shieldops.auth.secret_rotation import (
    RotationEvent,
    RotationStatus,
    SecretRecord,
    SecretRotationScheduler,
    SecretType,
)


def _scheduler(**kw) -> SecretRotationScheduler:
    return SecretRotationScheduler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # SecretType (6 values)

    def test_secret_type_api_key(self):
        assert SecretType.API_KEY == "api_key"

    def test_secret_type_database(self):
        assert SecretType.DATABASE == "database"

    def test_secret_type_certificate(self):
        assert SecretType.CERTIFICATE == "certificate"

    def test_secret_type_ssh_key(self):
        assert SecretType.SSH_KEY == "ssh_key"

    def test_secret_type_token(self):
        assert SecretType.TOKEN == "token"  # noqa: S105

    def test_secret_type_password(self):
        assert SecretType.PASSWORD == "password"  # noqa: S105

    # RotationStatus (5 values)

    def test_rotation_status_pending(self):
        assert RotationStatus.PENDING == "pending"

    def test_rotation_status_in_progress(self):
        assert RotationStatus.IN_PROGRESS == "in_progress"

    def test_rotation_status_completed(self):
        assert RotationStatus.COMPLETED == "completed"

    def test_rotation_status_failed(self):
        assert RotationStatus.FAILED == "failed"

    def test_rotation_status_overdue(self):
        assert RotationStatus.OVERDUE == "overdue"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_secret_record_defaults(self):
        rec = SecretRecord(name="db-pass", secret_type=SecretType.DATABASE, service="auth")
        assert rec.id  # auto-generated uuid
        assert rec.environment == "production"
        assert rec.rotation_interval_days == 90
        assert rec.last_rotated_at is None
        assert rec.next_rotation_due is None
        assert rec.status == RotationStatus.PENDING
        assert rec.owner == ""
        assert rec.metadata == {}
        assert rec.created_at > 0

    def test_rotation_event_defaults(self):
        ev = RotationEvent(secret_id="s1", status=RotationStatus.IN_PROGRESS)
        assert ev.id
        assert ev.secret_id == "s1"  # noqa: S105
        assert ev.initiated_by == ""
        assert ev.completed_at is None
        assert ev.error_message == ""
        assert ev.metadata == {}
        assert ev.started_at > 0


# ---------------------------------------------------------------------------
# register_secret
# ---------------------------------------------------------------------------


class TestRegisterSecret:
    def test_basic_register(self):
        s = _scheduler()
        rec = s.register_secret("db-pass", SecretType.DATABASE, "auth-svc")
        assert rec.name == "db-pass"
        assert rec.secret_type == SecretType.DATABASE
        assert rec.service == "auth-svc"
        assert rec.status == RotationStatus.PENDING

    def test_register_all_fields(self):
        s = _scheduler()
        rec = s.register_secret(
            "api-key",
            SecretType.API_KEY,
            "gateway",
            environment="staging",
            rotation_interval_days=30,
            owner="team-a",
        )
        assert rec.environment == "staging"
        assert rec.rotation_interval_days == 30
        assert rec.owner == "team-a"

    def test_register_unique_ids(self):
        s = _scheduler()
        r1 = s.register_secret("k1", SecretType.TOKEN, "svc1")
        r2 = s.register_secret("k2", SecretType.TOKEN, "svc2")
        assert r1.id != r2.id

    def test_register_max_limit(self):
        s = _scheduler(max_secrets=2)
        s.register_secret("k1", SecretType.TOKEN, "svc1")
        s.register_secret("k2", SecretType.TOKEN, "svc2")
        with pytest.raises(ValueError, match="Max secrets limit reached"):
            s.register_secret("k3", SecretType.TOKEN, "svc3")

    def test_register_sets_next_rotation_due(self):
        s = _scheduler()
        rec = s.register_secret("k", SecretType.SSH_KEY, "svc", rotation_interval_days=7)
        assert rec.next_rotation_due is not None
        assert rec.next_rotation_due == pytest.approx(rec.created_at + 7 * 86400, abs=1.0)


# ---------------------------------------------------------------------------
# start_rotation
# ---------------------------------------------------------------------------


class TestStartRotation:
    def test_start_basic(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc")
        ev = s.start_rotation(rec.id)
        assert ev.secret_id == rec.id  # noqa: S105
        assert ev.status == RotationStatus.IN_PROGRESS

    def test_start_updates_secret_status(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc")
        s.start_rotation(rec.id)
        assert rec.status == RotationStatus.IN_PROGRESS

    def test_start_not_found(self):
        s = _scheduler()
        with pytest.raises(ValueError, match="Secret not found"):
            s.start_rotation("nonexistent")


# ---------------------------------------------------------------------------
# complete_rotation
# ---------------------------------------------------------------------------


class TestCompleteRotation:
    def test_complete_success(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc")
        ev = s.start_rotation(rec.id)
        result = s.complete_rotation(ev.id, success=True)
        assert result is not None
        assert result.status == RotationStatus.COMPLETED
        assert result.completed_at is not None

    def test_complete_failure(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc")
        ev = s.start_rotation(rec.id)
        result = s.complete_rotation(ev.id, success=False, error_message="timeout")
        assert result is not None
        assert result.status == RotationStatus.FAILED
        assert result.error_message == "timeout"
        assert rec.status == RotationStatus.FAILED

    def test_complete_not_found(self):
        s = _scheduler()
        result = s.complete_rotation("nonexistent")
        assert result is None

    def test_complete_updates_next_due(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc", rotation_interval_days=7)
        ev = s.start_rotation(rec.id)
        s.complete_rotation(ev.id, success=True)
        assert rec.last_rotated_at is not None
        expected_next = rec.last_rotated_at + 7 * 86400
        assert rec.next_rotation_due == pytest.approx(expected_next, abs=1.0)


# ---------------------------------------------------------------------------
# list_secrets
# ---------------------------------------------------------------------------


class TestListSecrets:
    def test_list_all(self):
        s = _scheduler()
        s.register_secret("k1", SecretType.TOKEN, "svc1")
        s.register_secret("k2", SecretType.DATABASE, "svc2")
        assert len(s.list_secrets()) == 2

    def test_list_by_service(self):
        s = _scheduler()
        s.register_secret("k1", SecretType.TOKEN, "svc1")
        s.register_secret("k2", SecretType.DATABASE, "svc2")
        results = s.list_secrets(service="svc1")
        assert len(results) == 1
        assert results[0].service == "svc1"

    def test_list_by_type(self):
        s = _scheduler()
        s.register_secret("k1", SecretType.TOKEN, "svc1")
        s.register_secret("k2", SecretType.DATABASE, "svc2")
        results = s.list_secrets(secret_type=SecretType.DATABASE)
        assert len(results) == 1
        assert results[0].secret_type == SecretType.DATABASE

    def test_list_by_status(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc1")
        s.register_secret("k2", SecretType.DATABASE, "svc2")
        ev = s.start_rotation(rec.id)
        s.complete_rotation(ev.id, success=True)
        results = s.list_secrets(status=RotationStatus.COMPLETED)
        assert len(results) == 1

    def test_list_empty(self):
        s = _scheduler()
        assert s.list_secrets() == []


# ---------------------------------------------------------------------------
# get_overdue_secrets
# ---------------------------------------------------------------------------


class TestOverdueSecrets:
    def test_never_rotated_is_overdue(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc")
        # brand-new secret with PENDING status and no last_rotated_at => overdue
        assert rec in s.get_overdue_secrets()

    def test_recently_rotated_not_overdue(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc", rotation_interval_days=30)
        ev = s.start_rotation(rec.id)
        s.complete_rotation(ev.id, success=True)
        overdue = s.get_overdue_secrets()
        assert rec not in overdue

    def test_past_due(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc", rotation_interval_days=1)
        # Force next_rotation_due into the past
        rec.next_rotation_due = time.time() - 1000
        rec.status = RotationStatus.COMPLETED  # not PENDING, so second branch won't match
        overdue = s.get_overdue_secrets()
        assert rec in overdue


# ---------------------------------------------------------------------------
# get_rotation_history
# ---------------------------------------------------------------------------


class TestRotationHistory:
    def test_all_history(self):
        s = _scheduler()
        r1 = s.register_secret("k1", SecretType.TOKEN, "svc1")
        r2 = s.register_secret("k2", SecretType.TOKEN, "svc2")
        s.start_rotation(r1.id)
        s.start_rotation(r2.id)
        assert len(s.get_rotation_history()) == 2

    def test_filtered_by_secret(self):
        s = _scheduler()
        r1 = s.register_secret("k1", SecretType.TOKEN, "svc1")
        r2 = s.register_secret("k2", SecretType.TOKEN, "svc2")
        s.start_rotation(r1.id)
        s.start_rotation(r2.id)
        history = s.get_rotation_history(secret_id=r1.id)
        assert len(history) == 1
        assert history[0].secret_id == r1.id


# ---------------------------------------------------------------------------
# delete_secret
# ---------------------------------------------------------------------------


class TestDeleteSecret:
    def test_delete_existing(self):
        s = _scheduler()
        rec = s.register_secret("k1", SecretType.TOKEN, "svc")
        assert s.delete_secret(rec.id) is True
        assert s.get_secret(rec.id) is None

    def test_delete_nonexistent(self):
        s = _scheduler()
        assert s.delete_secret("nonexistent") is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        s = _scheduler()
        stats = s.get_stats()
        assert stats["total_secrets"] == 0
        assert stats["total_rotations"] == 0
        assert stats["overdue_count"] == 0
        assert stats["completed_rotations"] == 0
        assert stats["failed_rotations"] == 0
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        s = _scheduler()
        r1 = s.register_secret("k1", SecretType.TOKEN, "svc1")
        s.register_secret("k2", SecretType.DATABASE, "svc2")
        ev = s.start_rotation(r1.id)
        s.complete_rotation(ev.id, success=True)
        stats = s.get_stats()
        assert stats["total_secrets"] == 2
        assert stats["total_rotations"] == 1
        assert stats["completed_rotations"] == 1
        assert stats["failed_rotations"] == 0
        assert SecretType.TOKEN in stats["type_distribution"]
        assert SecretType.DATABASE in stats["type_distribution"]
