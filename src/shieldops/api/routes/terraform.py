"""Terraform provider–compatible CRUD endpoints for ShieldOps resources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory stores (production would use DB)
# ---------------------------------------------------------------------------
_agents: dict[str, dict[str, Any]] = {}
_playbooks: dict[str, dict[str, Any]] = {}
_policies: dict[str, dict[str, Any]] = {}
_webhook_subscriptions: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _gen_id(prefix: str = "tf") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class TerraformResource(BaseModel):
    """Envelope for all Terraform-managed resources."""

    id: str = ""
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: str = ""
    updated_at: str = ""


class TerraformImportRequest(BaseModel):
    resource_type: str
    resource_id: str


# ---------------------------------------------------------------------------
# Agent config resources
# ---------------------------------------------------------------------------
@router.get("/terraform/agents")
async def list_agent_configs() -> dict[str, Any]:
    return {"resources": list(_agents.values()), "count": len(_agents)}


@router.get("/terraform/agents/{name}")
async def get_agent_config(name: str) -> dict[str, Any]:
    resource = _agents.get(name)
    if resource is None:
        raise HTTPException(status_code=404, detail=f"Agent config '{name}' not found")
    return resource


@router.post("/terraform/agents", status_code=201)
async def create_agent_config(body: TerraformResource) -> dict[str, Any]:
    if body.name in _agents:
        raise HTTPException(status_code=409, detail=f"Agent config '{body.name}' already exists")
    now = _now_iso()
    resource = {
        "id": _gen_id("agent"),
        "name": body.name,
        "config": body.config,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    _agents[body.name] = resource
    return resource


@router.put("/terraform/agents/{name}")
async def update_agent_config(name: str, body: TerraformResource) -> dict[str, Any]:
    existing = _agents.get(name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Agent config '{name}' not found")
    existing["config"] = body.config
    existing["version"] = existing["version"] + 1
    existing["updated_at"] = _now_iso()
    return existing


@router.delete("/terraform/agents/{name}")
async def delete_agent_config(name: str) -> dict[str, Any]:
    if name not in _agents:
        raise HTTPException(status_code=404, detail=f"Agent config '{name}' not found")
    del _agents[name]
    return {"deleted": True, "name": name}


# ---------------------------------------------------------------------------
# Playbook resources
# ---------------------------------------------------------------------------
@router.get("/terraform/playbooks")
async def list_playbooks() -> dict[str, Any]:
    return {"resources": list(_playbooks.values()), "count": len(_playbooks)}


@router.get("/terraform/playbooks/{name}")
async def get_playbook(name: str) -> dict[str, Any]:
    resource = _playbooks.get(name)
    if resource is None:
        raise HTTPException(status_code=404, detail=f"Playbook '{name}' not found")
    return resource


@router.post("/terraform/playbooks", status_code=201)
async def create_playbook(body: TerraformResource) -> dict[str, Any]:
    if body.name in _playbooks:
        raise HTTPException(status_code=409, detail=f"Playbook '{body.name}' already exists")
    now = _now_iso()
    resource = {
        "id": _gen_id("pb"),
        "name": body.name,
        "config": body.config,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    _playbooks[body.name] = resource
    return resource


@router.put("/terraform/playbooks/{name}")
async def update_playbook(name: str, body: TerraformResource) -> dict[str, Any]:
    existing = _playbooks.get(name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Playbook '{name}' not found")
    existing["config"] = body.config
    existing["version"] = existing["version"] + 1
    existing["updated_at"] = _now_iso()
    return existing


@router.delete("/terraform/playbooks/{name}")
async def delete_playbook(name: str) -> dict[str, Any]:
    if name not in _playbooks:
        raise HTTPException(status_code=404, detail=f"Playbook '{name}' not found")
    del _playbooks[name]
    return {"deleted": True, "name": name}


# ---------------------------------------------------------------------------
# Policy resources
# ---------------------------------------------------------------------------
@router.get("/terraform/policies")
async def list_policies() -> dict[str, Any]:
    return {"resources": list(_policies.values()), "count": len(_policies)}


@router.get("/terraform/policies/{name}")
async def get_policy(name: str) -> dict[str, Any]:
    resource = _policies.get(name)
    if resource is None:
        raise HTTPException(status_code=404, detail=f"Policy '{name}' not found")
    return resource


@router.post("/terraform/policies", status_code=201)
async def create_policy(body: TerraformResource) -> dict[str, Any]:
    if body.name in _policies:
        raise HTTPException(status_code=409, detail=f"Policy '{body.name}' already exists")
    now = _now_iso()
    resource = {
        "id": _gen_id("pol"),
        "name": body.name,
        "config": body.config,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    _policies[body.name] = resource
    return resource


@router.put("/terraform/policies/{name}")
async def update_policy(name: str, body: TerraformResource) -> dict[str, Any]:
    existing = _policies.get(name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Policy '{name}' not found")
    existing["config"] = body.config
    existing["version"] = existing["version"] + 1
    existing["updated_at"] = _now_iso()
    return existing


@router.delete("/terraform/policies/{name}")
async def delete_policy(name: str) -> dict[str, Any]:
    if name not in _policies:
        raise HTTPException(status_code=404, detail=f"Policy '{name}' not found")
    del _policies[name]
    return {"deleted": True, "name": name}


# ---------------------------------------------------------------------------
# Webhook subscription resources
# ---------------------------------------------------------------------------
@router.get("/terraform/webhook-subscriptions")
async def list_tf_webhook_subs() -> dict[str, Any]:
    return {
        "resources": list(_webhook_subscriptions.values()),
        "count": len(_webhook_subscriptions),
    }


@router.get("/terraform/webhook-subscriptions/{sub_id}")
async def get_tf_webhook_sub(sub_id: str) -> dict[str, Any]:
    resource = _webhook_subscriptions.get(sub_id)
    if resource is None:
        raise HTTPException(status_code=404, detail=f"Webhook subscription '{sub_id}' not found")
    return resource


@router.post("/terraform/webhook-subscriptions", status_code=201)
async def create_tf_webhook_sub(body: TerraformResource) -> dict[str, Any]:
    sub_id = _gen_id("wsub")
    now = _now_iso()
    resource = {
        "id": sub_id,
        "name": body.name,
        "config": body.config,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    _webhook_subscriptions[sub_id] = resource
    return resource


@router.put("/terraform/webhook-subscriptions/{sub_id}")
async def update_tf_webhook_sub(sub_id: str, body: TerraformResource) -> dict[str, Any]:
    existing = _webhook_subscriptions.get(sub_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Webhook subscription '{sub_id}' not found")
    existing["config"] = body.config
    existing["version"] = existing["version"] + 1
    existing["updated_at"] = _now_iso()
    return existing


@router.delete("/terraform/webhook-subscriptions/{sub_id}")
async def delete_tf_webhook_sub(sub_id: str) -> dict[str, Any]:
    if sub_id not in _webhook_subscriptions:
        raise HTTPException(status_code=404, detail=f"Webhook subscription '{sub_id}' not found")
    del _webhook_subscriptions[sub_id]
    return {"deleted": True, "id": sub_id}
