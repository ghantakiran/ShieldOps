"""Comprehensive unit tests for Terraform provider API routes.

Tests cover two modules:
- terraform.py: CRUD endpoints for agents, playbooks, policies, webhook-subscriptions
- terraform_state.py: State storage and locking endpoints

All routes use in-memory dicts, so no database/external dependencies are needed.
Module-level dicts are cleared between tests via an autouse fixture to prevent
state leakage.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from shieldops.api.routes import terraform as tf_mod
from shieldops.api.routes import terraform_state as tf_state_mod
from shieldops.api.routes.terraform import router as tf_router
from shieldops.api.routes.terraform_state import router as tf_state_router

# ---------------------------------------------------------------------------
# Test application
# ---------------------------------------------------------------------------
_app = FastAPI()
_app.include_router(tf_router)
_app.include_router(tf_state_router)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear all in-memory stores before and after each test."""
    tf_mod._agents.clear()
    tf_mod._playbooks.clear()
    tf_mod._policies.clear()
    tf_mod._webhook_subscriptions.clear()
    tf_state_mod._state_store.clear()
    tf_state_mod._locks.clear()
    yield
    tf_mod._agents.clear()
    tf_mod._playbooks.clear()
    tf_mod._policies.clear()
    tf_mod._webhook_subscriptions.clear()
    tf_state_mod._state_store.clear()
    tf_state_mod._locks.clear()


@pytest.fixture
async def client():
    """Async HTTP client wired to the test FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resource_payload(name: str, config: dict | None = None) -> dict:
    return {"name": name, "config": config or {}}


# ===========================================================================
# AGENT CONFIG CRUD
# ===========================================================================
class TestAgentConfigCRUD:
    """Tests for /terraform/agents endpoints."""

    @pytest.mark.asyncio
    async def test_create_agent_returns_201_with_resource(self, client: AsyncClient):
        resp = await client.post(
            "/terraform/agents",
            json=_resource_payload("invest-agent", {"type": "investigation", "llm": "claude"}),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "invest-agent"
        assert data["config"] == {"type": "investigation", "llm": "claude"}
        assert data["version"] == 1
        assert data["id"].startswith("agent-")
        assert data["created_at"] != ""
        assert data["updated_at"] != ""

    @pytest.mark.asyncio
    async def test_create_agent_duplicate_returns_409(self, client: AsyncClient):
        await client.post("/terraform/agents", json=_resource_payload("dup-agent"))
        resp = await client.post("/terraform/agents", json=_resource_payload("dup-agent"))
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, client: AsyncClient):
        resp = await client.get("/terraform/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resources"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_list_agents_returns_all_created(self, client: AsyncClient):
        await client.post("/terraform/agents", json=_resource_payload("agent-a"))
        await client.post("/terraform/agents", json=_resource_payload("agent-b"))
        resp = await client.get("/terraform/agents")
        data = resp.json()
        assert data["count"] == 2
        names = {r["name"] for r in data["resources"]}
        assert names == {"agent-a", "agent-b"}

    @pytest.mark.asyncio
    async def test_get_agent_returns_200(self, client: AsyncClient):
        await client.post("/terraform/agents", json=_resource_payload("my-agent"))
        resp = await client.get("/terraform/agents/my-agent")
        assert resp.status_code == 200
        assert resp.json()["name"] == "my-agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found_returns_404(self, client: AsyncClient):
        resp = await client.get("/terraform/agents/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_agent_increments_version(self, client: AsyncClient):
        await client.post("/terraform/agents", json=_resource_payload("ver-agent", {"v": 1}))
        resp = await client.put(
            "/terraform/agents/ver-agent", json=_resource_payload("ver-agent", {"v": 2})
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 2
        assert data["config"] == {"v": 2}

    @pytest.mark.asyncio
    async def test_update_agent_multiple_times_tracks_version(self, client: AsyncClient):
        await client.post("/terraform/agents", json=_resource_payload("inc-agent"))
        for i in range(5):
            await client.put(
                "/terraform/agents/inc-agent", json=_resource_payload("inc-agent", {"step": i})
            )
        resp = await client.get("/terraform/agents/inc-agent")
        assert resp.json()["version"] == 6  # 1 initial + 5 updates

    @pytest.mark.asyncio
    async def test_update_agent_not_found_returns_404(self, client: AsyncClient):
        resp = await client.put(
            "/terraform/agents/ghost", json=_resource_payload("ghost", {"x": 1})
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_agent_changes_updated_at(self, client: AsyncClient):
        create_resp = await client.post("/terraform/agents", json=_resource_payload("ts-agent"))
        original_updated = create_resp.json()["updated_at"]
        update_resp = await client.put(
            "/terraform/agents/ts-agent", json=_resource_payload("ts-agent", {"new": True})
        )
        assert update_resp.json()["updated_at"] >= original_updated

    @pytest.mark.asyncio
    async def test_delete_agent_returns_200(self, client: AsyncClient):
        await client.post("/terraform/agents", json=_resource_payload("del-agent"))
        resp = await client.delete("/terraform/agents/del-agent")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True, "name": "del-agent"}

    @pytest.mark.asyncio
    async def test_delete_agent_removes_from_list(self, client: AsyncClient):
        await client.post("/terraform/agents", json=_resource_payload("rm-agent"))
        await client.delete("/terraform/agents/rm-agent")
        resp = await client.get("/terraform/agents")
        assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_delete_agent_not_found_returns_404(self, client: AsyncClient):
        resp = await client.delete("/terraform/agents/missing")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_agent_with_empty_config(self, client: AsyncClient):
        resp = await client.post("/terraform/agents", json=_resource_payload("bare-agent"))
        assert resp.status_code == 201
        assert resp.json()["config"] == {}


# ===========================================================================
# PLAYBOOK CRUD
# ===========================================================================
class TestPlaybookCRUD:
    """Tests for /terraform/playbooks endpoints."""

    @pytest.mark.asyncio
    async def test_create_playbook_returns_201(self, client: AsyncClient):
        resp = await client.post(
            "/terraform/playbooks",
            json=_resource_payload("cpu-remediation", {"trigger": "HighCPU"}),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "cpu-remediation"
        assert data["id"].startswith("pb-")
        assert data["version"] == 1

    @pytest.mark.asyncio
    async def test_create_playbook_duplicate_returns_409(self, client: AsyncClient):
        await client.post("/terraform/playbooks", json=_resource_payload("dup-pb"))
        resp = await client.post("/terraform/playbooks", json=_resource_payload("dup-pb"))
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_playbooks_empty(self, client: AsyncClient):
        resp = await client.get("/terraform/playbooks")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_get_playbook_returns_200(self, client: AsyncClient):
        await client.post("/terraform/playbooks", json=_resource_payload("my-pb"))
        resp = await client.get("/terraform/playbooks/my-pb")
        assert resp.status_code == 200
        assert resp.json()["name"] == "my-pb"

    @pytest.mark.asyncio
    async def test_get_playbook_not_found_returns_404(self, client: AsyncClient):
        resp = await client.get("/terraform/playbooks/nope")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_playbook_increments_version(self, client: AsyncClient):
        await client.post("/terraform/playbooks", json=_resource_payload("upd-pb"))
        resp = await client.put(
            "/terraform/playbooks/upd-pb",
            json=_resource_payload("upd-pb", {"steps": ["restart"]}),
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2
        assert resp.json()["config"] == {"steps": ["restart"]}

    @pytest.mark.asyncio
    async def test_update_playbook_not_found_returns_404(self, client: AsyncClient):
        resp = await client.put("/terraform/playbooks/ghost", json=_resource_payload("ghost"))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_playbook_returns_200(self, client: AsyncClient):
        await client.post("/terraform/playbooks", json=_resource_payload("del-pb"))
        resp = await client.delete("/terraform/playbooks/del-pb")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True, "name": "del-pb"}

    @pytest.mark.asyncio
    async def test_delete_playbook_not_found_returns_404(self, client: AsyncClient):
        resp = await client.delete("/terraform/playbooks/nope")
        assert resp.status_code == 404


# ===========================================================================
# POLICY CRUD
# ===========================================================================
class TestPolicyCRUD:
    """Tests for /terraform/policies endpoints."""

    @pytest.mark.asyncio
    async def test_create_policy_returns_201(self, client: AsyncClient):
        resp = await client.post(
            "/terraform/policies",
            json=_resource_payload("blast-radius", {"max_affected": 10}),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "blast-radius"
        assert data["id"].startswith("pol-")
        assert data["version"] == 1

    @pytest.mark.asyncio
    async def test_create_policy_duplicate_returns_409(self, client: AsyncClient):
        await client.post("/terraform/policies", json=_resource_payload("dup-pol"))
        resp = await client.post("/terraform/policies", json=_resource_payload("dup-pol"))
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_list_policies_empty(self, client: AsyncClient):
        resp = await client.get("/terraform/policies")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_list_policies_returns_all(self, client: AsyncClient):
        await client.post("/terraform/policies", json=_resource_payload("pol-a"))
        await client.post("/terraform/policies", json=_resource_payload("pol-b"))
        await client.post("/terraform/policies", json=_resource_payload("pol-c"))
        resp = await client.get("/terraform/policies")
        assert resp.json()["count"] == 3

    @pytest.mark.asyncio
    async def test_get_policy_returns_200(self, client: AsyncClient):
        await client.post("/terraform/policies", json=_resource_payload("my-pol"))
        resp = await client.get("/terraform/policies/my-pol")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_policy_not_found_returns_404(self, client: AsyncClient):
        resp = await client.get("/terraform/policies/missing")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_policy_increments_version(self, client: AsyncClient):
        await client.post("/terraform/policies", json=_resource_payload("upd-pol"))
        resp = await client.put(
            "/terraform/policies/upd-pol",
            json=_resource_payload("upd-pol", {"severity": "high"}),
        )
        assert resp.json()["version"] == 2

    @pytest.mark.asyncio
    async def test_update_policy_not_found_returns_404(self, client: AsyncClient):
        resp = await client.put("/terraform/policies/ghost", json=_resource_payload("ghost"))
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_policy_returns_200(self, client: AsyncClient):
        await client.post("/terraform/policies", json=_resource_payload("del-pol"))
        resp = await client.delete("/terraform/policies/del-pol")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True, "name": "del-pol"}

    @pytest.mark.asyncio
    async def test_delete_policy_not_found_returns_404(self, client: AsyncClient):
        resp = await client.delete("/terraform/policies/missing")
        assert resp.status_code == 404


# ===========================================================================
# WEBHOOK SUBSCRIPTION CRUD
# ===========================================================================
class TestWebhookSubscriptionCRUD:
    """Tests for /terraform/webhook-subscriptions endpoints.

    Webhook subscriptions differ from agents/playbooks/policies: the key is a
    server-generated ID (not the name), so create never conflicts on name.
    """

    @pytest.mark.asyncio
    async def test_create_webhook_returns_201(self, client: AsyncClient):
        resp = await client.post(
            "/terraform/webhook-subscriptions",
            json=_resource_payload("slack-hook", {"url": "https://hooks.slack.com/x"}),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "slack-hook"
        assert data["id"].startswith("wsub-")
        assert data["version"] == 1

    @pytest.mark.asyncio
    async def test_create_multiple_webhooks_with_same_name_allowed(self, client: AsyncClient):
        """Webhook subscriptions are keyed by generated ID, not name."""
        r1 = await client.post("/terraform/webhook-subscriptions", json=_resource_payload("hook"))
        r2 = await client.post("/terraform/webhook-subscriptions", json=_resource_payload("hook"))
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

    @pytest.mark.asyncio
    async def test_list_webhooks_empty(self, client: AsyncClient):
        resp = await client.get("/terraform/webhook-subscriptions")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_list_webhooks_returns_all(self, client: AsyncClient):
        await client.post("/terraform/webhook-subscriptions", json=_resource_payload("h1"))
        await client.post("/terraform/webhook-subscriptions", json=_resource_payload("h2"))
        resp = await client.get("/terraform/webhook-subscriptions")
        assert resp.json()["count"] == 2

    @pytest.mark.asyncio
    async def test_get_webhook_by_id_returns_200(self, client: AsyncClient):
        create_resp = await client.post(
            "/terraform/webhook-subscriptions", json=_resource_payload("my-hook")
        )
        sub_id = create_resp.json()["id"]
        resp = await client.get(f"/terraform/webhook-subscriptions/{sub_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "my-hook"

    @pytest.mark.asyncio
    async def test_get_webhook_not_found_returns_404(self, client: AsyncClient):
        resp = await client.get("/terraform/webhook-subscriptions/wsub-nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_webhook_increments_version(self, client: AsyncClient):
        create_resp = await client.post(
            "/terraform/webhook-subscriptions",
            json=_resource_payload("upd-hook", {"url": "old"}),
        )
        sub_id = create_resp.json()["id"]
        resp = await client.put(
            f"/terraform/webhook-subscriptions/{sub_id}",
            json=_resource_payload("upd-hook", {"url": "new"}),
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2
        assert resp.json()["config"]["url"] == "new"

    @pytest.mark.asyncio
    async def test_update_webhook_not_found_returns_404(self, client: AsyncClient):
        resp = await client.put(
            "/terraform/webhook-subscriptions/wsub-fake",
            json=_resource_payload("x"),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_webhook_returns_200(self, client: AsyncClient):
        create_resp = await client.post(
            "/terraform/webhook-subscriptions", json=_resource_payload("del-hook")
        )
        sub_id = create_resp.json()["id"]
        resp = await client.delete(f"/terraform/webhook-subscriptions/{sub_id}")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True, "id": sub_id}

    @pytest.mark.asyncio
    async def test_delete_webhook_not_found_returns_404(self, client: AsyncClient):
        resp = await client.delete("/terraform/webhook-subscriptions/wsub-gone")
        assert resp.status_code == 404


# ===========================================================================
# TERRAFORM STATE CRUD
# ===========================================================================
class TestTerraformStateCRUD:
    """Tests for /terraform/state/{workspace} endpoints."""

    @pytest.mark.asyncio
    async def test_get_state_not_found_returns_404(self, client: AsyncClient):
        resp = await client.get("/terraform/state/production")
        assert resp.status_code == 404
        assert "No state" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_state_creates_new_state(self, client: AsyncClient):
        state_payload = {
            "version": 4,
            "terraform_version": "1.7.0",
            "serial": 1,
            "lineage": "abc-123",
            "outputs": {"vpc_id": {"value": "vpc-1234"}},
            "resources": [{"type": "aws_instance", "name": "web"}],
        }
        resp = await client.post("/terraform/state/staging", json=state_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["workspace"] == "staging"
        assert data["serial"] == 1

    @pytest.mark.asyncio
    async def test_get_state_after_update_returns_200(self, client: AsyncClient):
        state_payload = {
            "version": 4,
            "terraform_version": "1.7.0",
            "serial": 5,
            "lineage": "xyz-789",
            "outputs": {},
            "resources": [],
        }
        await client.post("/terraform/state/dev", json=state_payload)
        resp = await client.get("/terraform/state/dev")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace"] == "dev"
        assert data["serial"] == 5
        assert data["lineage"] == "xyz-789"
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_update_state_overwrites_previous(self, client: AsyncClient):
        await client.post(
            "/terraform/state/ws1",
            json={"version": 4, "serial": 1, "lineage": "a", "outputs": {}, "resources": []},
        )
        await client.post(
            "/terraform/state/ws1",
            json={
                "version": 4,
                "serial": 2,
                "lineage": "a",
                "outputs": {},
                "resources": [{"type": "new"}],
            },
        )
        resp = await client.get("/terraform/state/ws1")
        data = resp.json()
        assert data["serial"] == 2
        assert len(data["resources"]) == 1

    @pytest.mark.asyncio
    async def test_delete_state_returns_200(self, client: AsyncClient):
        await client.post(
            "/terraform/state/tmp",
            json={"version": 4, "serial": 1, "lineage": "l", "outputs": {}, "resources": []},
        )
        resp = await client.delete("/terraform/state/tmp")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True, "workspace": "tmp"}

    @pytest.mark.asyncio
    async def test_delete_state_not_found_returns_404(self, client: AsyncClient):
        resp = await client.delete("/terraform/state/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_state_then_get_returns_404(self, client: AsyncClient):
        await client.post(
            "/terraform/state/ephemeral",
            json={"version": 4, "serial": 1, "lineage": "e", "outputs": {}, "resources": []},
        )
        await client.delete("/terraform/state/ephemeral")
        resp = await client.get("/terraform/state/ephemeral")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_state_with_minimal_payload(self, client: AsyncClient):
        """StateData has defaults, so an empty-ish body should work."""
        resp = await client.post("/terraform/state/minimal", json={})
        assert resp.status_code == 200
        state = await client.get("/terraform/state/minimal")
        data = state.json()
        assert data["version"] == 4  # default
        assert data["serial"] == 0  # default


# ===========================================================================
# TERRAFORM STATE LOCKING
# ===========================================================================
class TestTerraformStateLocking:
    """Tests for /terraform/state/{workspace}/lock endpoints."""

    @pytest.mark.asyncio
    async def test_acquire_lock_returns_lock_info(self, client: AsyncClient):
        lock_body = {
            "ID": "lock-abc123",
            "Operation": "OperationTypeApply",
            "Info": "",
            "Who": "user@host",
            "Version": "1.7.0",
            "Created": "",
            "Path": "staging",
        }
        resp = await client.put("/terraform/state/staging/lock", json=lock_body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ID"] == "lock-abc123"
        assert data["Operation"] == "OperationTypeApply"
        assert data["Who"] == "user@host"
        assert data["Created"] != ""  # server populates timestamp

    @pytest.mark.asyncio
    async def test_acquire_lock_generates_id_when_empty(self, client: AsyncClient):
        resp = await client.put(
            "/terraform/state/auto-id/lock",
            json={"Operation": "plan"},
        )
        assert resp.status_code == 200
        assert resp.json()["ID"].startswith("lock-")

    @pytest.mark.asyncio
    async def test_acquire_lock_conflict_returns_409(self, client: AsyncClient):
        lock_body = {"ID": "first-lock", "Operation": "apply"}
        await client.put("/terraform/state/prod/lock", json=lock_body)
        resp = await client.put(
            "/terraform/state/prod/lock",
            json={"ID": "second-lock", "Operation": "apply"},
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "already locked" in detail["message"]
        assert detail["lock"]["ID"] == "first-lock"

    @pytest.mark.asyncio
    async def test_release_lock_returns_200(self, client: AsyncClient):
        await client.put(
            "/terraform/state/ws/lock",
            json={"ID": "my-lock", "Operation": "apply"},
        )
        resp = await client.request(
            "DELETE",
            "/terraform/state/ws/lock",
            json={"ID": "my-lock"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"unlocked": True, "workspace": "ws"}

    @pytest.mark.asyncio
    async def test_release_lock_no_lock_returns_404(self, client: AsyncClient):
        resp = await client.request(
            "DELETE",
            "/terraform/state/empty/lock",
            json={"ID": "anything"},
        )
        assert resp.status_code == 404
        assert "No lock found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_release_lock_id_mismatch_returns_409(self, client: AsyncClient):
        await client.put(
            "/terraform/state/ws2/lock",
            json={"ID": "real-lock-id", "Operation": "apply"},
        )
        resp = await client.request(
            "DELETE",
            "/terraform/state/ws2/lock",
            json={"ID": "wrong-lock-id"},
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["message"] == "Lock ID mismatch"
        assert detail["expected"] == "real-lock-id"
        assert detail["received"] == "wrong-lock-id"

    @pytest.mark.asyncio
    async def test_release_lock_empty_id_skips_verification(self, client: AsyncClient):
        """When body.ID is empty, the unlock should succeed without matching."""
        await client.put(
            "/terraform/state/lenient/lock",
            json={"ID": "the-lock", "Operation": "apply"},
        )
        resp = await client.request(
            "DELETE",
            "/terraform/state/lenient/lock",
            json={"ID": ""},
        )
        assert resp.status_code == 200
        assert resp.json()["unlocked"] is True

    @pytest.mark.asyncio
    async def test_get_lock_info_when_locked(self, client: AsyncClient):
        await client.put(
            "/terraform/state/info-ws/lock",
            json={"ID": "info-lock", "Operation": "plan", "Who": "ci-bot"},
        )
        resp = await client.get("/terraform/state/info-ws/lock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["locked"] is True
        assert data["workspace"] == "info-ws"
        assert data["lock"]["ID"] == "info-lock"
        assert data["lock"]["Who"] == "ci-bot"

    @pytest.mark.asyncio
    async def test_get_lock_info_when_unlocked(self, client: AsyncClient):
        resp = await client.get("/terraform/state/free-ws/lock")
        assert resp.status_code == 200
        data = resp.json()
        assert data["locked"] is False
        assert data["workspace"] == "free-ws"
        assert "lock" not in data

    @pytest.mark.asyncio
    async def test_lock_then_unlock_then_relock_succeeds(self, client: AsyncClient):
        """After releasing a lock, a new lock can be acquired."""
        await client.put(
            "/terraform/state/cycle/lock",
            json={"ID": "lock-1", "Operation": "apply"},
        )
        await client.request(
            "DELETE",
            "/terraform/state/cycle/lock",
            json={"ID": "lock-1"},
        )
        resp = await client.put(
            "/terraform/state/cycle/lock",
            json={"ID": "lock-2", "Operation": "plan"},
        )
        assert resp.status_code == 200
        assert resp.json()["ID"] == "lock-2"

    @pytest.mark.asyncio
    async def test_lock_uses_workspace_as_default_path(self, client: AsyncClient):
        resp = await client.put(
            "/terraform/state/default-path/lock",
            json={"ID": "p-lock", "Operation": "apply"},
        )
        assert resp.json()["Path"] == "default-path"

    @pytest.mark.asyncio
    async def test_lock_preserves_custom_path(self, client: AsyncClient):
        resp = await client.put(
            "/terraform/state/custom/lock",
            json={"ID": "c-lock", "Operation": "apply", "Path": "custom/override"},
        )
        assert resp.json()["Path"] == "custom/override"


# ===========================================================================
# CROSS-CUTTING / INTEGRATION SCENARIOS
# ===========================================================================
class TestCrossCuttingScenarios:
    """Tests that exercise interactions across multiple endpoints."""

    @pytest.mark.asyncio
    async def test_full_agent_lifecycle_create_read_update_delete(self, client: AsyncClient):
        """End-to-end lifecycle: create -> read -> update -> verify version -> delete -> 404."""
        # Create
        create = await client.post(
            "/terraform/agents", json=_resource_payload("lifecycle", {"stage": "init"})
        )
        assert create.status_code == 201

        # Read
        read = await client.get("/terraform/agents/lifecycle")
        assert read.json()["config"]["stage"] == "init"

        # Update
        update = await client.put(
            "/terraform/agents/lifecycle", json=_resource_payload("lifecycle", {"stage": "prod"})
        )
        assert update.json()["version"] == 2
        assert update.json()["config"]["stage"] == "prod"

        # Delete
        delete = await client.delete("/terraform/agents/lifecycle")
        assert delete.json()["deleted"] is True

        # Verify gone
        gone = await client.get("/terraform/agents/lifecycle")
        assert gone.status_code == 404

    @pytest.mark.asyncio
    async def test_different_resource_types_are_isolated(self, client: AsyncClient):
        """Creating an agent named 'foo' does not conflict with a playbook named 'foo'."""
        r1 = await client.post("/terraform/agents", json=_resource_payload("foo"))
        r2 = await client.post("/terraform/playbooks", json=_resource_payload("foo"))
        r3 = await client.post("/terraform/policies", json=_resource_payload("foo"))
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r3.status_code == 201

    @pytest.mark.asyncio
    async def test_state_operations_independent_across_workspaces(self, client: AsyncClient):
        """State in workspace A is not visible from workspace B."""
        await client.post(
            "/terraform/state/ws-alpha",
            json={"version": 4, "serial": 10, "lineage": "a", "outputs": {}, "resources": []},
        )
        resp = await client.get("/terraform/state/ws-beta")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_locks_are_per_workspace(self, client: AsyncClient):
        """Locking workspace A does not lock workspace B."""
        await client.put(
            "/terraform/state/locked-ws/lock",
            json={"ID": "lock-a", "Operation": "apply"},
        )
        resp = await client.put(
            "/terraform/state/unlocked-ws/lock",
            json={"ID": "lock-b", "Operation": "plan"},
        )
        assert resp.status_code == 200  # no conflict

    @pytest.mark.asyncio
    async def test_create_agent_preserves_created_at_on_update(self, client: AsyncClient):
        """created_at should not change when the resource is updated."""
        create_resp = await client.post("/terraform/agents", json=_resource_payload("stable-ts"))
        original_created = create_resp.json()["created_at"]
        await client.put(
            "/terraform/agents/stable-ts", json=_resource_payload("stable-ts", {"x": 1})
        )
        get_resp = await client.get("/terraform/agents/stable-ts")
        assert get_resp.json()["created_at"] == original_created
