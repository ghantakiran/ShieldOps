"""Tests for batch operations API endpoints.

Tests cover:
- POST /batch/investigations — Bulk create investigations
- POST /batch/remediations — Bulk create remediations
- POST /batch/update-status — Bulk update status
- GET /batch/jobs/{job_id} — Check batch job status
- Validation: max 100 items, empty batch, invalid entity/operation
- Partial failure handling
- Job not found (404)
- Auth enforcement
- Job auto-expiry
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.routes import batch


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the batch router."""
    app = FastAPI()
    app.include_router(batch.router, prefix="/api/v1")
    return app


def _mock_admin_user() -> UserResponse:
    return UserResponse(
        id="user-1",
        email="admin@test.com",
        name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset module-level state between tests."""
    original_repo = batch._repository
    original_jobs = batch._batch_jobs.copy()
    batch._repository = None
    batch._batch_jobs.clear()
    yield
    batch._repository = original_repo
    batch._batch_jobs.clear()
    batch._batch_jobs.update(original_jobs)


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save_investigation = AsyncMock(return_value=None)
    repo.save_remediation = AsyncMock(return_value=None)
    repo.get_investigation = AsyncMock(
        return_value={"investigation_id": "inv-1", "status": "created"}
    )
    repo.get_remediation = AsyncMock(return_value={"remediation_id": "rem-1", "status": "created"})
    repo._sf = AsyncMock()
    return repo


@pytest.fixture
def client(mock_repo: AsyncMock) -> TestClient:
    """TestClient with auth bypassed and mock repository."""
    app = _create_test_app()
    batch.set_repository(mock_repo)

    async def _mock_user() -> UserResponse:
        return _mock_admin_user()

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def viewer_client(mock_repo: AsyncMock) -> TestClient:
    """TestClient with a viewer role (should be forbidden)."""
    app = _create_test_app()
    batch.set_repository(mock_repo)

    async def _mock_viewer() -> UserResponse:
        return UserResponse(
            id="user-2",
            email="viewer@test.com",
            name="Viewer",
            role=UserRole.VIEWER,
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = _mock_viewer
    return TestClient(app, raise_server_exceptions=False)


def _investigation_items(count: int = 2) -> list[dict[str, Any]]:
    """Generate investigation batch items."""
    return [
        {
            "alert_id": f"alert-{i}",
            "title": f"Test alert {i}",
            "severity": "warning",
            "environment": "production",
        }
        for i in range(count)
    ]


def _remediation_items(count: int = 2) -> list[dict[str, Any]]:
    """Generate remediation batch items."""
    return [
        {
            "investigation_id": f"inv-{i}",
            "action": "restart_service",
            "target": f"service-{i}",
            "environment": "staging",
        }
        for i in range(count)
    ]


def _status_update_items(
    entity_type: str = "investigation",
) -> list[dict[str, Any]]:
    """Generate status update batch items."""
    prefix = "inv" if entity_type == "investigation" else "rem"
    return [{"id": f"{prefix}-{i}", "status": "completed"} for i in range(2)]


# ================================================================
# POST /batch/investigations
# ================================================================


class TestBatchCreateInvestigations:
    def test_returns_202_with_job_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(3),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["total"] == 3
        assert "message" in data

    def test_creates_job_in_tracker(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(2),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        job_id = resp.json()["job_id"]
        assert job_id in batch._batch_jobs
        job = batch._batch_jobs[job_id]
        assert job.total == 2

    def test_rejects_wrong_entity_type(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _remediation_items(),
                "operation": "create",
                "entity_type": "remediation",
            },
        )
        assert resp.status_code == 400
        assert "investigation" in resp.json()["detail"]

    def test_rejects_wrong_operation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(),
                "operation": "update_status",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 400
        assert "create" in resp.json()["detail"]


# ================================================================
# POST /batch/remediations
# ================================================================


class TestBatchCreateRemediations:
    def test_returns_202_with_job_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/remediations",
            json={
                "items": _remediation_items(2),
                "operation": "create",
                "entity_type": "remediation",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["total"] == 2

    def test_rejects_wrong_entity_type(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/remediations",
            json={
                "items": _investigation_items(),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 400


# ================================================================
# POST /batch/update-status
# ================================================================


class TestBatchUpdateStatus:
    def test_returns_202(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/update-status",
            json={
                "items": _status_update_items(),
                "operation": "update_status",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["total"] == 2

    def test_rejects_create_operation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/update-status",
            json={
                "items": _status_update_items(),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 400
        assert "update_status" in resp.json()["detail"]


# ================================================================
# GET /batch/jobs/{job_id}
# ================================================================


class TestGetBatchJobStatus:
    def test_returns_pending_job(self, client: TestClient) -> None:
        # Create a job first
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        job_id = resp.json()["job_id"]

        # Fetch its status
        resp2 = client.get(f"/api/v1/batch/jobs/{job_id}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["job_id"] == job_id
        assert data["total"] == 2
        assert data["status"] in ("pending", "processing", "completed")

    def test_404_for_unknown_job(self, client: TestClient) -> None:
        resp = client.get("/api/v1/batch/jobs/nonexistent-job-id")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_completed_job_has_counts(self, client: TestClient) -> None:
        """Manually insert a completed job and verify fields."""
        job = batch.BatchJobStatus(
            job_id="test-completed",
            status="completed",
            total=5,
            succeeded=5,
            failed=0,
            created_at=datetime.now(UTC).isoformat(),
            completed_at=datetime.now(UTC).isoformat(),
        )
        batch._batch_jobs["test-completed"] = job

        resp = client.get("/api/v1/batch/jobs/test-completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] == 5
        assert data["failed"] == 0
        assert data["completed_at"] is not None

    def test_failed_job_has_errors(self, client: TestClient) -> None:
        """Manually insert a failed job and verify error list."""
        job = batch.BatchJobStatus(
            job_id="test-with-errors",
            status="completed_with_errors",
            total=3,
            succeeded=2,
            failed=1,
            errors=[{"index": 1, "error": "Some error"}],
            created_at=datetime.now(UTC).isoformat(),
            completed_at=datetime.now(UTC).isoformat(),
        )
        batch._batch_jobs["test-with-errors"] = job

        resp = client.get("/api/v1/batch/jobs/test-with-errors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["failed"] == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["index"] == 1


# ================================================================
# Validation: max 100 items
# ================================================================


class TestBatchSizeLimits:
    def test_rejects_more_than_100_items(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(101),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 422  # Pydantic validation

    def test_rejects_empty_batch(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": [],
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 422  # min_length=1

    def test_accepts_exactly_100_items(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(100),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 202
        assert resp.json()["total"] == 100

    def test_accepts_single_item(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(1),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 202
        assert resp.json()["total"] == 1


# ================================================================
# Invalid entity type and operation
# ================================================================


class TestInvalidInputs:
    def test_invalid_entity_type_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": [{"title": "x"}],
                "operation": "create",
                "entity_type": "nonexistent_type",
            },
        )
        assert resp.status_code == 422

    def test_invalid_operation_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/batch/investigations",
            json={
                "items": [{"title": "x"}],
                "operation": "delete",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 422


# ================================================================
# Partial failure handling
# ================================================================


class TestPartialFailure:
    @pytest.mark.asyncio
    async def test_partial_failure_tracking(self, mock_repo: AsyncMock) -> None:
        """Verify that when some items fail, the job
        records both succeeded and failed counts."""
        call_count = 0

        async def _fail_on_second(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Simulated failure on item 2")

        mock_repo.save_investigation = _fail_on_second

        request = batch.BatchRequest(
            items=_investigation_items(3),
            operation="create",
            entity_type="investigation",
        )
        job_id = "test-partial"
        batch._batch_jobs[job_id] = batch.BatchJobStatus(
            job_id=job_id,
            status="pending",
            total=3,
            created_at=datetime.now(UTC).isoformat(),
        )

        await batch._process_batch(job_id, request, mock_repo)

        job = batch._batch_jobs[job_id]
        assert job.succeeded == 2
        assert job.failed == 1
        assert job.status == "completed_with_errors"
        assert len(job.errors) == 1
        assert job.errors[0]["index"] == 1

    @pytest.mark.asyncio
    async def test_all_succeed_status(self, mock_repo: AsyncMock) -> None:
        """When all items succeed, status should be 'completed'."""
        request = batch.BatchRequest(
            items=_investigation_items(2),
            operation="create",
            entity_type="investigation",
        )
        job_id = "test-all-ok"
        batch._batch_jobs[job_id] = batch.BatchJobStatus(
            job_id=job_id,
            status="pending",
            total=2,
            created_at=datetime.now(UTC).isoformat(),
        )

        await batch._process_batch(job_id, request, mock_repo)

        job = batch._batch_jobs[job_id]
        assert job.succeeded == 2
        assert job.failed == 0
        assert job.status == "completed"
        assert job.completed_at is not None


# ================================================================
# Authentication enforcement
# ================================================================


class TestAuthEnforcement:
    def test_unauthenticated_returns_401(self) -> None:
        """Without auth override, requests should fail."""
        app = _create_test_app()
        batch.set_repository(AsyncMock())
        # No dependency override -> auth kicks in
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        # Should be 401 or 403 (no bearer token)
        assert resp.status_code in (401, 403)

    def test_viewer_forbidden_for_create(self, viewer_client: TestClient) -> None:
        resp = viewer_client.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 403

    def test_viewer_can_read_job_status(self, viewer_client: TestClient) -> None:
        """Viewers should be able to check job status (GET)."""
        job = batch.BatchJobStatus(
            job_id="viewer-test",
            status="completed",
            total=1,
            succeeded=1,
            created_at=datetime.now(UTC).isoformat(),
        )
        batch._batch_jobs["viewer-test"] = job

        resp = viewer_client.get("/api/v1/batch/jobs/viewer-test")
        assert resp.status_code == 200


# ================================================================
# 503 when no repository
# ================================================================


class TestNoRepository:
    def test_503_when_no_repo(self) -> None:
        app = _create_test_app()
        # Do NOT set repository

        async def _mock_user() -> UserResponse:
            return _mock_admin_user()

        app.dependency_overrides[get_current_user] = _mock_user
        c = TestClient(app, raise_server_exceptions=False)

        resp = c.post(
            "/api/v1/batch/investigations",
            json={
                "items": _investigation_items(),
                "operation": "create",
                "entity_type": "investigation",
            },
        )
        assert resp.status_code == 503
        assert "Database" in resp.json()["detail"]


# ================================================================
# Job auto-expiry
# ================================================================


class TestJobAutoExpiry:
    def test_expired_jobs_cleaned_up(self, client: TestClient) -> None:
        """Jobs older than 1 hour should be cleaned up."""
        old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        batch._batch_jobs["old-job"] = batch.BatchJobStatus(
            job_id="old-job",
            status="completed",
            total=1,
            succeeded=1,
            created_at=old_time,
        )
        # Also add a recent job
        recent_time = datetime.now(UTC).isoformat()
        batch._batch_jobs["recent-job"] = batch.BatchJobStatus(
            job_id="recent-job",
            status="completed",
            total=1,
            succeeded=1,
            created_at=recent_time,
        )

        # Trigger cleanup via GET (calls _cleanup_expired_jobs)
        resp = client.get("/api/v1/batch/jobs/recent-job")
        assert resp.status_code == 200

        # Old job should be cleaned up
        assert "old-job" not in batch._batch_jobs
        # Recent job should remain
        assert "recent-job" in batch._batch_jobs

    def test_expired_job_returns_404(self, client: TestClient) -> None:
        """After expiry, fetching the job returns 404."""
        old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        batch._batch_jobs["expired-job"] = batch.BatchJobStatus(
            job_id="expired-job",
            status="completed",
            total=1,
            succeeded=1,
            created_at=old_time,
        )

        resp = client.get("/api/v1/batch/jobs/expired-job")
        assert resp.status_code == 404
