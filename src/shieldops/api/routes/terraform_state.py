"""Terraform remote state backend — locking and state storage endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# In-memory state and lock storage
_state_store: dict[str, dict[str, Any]] = {}
_locks: dict[str, dict[str, Any]] = {}


class StateLockRequest(BaseModel):
    """Terraform state lock request."""

    ID: str = ""  # noqa: N815 — Terraform sends uppercase
    Operation: str = ""  # noqa: N815
    Info: str = ""  # noqa: N815
    Who: str = ""  # noqa: N815
    Version: str = ""  # noqa: N815
    Created: str = ""  # noqa: N815
    Path: str = ""  # noqa: N815


class StateData(BaseModel):
    """Terraform state payload."""

    version: int = 4
    terraform_version: str = ""
    serial: int = 0
    lineage: str = ""
    outputs: dict[str, Any] = Field(default_factory=dict)
    resources: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# State CRUD
# ---------------------------------------------------------------------------
@router.get("/terraform/state/{workspace}")
async def get_state(workspace: str) -> dict[str, Any]:
    """Get current state for a workspace."""
    state = _state_store.get(workspace)
    if state is None:
        raise HTTPException(status_code=404, detail=f"No state for workspace '{workspace}'")
    return state


@router.post("/terraform/state/{workspace}")
async def update_state(workspace: str, body: StateData) -> dict[str, Any]:
    """Update state for a workspace. Must hold the lock."""
    _locks.get(workspace)  # In production, verify lock ID matches caller
    _state_store[workspace] = {
        **body.model_dump(),
        "workspace": workspace,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    return {"status": "ok", "workspace": workspace, "serial": body.serial}


@router.delete("/terraform/state/{workspace}")
async def delete_state(workspace: str) -> dict[str, Any]:
    """Delete state for a workspace."""
    if workspace not in _state_store:
        raise HTTPException(status_code=404, detail=f"No state for workspace '{workspace}'")
    del _state_store[workspace]
    return {"deleted": True, "workspace": workspace}


# ---------------------------------------------------------------------------
# State locking
# ---------------------------------------------------------------------------
@router.put("/terraform/state/{workspace}/lock")
async def lock_state(workspace: str, body: StateLockRequest) -> dict[str, Any]:
    """Acquire a lock for a workspace."""
    existing = _locks.get(workspace)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"State for '{workspace}' is already locked",
                "lock": existing,
            },
        )

    lock_id = body.ID or f"lock-{uuid4().hex[:12]}"
    lock = {
        "ID": lock_id,
        "Operation": body.Operation,
        "Info": body.Info,
        "Who": body.Who,
        "Version": body.Version,
        "Created": datetime.now(UTC).isoformat(),
        "Path": body.Path or workspace,
    }
    _locks[workspace] = lock
    return lock


@router.delete("/terraform/state/{workspace}/lock")
async def unlock_state(workspace: str, body: StateLockRequest) -> dict[str, Any]:
    """Release a lock for a workspace."""
    existing = _locks.get(workspace)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"No lock found for workspace '{workspace}'",
        )

    # Verify lock ID matches
    if body.ID and existing["ID"] != body.ID:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Lock ID mismatch",
                "expected": existing["ID"],
                "received": body.ID,
            },
        )

    del _locks[workspace]
    return {"unlocked": True, "workspace": workspace}


# ---------------------------------------------------------------------------
# Lock info
# ---------------------------------------------------------------------------
@router.get("/terraform/state/{workspace}/lock")
async def get_lock_info(workspace: str) -> dict[str, Any]:
    """Get lock info for a workspace."""
    lock = _locks.get(workspace)
    if lock is None:
        return {"locked": False, "workspace": workspace}
    return {"locked": True, "workspace": workspace, "lock": lock}
