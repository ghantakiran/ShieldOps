"""Tests for the Change Tracking & Deployment Correlation module.

Covers: change recording, retrieval, filtering, timeline, correlation scoring,
blast radius estimation, K8s/GitHub/CI-CD parsers, and API routes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.routes import changes as changes_mod
from shieldops.changes.tracker import (
    ChangeRecord,
    ChangeTimeline,
    ChangeTracker,
    CorrelationResult,
    RecordChangeRequest,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracker() -> ChangeTracker:
    """Return a fresh ChangeTracker instance."""
    return ChangeTracker()


def _make_request(**overrides: Any) -> RecordChangeRequest:
    """Helper to build a RecordChangeRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "source": "manual",
        "service": "api-server",
        "environment": "production",
        "change_type": "deployment",
        "description": "Deploy v1.2.3",
        "deployed_by": "ci-bot",
        "commit_sha": "abc123",
        "version": "v1.2.3",
        "blast_radius": "low",
    }
    defaults.update(overrides)
    return RecordChangeRequest(**defaults)


def _mock_user() -> UserResponse:
    return UserResponse(
        id="usr-test",
        email="test@shieldops.dev",
        name="Test User",
        role=UserRole.ADMIN,
        is_active=True,
    )


def _make_app(tracker_instance: ChangeTracker | None = None) -> tuple[FastAPI, TestClient]:
    """Build a minimal FastAPI app with the changes router wired."""
    app = FastAPI()
    app.include_router(changes_mod.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = _mock_user

    if tracker_instance is not None:
        changes_mod.set_tracker(tracker_instance)
    else:
        changes_mod._tracker = None

    client = TestClient(app, raise_server_exceptions=False)
    return app, client


# =========================================================================
# TestRecordChange
# =========================================================================


class TestRecordChange:
    """Tests for recording change events."""

    def test_record_change_returns_record(self, tracker: ChangeTracker) -> None:
        req = _make_request()
        record = tracker.record_change(req)
        assert isinstance(record, ChangeRecord)
        assert record.service == "api-server"
        assert record.environment == "production"

    def test_record_change_auto_generates_id(self, tracker: ChangeTracker) -> None:
        record = tracker.record_change(_make_request())
        assert record.id.startswith("chg-")
        assert len(record.id) == 16  # "chg-" + 12 hex chars

    def test_record_change_defaults(self, tracker: ChangeTracker) -> None:
        record = tracker.record_change(_make_request())
        assert record.status == "in_progress"
        assert record.completed_at is None
        assert record.started_at is not None

    def test_complete_change(self, tracker: ChangeTracker) -> None:
        record = tracker.record_change(_make_request())
        completed = tracker.complete_change(record.id)
        assert completed is not None
        assert completed.status == "completed"
        assert completed.completed_at is not None

    def test_complete_change_custom_status(self, tracker: ChangeTracker) -> None:
        record = tracker.record_change(_make_request())
        completed = tracker.complete_change(record.id, status="failed")
        assert completed is not None
        assert completed.status == "failed"

    def test_complete_change_missing_id(self, tracker: ChangeTracker) -> None:
        result = tracker.complete_change("chg-nonexistent")
        assert result is None


# =========================================================================
# TestGetChange
# =========================================================================


class TestGetChange:
    """Tests for retrieving individual changes."""

    def test_get_existing_change(self, tracker: ChangeTracker) -> None:
        record = tracker.record_change(_make_request())
        found = tracker.get_change(record.id)
        assert found is not None
        assert found.id == record.id

    def test_get_missing_change_returns_none(self, tracker: ChangeTracker) -> None:
        assert tracker.get_change("chg-nonexistent") is None


# =========================================================================
# TestListChanges
# =========================================================================


class TestListChanges:
    """Tests for listing changes with filters."""

    def test_list_all_changes(self, tracker: ChangeTracker) -> None:
        tracker.record_change(_make_request(service="svc-a"))
        tracker.record_change(_make_request(service="svc-b"))
        changes = tracker.list_changes()
        assert len(changes) == 2

    def test_list_filter_by_service(self, tracker: ChangeTracker) -> None:
        tracker.record_change(_make_request(service="svc-a"))
        tracker.record_change(_make_request(service="svc-b"))
        tracker.record_change(_make_request(service="svc-a"))
        changes = tracker.list_changes(service="svc-a")
        assert len(changes) == 2
        assert all(c.service == "svc-a" for c in changes)

    def test_list_filter_by_environment(self, tracker: ChangeTracker) -> None:
        tracker.record_change(_make_request(environment="production"))
        tracker.record_change(_make_request(environment="staging"))
        changes = tracker.list_changes(environment="staging")
        assert len(changes) == 1
        assert changes[0].environment == "staging"

    def test_list_respects_limit(self, tracker: ChangeTracker) -> None:
        for i in range(10):
            tracker.record_change(_make_request(service=f"svc-{i}"))
        changes = tracker.list_changes(limit=3)
        assert len(changes) == 3

    def test_list_sorted_desc_by_started_at(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        r1 = tracker.record_change(_make_request(description="first"))
        r1.started_at = now - timedelta(hours=2)
        r2 = tracker.record_change(_make_request(description="second"))
        r2.started_at = now - timedelta(hours=1)
        r3 = tracker.record_change(_make_request(description="third"))
        r3.started_at = now

        changes = tracker.list_changes()
        assert changes[0].description == "third"
        assert changes[1].description == "second"
        assert changes[2].description == "first"


# =========================================================================
# TestTimeline
# =========================================================================


class TestTimeline:
    """Tests for the change timeline view."""

    def test_full_timeline(self, tracker: ChangeTracker) -> None:
        tracker.record_change(_make_request())
        tracker.record_change(_make_request())
        timeline = tracker.get_timeline()
        assert isinstance(timeline, ChangeTimeline)
        assert timeline.total == 2
        assert len(timeline.changes) == 2

    def test_timeline_with_time_range(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        r1 = tracker.record_change(_make_request(description="old"))
        r1.started_at = now - timedelta(hours=5)
        r2 = tracker.record_change(_make_request(description="recent"))
        r2.started_at = now - timedelta(minutes=30)

        timeline = tracker.get_timeline(
            start=now - timedelta(hours=1),
            end=now,
        )
        assert timeline.total == 1
        assert timeline.changes[0].description == "recent"

    def test_empty_timeline(self, tracker: ChangeTracker) -> None:
        timeline = tracker.get_timeline()
        assert timeline.total == 0
        assert timeline.changes == []
        assert timeline.time_range == {}


# =========================================================================
# TestCorrelation
# =========================================================================


class TestCorrelation:
    """Tests for the incident correlation scoring algorithm."""

    def test_match_within_window(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        record = tracker.record_change(_make_request(service="web", environment="prod"))
        record.started_at = now - timedelta(minutes=10)

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="other-svc",
            incident_env="other-env",
            incident_time=now,
            time_window_minutes=60,
        )
        assert len(results) == 1
        assert results[0].correlation_score >= 0.3  # base score

    def test_no_match_outside_window(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        record = tracker.record_change(_make_request())
        record.started_at = now - timedelta(hours=5)

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=now,
            time_window_minutes=60,
        )
        assert len(results) == 0

    def test_same_service_bonus(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        record = tracker.record_change(_make_request(service="api-server", environment="other"))
        record.started_at = now - timedelta(minutes=30)

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=now,
        )
        assert len(results) == 1
        assert results[0].same_service is True
        assert "same_service" in results[0].factors
        # Base (0.3) + same_service (0.3) = 0.6
        assert results[0].correlation_score >= 0.6

    def test_same_environment_bonus(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        record = tracker.record_change(_make_request(service="other-svc", environment="production"))
        record.started_at = now - timedelta(minutes=30)

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=now,
        )
        assert len(results) == 1
        assert results[0].same_environment is True
        assert "same_environment" in results[0].factors
        # Base (0.3) + same_env (0.2) = 0.5
        assert results[0].correlation_score >= 0.5

    def test_recent_change_bonus(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        record = tracker.record_change(_make_request(service="other", environment="other"))
        record.started_at = now - timedelta(minutes=5)  # within 15 min

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=now,
        )
        assert len(results) == 1
        assert "recent_change" in results[0].factors
        # Base (0.3) + recent (0.1) = 0.4
        assert results[0].correlation_score >= 0.4

    def test_high_blast_radius_bonus(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)
        record = tracker.record_change(
            _make_request(
                service="other",
                environment="other",
                blast_radius="high",
            )
        )
        record.started_at = now - timedelta(minutes=30)

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=now,
        )
        assert len(results) == 1
        assert "high_blast_radius" in results[0].factors
        # Base (0.3) + blast_radius (0.1) = 0.4
        assert results[0].correlation_score >= 0.4

    def test_multiple_matches_sorted_by_score(self, tracker: ChangeTracker) -> None:
        now = datetime.now(UTC)

        # Low-score change: different service, different env, not recent
        r1 = tracker.record_change(_make_request(service="other", environment="dev"))
        r1.started_at = now - timedelta(minutes=45)

        # High-score change: same service, same env, recent
        r2 = tracker.record_change(_make_request(service="api-server", environment="production"))
        r2.started_at = now - timedelta(minutes=5)

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=now,
        )
        assert len(results) == 2
        # Highest score first
        assert results[0].correlation_score > results[1].correlation_score
        assert results[0].change_id == r2.id

    def test_no_changes_returns_empty(self, tracker: ChangeTracker) -> None:
        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=datetime.now(UTC),
        )
        assert results == []

    def test_full_score_combination(self, tracker: ChangeTracker) -> None:
        """Change matching all bonuses should score 1.0."""
        now = datetime.now(UTC)
        record = tracker.record_change(
            _make_request(
                service="api-server",
                environment="production",
                blast_radius="critical",
            )
        )
        record.started_at = now - timedelta(minutes=5)

        results = tracker.correlate_with_incident(
            incident_id="inc-001",
            incident_service="api-server",
            incident_env="production",
            incident_time=now,
        )
        assert len(results) == 1
        # 0.3 + 0.3 + 0.2 + 0.1 + 0.1 = 1.0
        assert results[0].correlation_score == 1.0


# =========================================================================
# TestBlastRadius
# =========================================================================


class TestBlastRadius:
    """Tests for heuristic blast radius estimation."""

    def test_production_deployment_is_high(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "deployment", "production") == "high"

    def test_staging_is_low(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "deployment", "staging") == "low"

    def test_config_change_production_is_medium(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "config_change", "production") == "medium"

    def test_rollback_production_is_medium(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "rollback", "production") == "medium"

    def test_scale_production_is_low(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "scale", "production") == "low"

    def test_config_change_dev_is_medium(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "config_change", "development") == "medium"

    def test_rollback_dev_is_medium(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "rollback", "development") == "medium"

    def test_deployment_dev_is_low(self, tracker: ChangeTracker) -> None:
        assert tracker.estimate_blast_radius("svc", "deployment", "development") == "low"


# =========================================================================
# TestK8sEvent
# =========================================================================


class TestK8sEvent:
    """Tests for parsing Kubernetes rollout events."""

    def test_parse_rollout_event(self, tracker: ChangeTracker) -> None:
        event = {
            "metadata": {
                "name": "api-server",
                "namespace": "production",
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"image": "api-server:v2.0.0"},
                        ],
                    },
                },
            },
        }
        record = tracker.record_from_k8s_event(event)
        assert record.source == "kubernetes"
        assert record.service == "api-server"
        assert record.environment == "production"
        assert record.change_type == "deployment"
        assert record.version == "api-server:v2.0.0"
        assert record.blast_radius == "high"  # production + deployment

    def test_handle_missing_fields(self, tracker: ChangeTracker) -> None:
        event: dict[str, Any] = {}
        record = tracker.record_from_k8s_event(event)
        assert record.source == "kubernetes"
        assert record.service == "unknown"
        assert record.environment == "default"
        assert record.version == ""


# =========================================================================
# TestGitHubWebhook
# =========================================================================


class TestGitHubWebhook:
    """Tests for parsing GitHub webhook payloads."""

    def test_parse_push_event(self, tracker: ChangeTracker) -> None:
        payload = {
            "ref": "refs/heads/main",
            "repository": {"name": "shieldops"},
            "head_commit": {
                "id": "abc123def456",
                "message": "feat: add correlation engine",
            },
            "pusher": {"name": "octocat"},
        }
        record = tracker.record_from_github_webhook(payload)
        assert record.source == "github"
        assert record.service == "shieldops"
        assert record.environment == "production"  # main branch -> production
        assert record.commit_sha == "abc123def456"
        assert record.deployed_by == "octocat"

    def test_parse_push_event_non_main(self, tracker: ChangeTracker) -> None:
        payload = {
            "ref": "refs/heads/develop",
            "repository": {"name": "shieldops"},
            "head_commit": {"id": "xyz789", "message": "wip"},
            "pusher": {"name": "dev"},
        }
        record = tracker.record_from_github_webhook(payload)
        assert record.environment == "staging"

    def test_parse_deployment_event(self, tracker: ChangeTracker) -> None:
        payload = {
            "deployment": {
                "sha": "deadbeef",
                "ref": "v3.0.0",
                "environment": "production",
                "description": "Production deploy v3.0.0",
            },
            "repository": {"name": "shieldops"},
            "sender": {"login": "deploy-bot"},
        }
        record = tracker.record_from_github_webhook(payload)
        assert record.source == "github"
        assert record.service == "shieldops"
        assert record.environment == "production"
        assert record.commit_sha == "deadbeef"
        assert record.deployed_by == "deploy-bot"
        assert record.description == "Production deploy v3.0.0"


# =========================================================================
# TestCICDPipeline
# =========================================================================


class TestCICDPipeline:
    """Tests for parsing CI/CD pipeline events."""

    def test_parse_pipeline_event(self, tracker: ChangeTracker) -> None:
        pipeline = {
            "project": "api-server",
            "environment": "production",
            "action": "deployment",
            "name": "Deploy api-server v4.1",
            "triggered_by": "ci-user",
            "commit_sha": "feed1234",
            "version": "v4.1.0",
        }
        record = tracker.record_from_cicd(pipeline)
        assert record.source == "cicd"
        assert record.service == "api-server"
        assert record.environment == "production"
        assert record.change_type == "deployment"
        assert record.commit_sha == "feed1234"
        assert record.deployed_by == "ci-user"

    def test_handle_missing_fields(self, tracker: ChangeTracker) -> None:
        pipeline: dict[str, Any] = {}
        record = tracker.record_from_cicd(pipeline)
        assert record.source == "cicd"
        assert record.service == "unknown"
        assert record.environment == "staging"
        assert record.change_type == "deployment"
        assert record.deployed_by == ""


# =========================================================================
# TestAPIRoutes
# =========================================================================


class TestAPIRoutes:
    """Tests for the /changes API endpoints via TestClient."""

    def test_post_record(self) -> None:
        _, client = _make_app(ChangeTracker())
        resp = client.post(
            "/api/v1/changes/record",
            json={
                "source": "manual",
                "service": "api-server",
                "environment": "production",
                "change_type": "deployment",
                "description": "Deploy v1.0",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "change" in data
        assert data["change"]["service"] == "api-server"
        assert data["change"]["id"].startswith("chg-")

    def test_get_list(self) -> None:
        tracker_inst = ChangeTracker()
        tracker_inst.record_change(_make_request())
        _, client = _make_app(tracker_inst)

        resp = client.get("/api/v1/changes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["changes"]) == 1

    def test_get_list_with_service_filter(self) -> None:
        tracker_inst = ChangeTracker()
        tracker_inst.record_change(_make_request(service="web"))
        tracker_inst.record_change(_make_request(service="db"))
        _, client = _make_app(tracker_inst)

        resp = client.get("/api/v1/changes", params={"service": "web"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_get_change_by_id(self) -> None:
        tracker_inst = ChangeTracker()
        record = tracker_inst.record_change(_make_request())
        _, client = _make_app(tracker_inst)

        resp = client.get(f"/api/v1/changes/{record.id}")
        assert resp.status_code == 200
        assert resp.json()["change"]["id"] == record.id

    def test_get_change_not_found(self) -> None:
        _, client = _make_app(ChangeTracker())
        resp = client.get("/api/v1/changes/chg-nonexistent")
        assert resp.status_code == 404

    def test_put_complete(self) -> None:
        tracker_inst = ChangeTracker()
        record = tracker_inst.record_change(_make_request())
        _, client = _make_app(tracker_inst)

        resp = client.put(f"/api/v1/changes/{record.id}/complete")
        assert resp.status_code == 200
        assert resp.json()["change"]["status"] == "completed"

    def test_put_complete_not_found(self) -> None:
        _, client = _make_app(ChangeTracker())
        resp = client.put("/api/v1/changes/chg-nonexistent/complete")
        assert resp.status_code == 404

    def test_get_timeline(self) -> None:
        tracker_inst = ChangeTracker()
        tracker_inst.record_change(_make_request())
        _, client = _make_app(tracker_inst)

        resp = client.get("/api/v1/changes/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "time_range" in data

    def test_get_correlate(self) -> None:
        tracker_inst = ChangeTracker()
        now = datetime.now(UTC)
        record = tracker_inst.record_change(
            _make_request(service="api-server", environment="production")
        )
        record.started_at = now - timedelta(minutes=10)
        _, client = _make_app(tracker_inst)

        resp = client.get(
            "/api/v1/changes/correlate/inc-001",
            params={
                "service": "api-server",
                "environment": "production",
                "time": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["incident_id"] == "inc-001"
        assert data["count"] >= 1
        assert data["correlations"][0]["correlation_score"] > 0

    def test_post_k8s(self) -> None:
        _, client = _make_app(ChangeTracker())
        event = {
            "metadata": {"name": "web-app", "namespace": "staging"},
            "spec": {},
        }
        resp = client.post("/api/v1/changes/k8s", json=event)
        assert resp.status_code == 200
        assert resp.json()["change"]["source"] == "kubernetes"

    def test_post_github(self) -> None:
        _, client = _make_app(ChangeTracker())
        payload = {
            "ref": "refs/heads/main",
            "repository": {"name": "shieldops"},
            "head_commit": {"id": "abc", "message": "deploy"},
            "pusher": {"name": "bot"},
        }
        resp = client.post("/api/v1/changes/github", json=payload)
        assert resp.status_code == 200
        assert resp.json()["change"]["source"] == "github"

    def test_post_cicd(self) -> None:
        _, client = _make_app(ChangeTracker())
        pipeline = {
            "project": "api-server",
            "environment": "staging",
            "name": "Deploy v2",
        }
        resp = client.post("/api/v1/changes/cicd", json=pipeline)
        assert resp.status_code == 200
        assert resp.json()["change"]["source"] == "cicd"

    def test_503_without_tracker(self) -> None:
        _, client = _make_app(tracker_instance=None)
        changes_mod._tracker = None  # ensure no tracker is set
        resp = client.get("/api/v1/changes")
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()

    def test_post_record_503_without_tracker(self) -> None:
        _, client = _make_app(tracker_instance=None)
        changes_mod._tracker = None
        resp = client.post(
            "/api/v1/changes/record",
            json={
                "source": "manual",
                "service": "svc",
                "environment": "dev",
                "change_type": "deployment",
                "description": "test",
            },
        )
        assert resp.status_code == 503


# =========================================================================
# TestPydanticModels
# =========================================================================


class TestPydanticModels:
    """Tests for Pydantic model validation and serialization."""

    def test_change_record_serialization(self) -> None:
        record = ChangeRecord(
            source="kubernetes",
            service="web",
            environment="production",
            change_type="deployment",
            description="Deploy",
        )
        data = record.model_dump(mode="json")
        assert isinstance(data["started_at"], str)
        assert data["status"] == "in_progress"
        assert data["blast_radius"] == "low"

    def test_correlation_result_model(self) -> None:
        result = CorrelationResult(
            incident_id="inc-001",
            change_id="chg-abc123",
            correlation_score=0.85,
            time_delta_minutes=12.5,
            same_service=True,
            same_environment=True,
            factors=["within_time_window", "same_service", "same_environment"],
        )
        assert result.correlation_score == 0.85
        assert len(result.factors) == 3

    def test_change_timeline_model(self) -> None:
        timeline = ChangeTimeline(
            changes=[],
            total=0,
            time_range={},
        )
        assert timeline.total == 0
        assert timeline.changes == []

    def test_record_change_request_defaults(self) -> None:
        req = RecordChangeRequest(
            source="manual",
            service="svc",
            environment="dev",
            change_type="deployment",
            description="test",
        )
        assert req.deployed_by == ""
        assert req.commit_sha == ""
        assert req.version == ""
        assert req.blast_radius == "low"
        assert req.metadata == {}
