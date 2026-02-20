"""Playbook CRUD API routes for creating, editing, and validating playbooks."""

from __future__ import annotations

import os
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import (
    get_current_user,
    require_role,
)
from shieldops.api.auth.models import UserResponse, UserRole

logger = structlog.get_logger()

router = APIRouter()

_repository: Any | None = None

# Directory where built-in playbooks live on the filesystem
_BUILTIN_PLAYBOOK_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "playbooks",
)

# Actions that are never allowed in playbooks
DANGEROUS_ACTIONS = frozenset(
    {
        "drop_database",
        "drop_table",
        "delete_database",
        "delete_iam_root",
        "modify_iam_root_policy",
        "rm_rf",
        "format_disk",
        "truncate_audit_log",
    }
)

# Required top-level fields for a valid playbook
REQUIRED_FIELDS = {"name", "description", "trigger", "steps"}

# Required fields in each step
REQUIRED_STEP_FIELDS = {"action", "target", "params"}


def set_repository(repo: Any | None) -> None:
    """Set the repository instance for DB access."""
    global _repository
    _repository = repo


# ── Pydantic request/response models ────────────────────────


class PlaybookCreate(BaseModel):
    """Request body for creating a new playbook."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    content: str = Field(..., min_length=1, description="YAML content")
    tags: list[str] = Field(default_factory=list)


class PlaybookUpdate(BaseModel):
    """Request body for updating a playbook."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None


class PlaybookResponse(BaseModel):
    """Playbook response shape."""

    id: str
    name: str
    description: str
    content: str
    tags: list[str]
    source: str  # "builtin" | "custom"
    is_valid: bool
    created_at: str | None = None
    updated_at: str | None = None


class ValidationResult(BaseModel):
    """Result of YAML validation."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DryRunStep(BaseModel):
    """A step that would execute during dry run."""

    action: str
    target: str
    params: dict[str, Any] = Field(default_factory=dict)


class DryRunResult(BaseModel):
    """Dry-run preview of playbook execution."""

    playbook_name: str
    total_steps: int
    steps: list[DryRunStep]
    warnings: list[str] = Field(default_factory=list)


# ── Validation helpers ───────────────────────────────────────


def _validate_playbook_yaml(
    content: str,
) -> ValidationResult:
    """Validate playbook YAML content and structure."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Parse YAML
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Invalid YAML syntax: {exc}"],
        )

    if not isinstance(data, dict):
        return ValidationResult(
            is_valid=False,
            errors=["Playbook must be a YAML mapping"],
        )

    # 2. Required top-level fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    if errors:
        return ValidationResult(is_valid=False, errors=errors)

    # 3. Validate trigger
    trigger = data.get("trigger")
    if trigger is not None and not isinstance(trigger, dict):
        errors.append("'trigger' must be a mapping")

    # 4. Validate steps
    steps = data.get("steps")
    if not isinstance(steps, list):
        errors.append("'steps' must be a list")
    elif len(steps) == 0:
        errors.append("'steps' must contain at least one step")
    else:
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i} must be a mapping")
                continue
            for sf in REQUIRED_STEP_FIELDS:
                if sf not in step:
                    errors.append(f"Step {i}: missing '{sf}'")

            # Check for dangerous actions
            action = step.get("action", "")
            if isinstance(action, str):
                action_lower = action.lower()
                if action_lower in DANGEROUS_ACTIONS:
                    errors.append(f"Step {i}: action '{action}' is prohibited")

    # 5. Warnings for optional best practices
    if not data.get("description"):
        warnings.append("Consider adding a description")

    is_valid = len(errors) == 0
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
    )


def _load_builtin_playbooks() -> list[dict[str, Any]]:
    """Load built-in playbooks from the filesystem."""
    playbooks: list[dict[str, Any]] = []
    playbook_dir = os.path.normpath(_BUILTIN_PLAYBOOK_DIR)

    if not os.path.isdir(playbook_dir):
        return playbooks

    for filename in sorted(os.listdir(playbook_dir)):
        if not filename.endswith((".yaml", ".yml")):
            continue

        filepath = os.path.join(playbook_dir, filename)
        try:
            with open(filepath) as f:
                content = f.read()
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                name = data.get("name", filename.rsplit(".", 1)[0])
                playbooks.append(
                    {
                        "id": f"builtin-{name}",
                        "name": name,
                        "description": data.get("description", ""),
                        "content": content,
                        "tags": [],
                        "source": "builtin",
                        "is_valid": True,
                        "created_at": None,
                        "updated_at": None,
                    }
                )
        except Exception as exc:
            logger.warning(
                "builtin_playbook_load_error",
                file=filename,
                error=str(exc),
            )
    return playbooks


# ── API Endpoints ────────────────────────────────────────────


@router.post("/playbooks/custom")
async def create_playbook(
    body: PlaybookCreate,
    user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Create a new custom playbook."""
    if _repository is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    # Validate YAML content
    validation = _validate_playbook_yaml(body.content)
    if not validation.is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid playbook",
                "errors": validation.errors,
            },
        )

    result = await _repository.create_playbook(
        name=body.name,
        description=body.description,
        content=body.content,
        tags=body.tags,
        created_by=user.id,
    )
    result["source"] = "custom"
    result["is_valid"] = True
    return result  # type: ignore[no-any-return]


@router.get("/playbooks/custom")
async def list_playbooks(
    include_builtin: bool = True,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all playbooks (custom from DB + builtin)."""
    custom: list[dict[str, Any]] = []
    if _repository is not None:
        custom = await _repository.list_playbooks()
        for pb in custom:
            pb["source"] = "custom"
            val = _validate_playbook_yaml(pb.get("content", ""))
            pb["is_valid"] = val.is_valid

    builtin: list[dict[str, Any]] = []
    if include_builtin:
        builtin = _load_builtin_playbooks()

    all_playbooks = custom + builtin
    return {
        "playbooks": all_playbooks,
        "total": len(all_playbooks),
        "custom_count": len(custom),
        "builtin_count": len(builtin),
    }


@router.get("/playbooks/custom/{playbook_id}")
async def get_playbook(
    playbook_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a playbook by ID (custom or builtin)."""
    # Check builtin playbooks first
    if playbook_id.startswith("builtin-"):
        for pb in _load_builtin_playbooks():
            if pb["id"] == playbook_id:
                return pb
        raise HTTPException(
            status_code=404,
            detail="Playbook not found",
        )

    # Check custom playbooks in DB
    if _repository is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    result = await _repository.get_playbook(playbook_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Playbook not found",
        )
    result["source"] = "custom"
    val = _validate_playbook_yaml(result.get("content", ""))
    result["is_valid"] = val.is_valid
    return result  # type: ignore[no-any-return]


@router.put("/playbooks/custom/{playbook_id}")
async def update_playbook(
    playbook_id: str,
    body: PlaybookUpdate,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Update a custom playbook."""
    if playbook_id.startswith("builtin-"):
        raise HTTPException(
            status_code=400,
            detail="Cannot modify built-in playbooks",
        )

    if _repository is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    # Validate new content if provided
    if body.content is not None:
        validation = _validate_playbook_yaml(body.content)
        if not validation.is_valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Invalid playbook",
                    "errors": validation.errors,
                },
            )

    update_fields: dict[str, Any] = {}
    if body.name is not None:
        update_fields["name"] = body.name
    if body.description is not None:
        update_fields["description"] = body.description
    if body.content is not None:
        update_fields["content"] = body.content
    if body.tags is not None:
        update_fields["tags"] = body.tags

    if not update_fields:
        raise HTTPException(
            status_code=400,
            detail="No fields to update",
        )

    result = await _repository.update_playbook(playbook_id, **update_fields)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Playbook not found",
        )
    result["source"] = "custom"
    val = _validate_playbook_yaml(result.get("content", ""))
    result["is_valid"] = val.is_valid
    return result  # type: ignore[no-any-return]


@router.delete("/playbooks/custom/{playbook_id}")
async def delete_playbook(
    playbook_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Soft-delete a custom playbook."""
    if playbook_id.startswith("builtin-"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete built-in playbooks",
        )

    if _repository is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    deleted = await _repository.delete_playbook(playbook_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Playbook not found",
        )
    return {
        "playbook_id": playbook_id,
        "deleted": True,
    }


@router.post("/playbooks/custom/{playbook_id}/validate")
async def validate_playbook(
    playbook_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> ValidationResult:
    """Validate a playbook's YAML without saving."""
    # Check builtin
    if playbook_id.startswith("builtin-"):
        for pb in _load_builtin_playbooks():
            if pb["id"] == playbook_id:
                return _validate_playbook_yaml(pb["content"])
        raise HTTPException(
            status_code=404,
            detail="Playbook not found",
        )

    if _repository is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    result = await _repository.get_playbook(playbook_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Playbook not found",
        )

    return _validate_playbook_yaml(result.get("content", ""))


@router.post("/playbooks/validate")
async def validate_playbook_content(
    body: PlaybookCreate,
    _user: UserResponse = Depends(get_current_user),
) -> ValidationResult:
    """Validate raw YAML content without saving."""
    return _validate_playbook_yaml(body.content)


@router.post("/playbooks/custom/{playbook_id}/dry-run")
async def dry_run_playbook(
    playbook_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> DryRunResult:
    """Preview what actions a playbook would execute."""
    # Resolve playbook content
    content: str | None = None
    pb_name: str = playbook_id

    if playbook_id.startswith("builtin-"):
        for pb in _load_builtin_playbooks():
            if pb["id"] == playbook_id:
                content = pb["content"]
                pb_name = pb["name"]
                break
        if content is None:
            raise HTTPException(
                status_code=404,
                detail="Playbook not found",
            )
    else:
        if _repository is None:
            raise HTTPException(
                status_code=503,
                detail="DB unavailable",
            )
        result = await _repository.get_playbook(playbook_id)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Playbook not found",
            )
        content = result.get("content", "")
        pb_name = result.get("name", playbook_id)

    # Parse and extract steps
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML: {exc}",
        ) from None

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="Playbook must be a YAML mapping",
        )

    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list):
        raise HTTPException(
            status_code=400,
            detail="'steps' must be a list",
        )

    steps: list[DryRunStep] = []
    warnings: list[str] = []
    for i, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            warnings.append(f"Step {i}: not a valid mapping")
            continue
        action = str(step.get("action", "unknown"))
        target = str(step.get("target", "unknown"))
        params = step.get("params", {})
        if not isinstance(params, dict):
            params = {}

        if action.lower() in DANGEROUS_ACTIONS:
            warnings.append(f"Step {i}: '{action}' is prohibited")
        else:
            steps.append(
                DryRunStep(
                    action=action,
                    target=target,
                    params=params,
                )
            )

    return DryRunResult(
        playbook_name=pb_name,
        total_steps=len(steps),
        steps=steps,
        warnings=warnings,
    )
